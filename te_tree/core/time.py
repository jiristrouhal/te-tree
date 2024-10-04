from __future__ import annotations
import dataclasses
from typing import Any, Callable, Optional
import abc
import bisect

from te_tree.core.item import Item, Parentage_Data
from te_tree.cmd.commands import Command
from te_tree.core.attributes import (
    Attribute,
    Attribute_Factory,
    Attribute_List,
    AbstractAttribute,
)
from te_tree.core.attributes import AttributeType


@dataclasses.dataclass(frozen=True)
class Timepoint_Data:
    tline: Timeline
    item: Item


@dataclasses.dataclass(frozen=True)
class Add_Item(Command):
    data: Timepoint_Data

    def run(self) -> None:
        self.data.tline._add_item_tree_to_timeline(self.data.item)

    def undo(self) -> None:
        self.data.tline._remove_item_tree(self.data.item)

    def redo(self) -> None:
        self.data.tline._add_item_tree_to_timeline(self.data.item)


@dataclasses.dataclass(frozen=True)
class Remove_Item(Command):
    data: Timepoint_Data

    def run(self) -> None:
        self.data.tline._remove_item_tree(self.data.item)

    def undo(self) -> None:
        self.data.tline._add_item_tree_to_timeline(self.data.item)

    def redo(self) -> None:
        self.data.tline._remove_item_tree(self.data.item)



@dataclasses.dataclass(frozen=True)
class Binding:
    output: str
    func: Callable[[Any], Any]
    inputs: tuple[str, ...]


