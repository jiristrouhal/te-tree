from __future__ import annotations

import dataclasses
from typing import Dict, Any, Callable

from te_tree.core.item import Item, Parentage_Data
from te_tree.cmd.commands import Command
from te_tree.core.attributes import (
    Attribute,
    Attribute_Factory,
    Attribute_List,
    AbstractAttribute,
)


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


from typing import Tuple, List


@dataclasses.dataclass(frozen=True)
class Binding:
    output: str
    func: Callable[[Any], Any]
    inputs: Tuple[str, ...]


from te_tree.core.attributes import AttributeType


class Timeline:

    def __init__(
        self,
        root: Item,
        attribute_factory: Attribute_Factory,
        timelike_var_label: str,
        timelike_var_type: AttributeType,
        tvars: Dict[str, Dict[str, Any]] | None = None,
    ) -> None:

        if tvars is None:
            tvars = {}

        self.__timename = timelike_var_label
        self.__time_type = timelike_var_type
        self.__id = str(id(self))

        self.__points: Dict[Any, TimepointRegular] = {}
        self.__time: List[Any] = list()
        self.__vars: Dict[str, Dict[str, Any]] = tvars

        self.__bindings: Dict[str, Binding] = dict()
        for label in self.__vars:
            self.__bindings[label] = Binding(label, lambda x: x, (label,))

        self.__attribute_factory = attribute_factory

        self.__init_point = TimepointInit(self.__create_vars(), self)
        self.__update_dependencies(self.__init_point)

        self._add_item_tree_to_timeline(root)

    @property
    def points(self) -> Dict[Any, TimepointRegular]:
        return self.__points.copy()

    @property
    def var_info(self) -> Dict[str, Dict[str, Any]]:
        return self.__vars.copy()

    @property
    def attrfac(self) -> Attribute_Factory:
        return self.__attribute_factory

    @property
    def timename(self) -> str:
        return self.__timename

    def bind(self, dependent: str, func: Callable[[Any], Any], *free: str) -> None:
        if dependent not in self.__vars:
            raise Timeline.UndefinedVariable(dependent)
        self.__bindings[dependent] = Binding(dependent, func, free)
        self.__set_dependency(dependent, self.__init_point, self.__init_point)
        prev_point: Timepoint = self.__init_point
        for time in self.__time:
            point = self.__points[time]
            self.__set_dependency(dependent, point, prev_point)
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
        self.__init_point.init_var(var_label).set(value)

    def _add_item_tree_to_timeline(self, item: Item) -> None:
        self.__set_up_hierarchy_edit_commands(item)
        if self.__has_time(item):
            self._add_item_to_timeline(item, item(self.timename))
        for child in item.children:
            self._add_item_tree_to_timeline(child)

    def _add_item_to_timeline(self, item: Item, time: Any) -> None:
        if time not in self.__points:
            point = self._create_point(time)
        else:
            point = self.__points[time]
        point._add_item(item)

    def _create_point(self, time: Any) -> TimepointRegular:
        point = self.__new_point(time)
        self.__update_dependencies(point)
        next_point = self.next_point(point)
        if next_point is not None:
            self.__update_dependencies(next_point)
        return point

    def _pick_last_point(self, time: Any) -> Timepoint:
        last_point_time = self.__last_point_time(time)
        if last_point_time is None:
            return self.__init_point
        else:
            return self.__points[last_point_time]

    def _remove_item_tree(self, item: Item) -> None:
        for child in item.children:
            self._remove_item_tree(child)
        if self.__has_time(item):
            self._remove_item_from_timeline(item, item(self.timename))
        self.__clean_up_hierarchy_edit_commands(item)

    def _remove_item_from_timeline(self, item: Item, time: Any) -> None:
        point = self.__points[time]
        point._remove_item(item)
        if not point.has_items():
            self._remove_point(point)

    def _remove_point(self, point: TimepointRegular) -> None:
        next_point = self.next_point(point)
        self.__points.pop(point.time)
        self.__time.remove(point.time)
        if next_point is not None:
            self.__update_dependencies(next_point)

    def __new_point(self, time: Any) -> TimepointRegular:
        vars = self.__create_vars()
        vars[self.__timename] = self.attrfac.new(self.__time_type, time, self.timename)
        insert_to_sorted_list(time, self.__time)
        self.__points[time] = TimepointRegular(vars, self)
        return self.__points[time]

    def prev_point(self, point: Timepoint) -> Timepoint:
        if point is self.__init_point:
            return self.__init_point
        point_time = point.time
        i = self.__time.index(point_time)
        if i == 0:
            return self.__init_point
        else:
            return self.__points[self.__time[i - 1]]

    def next_point(self, point: Timepoint) -> Timepoint | None:
        if point == self.__init_point and self.__points:
            return self.__points[self.__time[0]]
        i = self.__time.index(point.time)
        if i < len(self.__time) - 1:
            return self.__points[self.__time[i + 1]]
        else:
            return None

    def __has_time(self, item: Item) -> bool:
        if not item.has_attribute(self.__timename):
            return False
        elif item.attribute(self.__timename).type != self.__time_type:
            raise Timeline.TimelikeVariableTypeConflict(
                f"Trying to add '{item.attribute('seconds').type}'"
                f"instead of '{self.__time_type}'."
            )
        return True

    def __clean_up_hierarchy_edit_commands(self, item: Item) -> None:
        item.command["adopt"].post.pop(self.__id)
        item.command["leave"].pre.pop(self.__id)

    def __set_up_hierarchy_edit_commands(self, item: Item) -> None:
        def __adopt(data: Parentage_Data):
            return Add_Item(Timepoint_Data(self, data.child))

        def __leave(data: Parentage_Data):
            return Remove_Item(Timepoint_Data(self, data.child))

        item.command["adopt"].add(self.__id, __adopt, "post")
        item.command["leave"].add(self.__id, __leave, "pre")

    def __update_dependencies(self, point: Timepoint) -> None:
        prev_point = self.prev_point(point)
        for label in point.vars:
            if label == self.__timename:
                continue
            self.__set_dependency(label, point, prev_point)

    def __set_dependency(self, var_label: str, point: Timepoint, prev_point: Timepoint) -> None:
        b = self.__bindings[var_label]
        if self.timename in b.inputs and point == self.__init_point:
            return
        x = self.__collect_inputs(point, prev_point, b)
        y = point.var(b.output)
        if y.dependent:
            y.break_dependency()
        y.add_dependency(b.func, *x)

    def __collect_inputs(
        self, point: Timepoint, prev_point: Timepoint, binding: Binding
    ) -> List[AbstractAttribute]:
        inputs: List[AbstractAttribute] = list()
        for f in binding.inputs:
            if f[0] == "[" and f[-1] == "]":
                f_label, f_type = self.__extract_item_variable_label_and_type(f)
                inputs.append(point._get_item_var_list(f_label, f_type))
            elif f == binding.output:
                inputs.append(prev_point.dep_var(f))
            else:
                inputs.append(point.dep_var(f))
        return inputs

    def __create_vars(self) -> Dict[str, Attribute]:
        vars: Dict[str, Attribute] = {}
        var_info = self.var_info
        for label, info in var_info.items():
            vars[label] = self.attrfac.new_from_dict(**info, name=label)
        return vars

    @staticmethod
    def __extract_item_variable_label_and_type(text: str) -> Tuple[str, str]:
        if ":" not in text:
            raise Timeline.MissingItemVariableType(text)
        f_label, f_type = text[1:-1].split(":")
        if f_label.strip() == "":
            raise Timeline.MissingItemVariableLabel(text)
        if f_type.strip() == "":
            raise Timeline.MissingItemVariableType(text)
        return f_label, f_type

    def __last_point_time(self, time: Any) -> Any:
        time_index = _index_of_nearest_smaller_or_equal(time, self.__time)
        if time_index < 0:
            return None
        else:
            return self.__time[time_index]

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