class Timeline:

    def __init__(
        self,
        root: Item,
        attribute_factory: Attribute_Factory,
        timelike_var_label: str,
        timelike_var_type: AttributeType,
        tvars: dict[str, dict[str, Any]] | None = None,
    ) -> None:

        if tvars is None:
            tvars = {}

        self._timename = timelike_var_label
        self._time_type = timelike_var_type
        self._id = str(id(self))

        self._points: dict[Any, TimepointRegular] = {}
        self._time: list[Any] = list()
        self.__vars: dict[str, dict[str, Any]] = tvars

        self._bindings: dict[str, Binding] = dict()
        for label in self.__vars:
            self._bindings[label] = Binding(label, lambda x: x, (label,))

        self.__attribute_factory = attribute_factory

        self._init_point = TimepointInit(self._create_vars(), self)
        self._update_dependencies(self._init_point)

        self._add_item_tree_to_timeline(root)

    @property
    def points(self) -> dict[Any, TimepointRegular]:
        return self._points.copy()

    @property
    def var_info(self) -> dict[str, dict[str, Any]]:
        return self.__vars.copy()

    @property
    def attrfac(self) -> Attribute_Factory:
        return self.__attribute_factory

    @property
    def timename(self) -> str:
        return self._timename

    def bind(self, dependent: str, func: Callable[[Any], Any], *free: str) -> None:
        if dependent not in self.__vars:
            raise Timeline.UndefinedVariable(dependent)
        self._bindings[dependent] = Binding(dependent, func, free)
        self._set_dependency(dependent, self._init_point, self._init_point)
        prev_point: Timepoint = self._init_point
        for time in self._time:
            point = self._points[time]
            self._set_dependency(dependent, point, prev_point)
            prev_point = point

    def response(self, variable: Attribute, input_change: Any, output_label: str, time: Any) -> Any:
        current_value = self(output_label, time)
        variable.set(variable.value + input_change)
        updated_value = self(output_label, time)
        self.attrfac.undo_and_forget()
        return updated_value - current_value

    def set_init(self, var_label: str, value: Any) -> None:
        if var_label not in self.__vars:
            raise Timeline.UndefinedVariable(var_label)
        self._init_point.init_var(var_label).set(value)

    def _add_item_tree_to_timeline(self, item: Item) -> None:
        self._set_up_hierarchy_edit_commands(item)
        if self._has_time(item):
            self._add_item_to_timeline(item, item(self.timename))
        for child in item.children:
            self._add_item_tree_to_timeline(child)

    def _add_item_to_timeline(self, item: Item, time: Any) -> None:
        if time not in self._points:
            point = self._create_point(time)
        else:
            point = self._points[time]
        point._add_item(item)

    def _create_point(self, time: Any) -> TimepointRegular:
        point = self.__new_point(time)
        self._update_dependencies(point)
        next_point = self.next_point(point)
        if next_point is not None:
            self._update_dependencies(next_point)
        return point

    def _pick_last_point(self, time: Any) -> Timepoint:
        last_point_time = self._last_point_time(time)
        if last_point_time is None:
            return self._init_point
        else:
            return self._points[last_point_time]

    def _remove_item_tree(self, item: Item) -> None:
        for child in item.children:
            self._remove_item_tree(child)
        if self._has_time(item):
            self._remove_item_from_timeline(item, item(self.timename))
        self._clean_up_hierarchy_edit_commands(item)

    def _remove_item_from_timeline(self, item: Item, time: Any) -> None:
        point = self._points[time]
        point._remove_item(item)
        if not point.has_items():
            self._remove_point(point)

    def _remove_point(self, point: TimepointRegular) -> None:
        next_point = self.next_point(point)
        self._points.pop(point.time)
        self._time.remove(point.time)
        if next_point is not None:
            self._update_dependencies(next_point)

    def __new_point(self, time: Any) -> TimepointRegular:
        vars = self._create_vars()
        vars[self._timename] = self.attrfac.new(self._time_type, time, self.timename)
        insert_to_sorted_list(time, self._time)
        self._points[time] = TimepointRegular(vars, self)
        return self._points[time]

    def prev_point(self, point: Timepoint) -> Timepoint:
        if point is self._init_point:
            return self._init_point
        point_time = point.time
        i = self._time.index(point_time)
        if i == 0:
            return self._init_point
        else:
            return self._points[self._time[i - 1]]

    def next_point(self, point: Timepoint) -> Timepoint | None:
        if point == self._init_point and self._points:
            return self._points[self._time[0]]
        i = self._time.index(point.time)
        if i < len(self._time) - 1:
            return self._points[self._time[i + 1]]
        else:
            return None

    def _has_time(self, item: Item) -> bool:
        if not item.has_attribute(self._timename):
            return False
        elif item.attribute(self._timename).type != self._time_type:
            raise Timeline.TimelikeVariableTypeConflict(
                f"Trying to add '{item.attribute('seconds').type}'"
                f"instead of '{self._time_type}'."
            )
        return True

    def _clean_up_hierarchy_edit_commands(self, item: Item) -> None:
        item.command["adopt"].post.pop(self._id)
        item.command["leave"].pre.pop(self._id)

    def _set_up_hierarchy_edit_commands(self, item: Item) -> None:
        def _adopt(data: Parentage_Data):
            return Add_Item(Timepoint_Data(self, data.child))

        def _leave(data: Parentage_Data):
            return Remove_Item(Timepoint_Data(self, data.child))

        item.command["adopt"].add(self._id, _adopt, "post")
        item.command["leave"].add(self._id, _leave, "pre")

    def _update_dependencies(self, point: Timepoint) -> None:
        prev_point = self.prev_point(point)
        for label in point.vars:
            if label == self._timename:
                continue
            self._set_dependency(label, point, prev_point)

    def _set_dependency(self, var_label: str, point: Timepoint, prev_point: Timepoint) -> None:
        b = self._bindings[var_label]
        if self.timename in b.inputs and point == self._init_point:
            return
        x = self._collect_inputs(point, prev_point, b)
        y = point.var(b.output)
        if y.dependent:
            y.break_dependency()
        y.add_dependency(b.func, *x)

    def _collect_inputs(
        self, point: Timepoint, prev_point: Timepoint, binding: Binding
    ) -> list[AbstractAttribute]:
        inputs: list[AbstractAttribute] = list()
        for f in binding.inputs:
            if f[0] == "[" and f[-1] == "]":
                f_label, f_type = self._extract_item_variable_label_and_type(f)
                inputs.append(point._get_item_var_list(f_label, f_type))
            elif f == binding.output:
                inputs.append(prev_point.dep_var(f))
            else:
                inputs.append(point.dep_var(f))
        return inputs

    def _create_vars(self) -> dict[str, Attribute]:
        vars: dict[str, Attribute] = {}
        var_info = self.var_info
        for label, info in var_info.items():
            vars[label] = self.attrfac.new_from_dict(**info, name=label)
        return vars

    @staticmethod
    def _extract_item_variable_label_and_type(text: str) -> tuple[str, str]:
        if ":" not in text:
            raise Timeline.MissingItemVariableType(text)
        f_label, f_type = text[1:-1].split(":")
        if f_label.strip() == "":
            raise Timeline.MissingItemVariableLabel(text)
        if f_type.strip() == "":
            raise Timeline.MissingItemVariableType(text)
        return f_label, f_type

    def _last_point_time(self, time: Any) -> Any:
        time_index = _index_of_nearest_smaller_or_equal(time, self._time)
        if time_index < 0:
            return None
        else:
            return self._time[time_index]

    def __call__(self, variable_label: str, time: Any) -> Any:
        timepoint = self._pick_last_point(time)
        return timepoint(variable_label)

    class MissingItemVariableLabel(Exception):
        pass

    class MissingItemVariableType(Exception):
        pass

    class TimelikeVariableTypeConflict(Exception):
        pass

    class UndefinedVariable(Exception):
        pass


class Timepoint(abc.ABC):
    def __init__(self, vars: dict[str, Attribute], timeline: Timeline) -> None:
        self._items: set[Item] = set()
        self._vars = vars
        self._item_var_lists: dict[str, Attribute_List] = dict()
        self._timeline = timeline

    @property
    def vars(self) -> dict[str, Attribute]:
        return self._vars.copy()

    @property
    @abc.abstractmethod
    def time(self) -> Any:
        pass  # pragma: no cover

    @property
    def timeline(self) -> Timeline:
        return self._timeline

    def __call__(self, var_label: str) -> Any:
        return self._vars[var_label].value

    def has_items(self) -> bool:
        return bool(self._items)

    def var(self, label: str) -> Attribute:
        return self._vars[label]

    def _get_item_var_list(self, label: str, var_type: AttributeType) -> Attribute_List:
        if label not in self._item_var_lists:
            self._add_var_list(label, self._timeline.attrfac.newlist(var_type, name=var_type))
            for item in self._items:
                self._item_var_lists[label].append(item.attribute(label))
        return self._item_var_lists[label]

    def _add_var_list(self, label: str, varlist: Attribute_List) -> None:
        self._item_var_lists[label] = varlist

    @abc.abstractmethod
    def dep_var(self, label: str) -> Attribute:
        pass  # pragma: no cover

    @abc.abstractmethod
    def _add_item(self, item: Item) -> None:
        pass  # pragma: no cover

    @abc.abstractmethod
    def _remove_item(self, item: Item) -> None:
        pass  # pragma: no cover

    @abc.abstractmethod
    def is_init(self) -> bool:
        pass  # pragma: no cover


@dataclasses.dataclass
class Moving_In_Time_Data:
    timeline: Timeline
    tpoint: TimepointRegular
    item: Item


@dataclasses.dataclass
class Move_Item_In_Time(Command):
    data: Moving_In_Time_Data
    prev_time: Any = dataclasses.field(init=False)
    new_time: Any = dataclasses.field(init=False)

    def run(self) -> None:
        self.prev_time = self.data.tpoint.time
        self.new_time = self.data.item(self.data.timeline.timename)
        self.data.timeline._remove_item_from_timeline(self.data.item, self.prev_time)
        self.data.timeline._add_item_to_timeline(self.data.item, self.new_time)

    def undo(self) -> None:
        self.data.timeline._remove_item_from_timeline(self.data.item, self.new_time)
        self.data.timeline._add_item_to_timeline(self.data.item, self.prev_time)

    def redo(self) -> None:
        self.data.timeline._remove_item_from_timeline(self.data.item, self.prev_time)
        self.data.timeline._add_item_to_timeline(self.data.item, self.new_time)


class TimepointRegular(Timepoint):

    def __init__(self, vars: dict[str, Attribute], timeline: Timeline) -> None:
        super().__init__(vars, timeline)

    @property
    def time(self) -> Any:
        return self.vars[self.timeline.timename].value

    def dep_var(self, label: str) -> Attribute:
        return self.var(label)

    def _add_item(self, item: Item) -> None:
        self._items.add(item)
        for attr_label, attr in item.attributes.items():
            if attr_label in self._item_var_lists:
                self._item_var_lists[attr_label].append(attr)

        def move_in_time(*args) -> Command:
            return Move_Item_In_Time(Moving_In_Time_Data(self.timeline, self, item))

        item.attribute(self.timeline.timename).command["set"].add(
            "timeline", move_in_time, timing="post"
        )

    def _remove_item(self, item: Item) -> None:
        self._items.remove(item)
        for label in self._item_var_lists:
            if label in item.attributes:
                self._item_var_lists[label].remove(item.attribute(label))

    def is_init(self) -> bool:
        return False