from typing import Set
import abc


class Timepoint(abc.ABC):
    def __init__(self, vars: Dict[str, Attribute], timeline: Timeline) -> None:
        self._items: Set[Item] = set()
        self.__vars = vars
        self._item_var_lists: Dict[str, Attribute_List] = dict()
        self.__timeline = timeline

    @property
    def vars(self) -> Dict[str, Attribute]:
        return self.__vars.copy()

    @abc.abstractproperty
    def time(self) -> Any:
        pass  # pragma: no cover

    @property
    def timeline(self) -> Timeline:
        return self.__timeline

    def __call__(self, var_label: str) -> Any:
        return self.__vars[var_label].value

    def has_items(self) -> bool:
        return bool(self._items)

    def var(self, label: str) -> Attribute:
        return self.__vars[label]

    def _get_item_var_list(self, label: str, var_type: AttributeType) -> Attribute_List:
        if label not in self._item_var_lists:
            self._add_var_list(label, self.__timeline.attrfac.newlist(var_type, name=var_type))
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

    def __init__(self, vars: Dict[str, Attribute], timeline: Timeline) -> None:
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

    def __init__(self, vars: Dict[str, Attribute], timeline: Timeline) -> None:
        super().__init__(vars, timeline)
        self.__init_vars: Dict[str, Attribute] = {label: var.copy() for label, var in vars.items()}

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


import bisect
from typing import Optional


class Planner:

    def __init__(self, get_current_time: Callable[[], Any]) -> None:
        self.__planned: List[Event] = list()
        self.__now = get_current_time

    @property
    def planned(self) -> List[Any]:
        return self.__planned

    @property
    def to_be_confirmed(self) -> List[Any]:
        tbc: List[Event] = list()
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


def _index_of_nearest_smaller(x: Any, thelist: List[Any], start: int = 0) -> int:
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


def _index_of_nearest_smaller_or_equal(x: Any, thelist: List[Any], start: int = 0) -> int:
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


def insert_to_sorted_list(x: Any, thelist: List[Any]):
    insertion_index = _index_of_nearest_smaller(x, thelist) + 1
    if insertion_index >= len(thelist):
        thelist.append(x)
    elif not x == thelist[insertion_index]:
        thelist.insert(insertion_index, x)