class TimepointInit(Timepoint):

    def __init__(self, vars: dict[str, Attribute], timeline: Timeline) -> None:
        super().__init__(vars, timeline)
        self.__init_vars: dict[str, Attribute] = {label: var.copy() for label, var in vars.items()}

    @property
    def time(self) -> Any:
        return None

    def _add_item(self, item: Item) -> None:
        raise TimepointInit.CannotAddItem

    def _remove_item(self, item: Item) -> None:
        raise TimepointInit.No_Items_At_Init_Timepoint

    def is_init(self) -> bool:
        return True

    def dep_var(self, label: str) -> Attribute:
        return self.__init_vars[label]

    def init_var(self, label: str) -> Attribute:
        return self.__init_vars[label]

    class CannotAddItem(Exception):
        pass

    class No_Items_At_Init_Timepoint(Exception):
        pass


class Planner:

    def __init__(self, get_current_time: Callable[[], Any]) -> None:
        self.__planned: list[Event] = list()
        self.__now = get_current_time

    @property
    def planned(self) -> list[Any]:
        return self.__planned

    @property
    def to_be_confirmed(self) -> list[Any]:
        tbc: list[Event] = list()
        for e in self.__planned:
            if e.time <= self.__now():
                tbc.append(e)
        return tbc

    def confirm(self, event: Event) -> None:
        if event not in self.__planned:
            raise Planner.EventNotPlanned(event)
        elif event.time <= self.__now():
            self.__planned.remove(event)
            if event.on_confirmation is not None:
                event.on_confirmation()
        else:
            raise Planner.CannotConfirmFutureEvent(f"Event '{event}' at time '{event.time}'")

    def dismiss(self, event: Event) -> None:
        if event not in self.__planned:
            raise Planner.EventNotPlanned(event)
        else:
            self.__planned.remove(event)
            if event.on_dismissal is not None:
                event.on_dismissal()

    def pending_confirmation(self) -> bool:
        if not self.__planned:
            return False
        else:
            return self.__planned[0].time < self.__now()

    def new(
        self,
        time: Any,
        on_confirmation: Optional[Callable[[], None]] = None,
        on_dismissal: Optional[Callable[[], None]] = None,
    ) -> Event:

        event = Event(time, on_confirmation, on_dismissal)
        bisect.insort(self.__planned, event, key=lambda x: x.time)
        return event

    class CannotConfirmFutureEvent(Exception):
        pass

    class EventNotPlanned(Exception):
        pass


@dataclasses.dataclass(frozen=True)
class Event:
    time: Any
    on_confirmation: Optional[Callable[[], None]] = None
    on_dismissal: Optional[Callable[[], None]] = None


def _index_of_nearest_smaller(x: Any, thelist: list[Any], start: int = 0) -> int:
    if not thelist:
        return -1
    elif x <= thelist[0]:
        return -1 + start
    elif x > thelist[-1]:
        return len(thelist) - 1 + start
    else:
        m = int((len(thelist) + 1) / 2)
        if x == thelist[m]:
            return m - 1 + start
        elif x > thelist[m]:
            return _index_of_nearest_smaller(x, thelist[m:], m)
        else:
            return _index_of_nearest_smaller(x, thelist[:m], start)


def _index_of_nearest_smaller_or_equal(x: Any, thelist: list[Any], start: int = 0) -> int:
    if not thelist:
        return -1
    elif x == thelist[0]:
        return start
    elif x < thelist[0]:
        return -1 + start
    elif x > thelist[-1]:
        return len(thelist) - 1 + start
    else:
        m = int((len(thelist) + 1) / 2)
        if x == thelist[m]:
            return m + start
        elif x > thelist[m]:
            return _index_of_nearest_smaller_or_equal(x, thelist[m:], m)
        else:
            return _index_of_nearest_smaller_or_equal(x, thelist[:m], start)


def insert_to_sorted_list(x: Any, thelist: list[Any]):
    insertion_index = _index_of_nearest_smaller(x, thelist) + 1
    if insertion_index >= len(thelist):
        thelist.append(x)
    elif not x == thelist[insertion_index]:
        thelist.insert(insertion_index, x)
