from __future__ import annotations
from typing import Dict, Any, Set, Callable, Optional, Literal, List
import dataclasses

import shutil
import time

from te_tree.cmd.commands import (
    Command,
    Controller,
    Composed_Command,
    Timing,
    Empty_Command,
)
from te_tree.utils.naming import adjust_taken_name, strip_and_join_spaces
from te_tree.core.attributes import (
    attribute_factory,
    Attribute,
    Attribute_List,
    Set_Attr_Data,
    Attribute_Data_Constructor,
)
from te_tree.core.attributes import Edit_AttrList_Data
from te_tree.core.attributes import NBSP
import abc


def freeatt(label: str) -> Template.FreeAttribute:
    return Template.FreeAttribute(label, {}, owner="self")


def freeatt_parent(label: str, info: Dict[str, Any]) -> Template.FreeAttribute:
    return Template.FreeAttribute(label, info, owner="parent")


def freeatt_child(label: str, info: Dict[str, Any]) -> Template.FreeAttribute:
    return Template.FreeAttribute(label, info, owner="child")


@dataclasses.dataclass(frozen=True)
class Template:
    label: str
    attribute_info: Dict[str, Dict[str, Any]]
    child_itypes: Tuple[str, ...] = ()
    dependencies: Optional[List[Template.Dependency]] = None

    @staticmethod
    def dependency(
        dependent: str,
        func: Callable[[Any], Any],
        *free: FreeAttribute,
        label: str = "",
    ) -> Dependency:
        return Template.Dependency(dependent, func, free, label=label)

    @dataclasses.dataclass(frozen=True)
    class Dependency:
        dependent: str
        func: Callable[[Any], Any]
        free: Tuple[Template.FreeAttribute, ...]
        label: str = ""

    AttributeOwner = Literal["parent", "child", "self"]

    @dataclasses.dataclass(frozen=True)
    class FreeAttribute:
        label: str
        info: Dict[str, Any]
        owner: Template.AttributeOwner


FileType = Literal["xml"]
from te_tree.core.attributes import Locale_Code, AttributeType, Currency_Code


class ItemCreator:

    def __init__(
        self,
        locale_code: Locale_Code = "en_us",
        currency_code: Currency_Code = "USD",
        ignore_duplicit_names: bool = False,
    ) -> None:
        self._controller = Controller()
        self._attrfac = attribute_factory(self._controller, locale_code, currency_code)
        self.__templates: Dict[str, Template] = {}
        self.__file_path: str = "."
        self.__ignore_duplicit_names = ignore_duplicit_names

    @property
    def templates(self) -> Tuple[str, ...]:
        return tuple(self.__templates.keys())

    def get_template(self, label: str) -> Template:
        return self.__templates[label]

    def template(
        self,
        label: str,
        attributes: Dict[str, Dict[str, Any]] | None = None,
        child_itypes: Tuple[str, ...] = (),
        dependencies: Optional[List[Template.Dependency]] = None,
    ) -> Template:

        if attributes is None:
            attributes = {}
        return Template(label, attributes, child_itypes, dependencies)

    def dependency(
        self,
        dependent: str,
        func: Callable[[Any], Any],
        *free: Template.FreeAttribute,
        label: str = "",
    ) -> Template.Dependency:

        return Template.dependency(dependent, func, *free, label=label)

    @property
    def attr(self) -> Attribute_Data_Constructor:
        return self._attrfac.data_constructor

    @property
    def file_path(self) -> str:
        return self.__file_path

    def add_templates(self, *templates: Template) -> None:
        new_labels = [t.label for t in templates]
        for t in templates:
            if t.label in self.__templates:
                raise ItemCreator.TemplateAlreadyExists(t.label)
            self.__check_child_template_presence(t.child_itypes, *new_labels)
            self.__check_attribute_info(t.attribute_info)
        self.__templates.update({t.label: t for t in templates})

    def add_template(
        self,
        label: str,
        attributes: Dict[str, Dict[str, Any]] | None = None,
        child_itypes: Tuple[str, ...] = (),
        dependencies: Optional[List[Template.Dependency]] = None,
    ) -> None:

        if attributes is None:
            attributes = {}
        self.add_templates(Template(label, attributes, child_itypes, dependencies))

    import xml.etree.ElementTree as et
    import os

    def load(self, dirpath: str, name: str, ftype: FileType) -> Item:
        filepath = self.__create_and_check_filepath(dirpath, name, ftype)
        root_elem = self.et.parse(filepath).getroot()
        loaded_item = self.__build_item_from_xml(root_elem)
        return loaded_item

    def __build_item_from_xml(self, xml_elem: et.Element) -> Tuple[Item, List[Command]]:
        self.__check_template_is_available(xml_elem.tag)
        item = self.from_template(xml_elem.tag)
        item.rename(xml_elem.attrib["name"])
        self.__read_attribute_values_from_xml_elem(item, xml_elem)

        @self._controller.single_cmd()
        def build_and_adopt():
            child = self.__build_item_from_xml(sub_elem)
            item.adopt(child)

        for sub_elem in xml_elem:
            build_and_adopt()
        return item

    def __create_and_check_filepath(self, dirpath: str, name: str, ftype: FileType) -> str:
        filepath = dirpath + "/" + name + "." + ftype
        if self.os.path.isfile(filepath):
            return filepath
        else:
            raise ItemCreator.FileDoesNotExist(filepath)

    def __check_template_is_available(self, label: str) -> None:
        if label not in self.__templates:
            raise ItemCreator.UnknownTemplate(label)

    def __read_attribute_values_from_xml_elem(
        self, loaded_item: Item, xml_elem: et.Element
    ) -> None:
        for attr_name in loaded_item.attributes:
            if attr_name in xml_elem.attrib:
                loaded_item.attributes[attr_name].read(
                    xml_elem.attrib[attr_name], overwrite_dependent=True
                )

    def save(self, item: Item, filetype: FileType, backup_folder_name: str = "") -> None:
        xml_tree = self.et.ElementTree(self.__create_xml_items_hierarchy(item))
        self.et.indent(xml_tree, space="\t")
        filename = item.name + "." + filetype
        filepath = self.os.path.join(self.file_path, filename)
        if backup_folder_name.strip() == "":
            backup_folder_name = "backup"
        if self.does_file_exist(item, filetype):
            backup_folder_path = self.os.path.join(self.file_path, backup_folder_name, item.name)
            if not self.os.path.isdir(backup_folder_path):
                self.os.makedirs(backup_folder_path)
            shutil.copyfile(
                filepath,
                self.os.path.join(backup_folder_path, self.__backup_file_name(item, filetype)),
            )
        xml_tree.write(filepath, encoding="UTF-8")

    @staticmethod
    def get_strtime(curr_seconds: Optional[float] = None) -> str:
        if curr_seconds is None:
            t = time.localtime()
        else:
            t = time.localtime(curr_seconds)
        strtime = f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:2d}_{t.tm_hour:02d}-{t.tm_min:02d}-{t.tm_sec:02d}"
        return strtime

    def __backup_file_name(self, item: Item, filetype: FileType) -> str:
        return item.name + " " + self.get_strtime() + "." + filetype

    def does_file_exist(self, item: Item, filetype: FileType) -> bool:
        filepath = self.file_path + "/" + item.name + "." + filetype
        return self.os.path.isfile(filepath)

    def set_dir_path(self, path: str) -> None:
        if not self.os.path.isdir(path):
            raise ItemCreator.NonexistentDirectory(path)
        self.__file_path = path

    def __check_template_exists_for_item(self, item: Item) -> None:
        if item.itype.strip() == "" or item.itype not in self.__templates:
            raise ItemCreator.NoTemplateIsAssigned(item.name)

    def __create_xml_items_hierarchy(self, item: Item) -> et.Element:
        xml_elem = self.__create_single_xml_item(item)
        for child in set.union(item.children, item.formal_children):
            xml_elem.append(self.__create_xml_items_hierarchy(child))
        return xml_elem

    def __create_single_xml_item(self, item: Item) -> et.Element:
        self.__check_template_exists_for_item(item)
        return self.et.Element(item.itype, self.__get_printed_attributes(item))

    def __get_printed_attributes(self, item: Item) -> Dict[str, str]:
        printed_attribs: Dict[str, str] = {"name": item.name}
        for label, attr in item.attributes.items():
            printed_attribs[label] = attr.print().replace(NBSP, " ")
        return printed_attribs

    def from_template(self, label: str, name: str = "") -> Item:
        if label not in self.__templates:
            raise ItemCreator.UndefinedTemplate(label)
        template = self.__templates[label]
        attributes = self.__get_attrs(template.attribute_info)
        if name.strip() == "":
            name = template.label
        item = ItemImpl(
            name,
            attributes,
            self,
            itype=template.label,
            child_itypes=template.child_itypes,
            ignore_duplicit_names=self.__ignore_duplicit_names,
        )
        if template.dependencies is not None:
            for dep in template.dependencies:
                item.bind(dep.dependent, dep.func, *dep.free, binding_label=dep.label)
        return item

    def new(
        self,
        name: str,
        attr_info: Dict[str, AttributeType | Dict[str, Any]] = {},
        child_itypes: Optional[Tuple[str, ...]] = None,
    ) -> Item:
        return ItemImpl(
            name,
            self.__get_attrs(attr_info),
            self,
            ignore_duplicit_names=self.__ignore_duplicit_names,
            child_itypes=child_itypes,
        )

    def undo(self):
        self._controller.undo()

    def redo(self):
        self._controller.redo()

    def __check_attribute_info(self, attribute_info: Dict[str, Dict[str, Any]]) -> None:
        for info in attribute_info.values():
            self.attr._check(info)

    def __check_child_template_presence(
        self, child_itypes: Tuple[str, ...], *templates_being_defined: str
    ) -> None:
        for child_itype in child_itypes:
            if not (child_itype in self.__templates or child_itype in templates_being_defined):
                raise ItemCreator.UndefinedTemplate(child_itype)

    def __get_attrs(
        self, attribute_info: Dict[str, AttributeType | Dict[str, Any]]
    ) -> Dict[str, Attribute]:
        attributes = {}
        for label, info in attribute_info.items():
            if isinstance(info, str):
                attributes[label] = self._attrfac.new(name=label, atype=info)
            elif isinstance(info, dict):
                attributes[label] = self._attrfac.new_from_dict(name=label, **info)
            else:
                raise TypeError(
                    f"Invalid type {type(info)} of attribute info for attribute construction. Expected 'str' or 'dict'."
                )
        return attributes

    class NonexistentDirectory(Exception):
        pass

    class FileDoesNotExist(Exception):
        pass

    class NoTemplateIsAssigned(Exception):
        pass

    class TemplateAlreadyExists(Exception):
        pass

    class UndefinedTemplate(Exception):
        pass

    class UnknownTemplate(Exception):
        pass


@dataclasses.dataclass
class Renaming_Data:
    item: Item
    new_name: str


@dataclasses.dataclass
class Parentage_Data:
    parent: Item
    child: Item


@dataclasses.dataclass
class Rename(Command):
    data: Renaming_Data
    original_name: str = dataclasses.field(init=False)

    def run(self):
        self.original_name = self.data.item.name
        self.data.item._rename(self.data.new_name)

    def undo(self):
        self.data.item._rename(self.original_name)

    def redo(self) -> None:
        self.data.item._rename(self.data.new_name)

    @property
    def message(self) -> str:
        return f"Rename | '{self.original_name}' renamed to '{self.data.new_name}'."


class Rename_Composed(Composed_Command):
    @staticmethod
    def cmd_type():
        return Rename

    def __call__(self, data: Renaming_Data):
        return super().__call__(data)

    def add(self, owner_id: str, func: Callable[[Renaming_Data], Command], timing: Timing) -> None:
        super().add(owner_id, creator=func, timing=timing)

    def add_composed(
        self,
        owner_id: str,
        data_converter: Callable[[Renaming_Data], Any],
        cmd: Composed_Command,
        timing: Timing,
    ) -> None:  # pragma: no cover

        return super().add_composed(owner_id, data_converter, cmd, timing)


@dataclasses.dataclass
class Adopt(Command):
    data: Parentage_Data
    old_name: str = dataclasses.field(init=False)

    def run(self):
        self.old_name = self.data.child.name
        self.data.parent._adopt(self.data.child)

    def undo(self):
        self.data.child._leave_parent(self.data.parent)
        self.data.child._rename(self.old_name)

    def redo(self):
        self.data.parent._adopt(self.data.child)

    @property
    def message(self) -> str:
        return f"Adopt child | '{self.data.parent.name}' adopts '{self.data.child.name}'."


class Adopt_Composed(Composed_Command):
    @staticmethod
    def cmd_type():
        return Adopt

    def __call__(self, data: Parentage_Data) -> Tuple[Command, ...]:
        return super().__call__(data)

    def add(self, owner_id: str, func: Callable[[Parentage_Data], Command], timing: Timing) -> None:
        super().add(owner_id, creator=func, timing=timing)

    def add_composed(
        self,
        owner_id: str,
        data_converter: Callable[[Parentage_Data], Any],
        cmd: Composed_Command,
        timing: Timing,
    ) -> None:  # pragma: no cover

        return super().add_composed(owner_id, data_converter, cmd, timing)


@dataclasses.dataclass
class Leave(Command):
    data: Parentage_Data

    def run(self):
        self.data.parent._leave_child(self.data.child)

    def undo(self):
        self.data.parent._adopt(self.data.child)

    def redo(self):
        self.data.parent._leave_child(self.data.child)

    @property
    def message(self) -> str:
        return f"Leave child | '{self.data.parent.name}' leaves '{self.data.child.name}'."


class Leave_Composed(Composed_Command):
    @staticmethod
    def cmd_type():
        return Leave

    def __call__(self, data: Parentage_Data) -> Tuple[Command, ...]:
        return super().__call__(data)

    def add(
        self,
        owner_id: str,
        creator: Callable[[Parentage_Data], Command],
        timing: Timing,
    ) -> None:
        return super().add(owner_id, creator, timing)

    def add_composed(
        self,
        owner_id: str,
        data_converter: Callable[[Parentage_Data], Any],
        cmd: Composed_Command,
        timing: Timing,
    ) -> None:  # pragma: no cover

        return super().add_composed(owner_id, data_converter, cmd, timing)


from te_tree.core.attributes import Dependency


class Parent_Attribute:

    def __init__(self, attribute: AbstractAttribute, stub: AbstractAttribute) -> None:
        self.__dependencies: List[Dependency] = list()
        self.__attribute = attribute
        self.__stub = stub

    @property
    def attr(self) -> AbstractAttribute:
        return self.__attribute

    @property
    def stub(self) -> AbstractAttribute:
        return self.__stub

    def watch_dependency(self, dependency: Dependency) -> None:
        if dependency not in self.__dependencies:
            self.__dependencies.append(dependency)

    def set(self, attribute: AbstractAttribute) -> None:
        for dep in self.__dependencies:
            dep.replace_input(self.__attribute, attribute)
        self.__attribute = attribute


from typing import Literal

Command_Type = Literal["adopt", "leave", "rename"]


class Item(abc.ABC):  # pragma: no cover

    @dataclasses.dataclass(frozen=True)
    class BindingInfo:
        func: Callable[[Any], Any]
        input_labels: Tuple[Template.FreeAttribute, ...]
        label: str = ""

    def __init__(
        self,
        name: str,
        attributes: Dict[str, Attribute],
        manager: ItemCreator,
        ignore_duplicit_names: bool = False,
    ) -> None:
        self._manager = manager
        self.__id = str(id(self))
        self._bindings: Dict[str, Item.BindingInfo] = dict()
        self._child_attr_lists: Dict[str, Attribute_List] = dict()
        self._parent_attributes: Dict[str, Parent_Attribute] = dict()

    @abc.abstractproperty
    def attributes(self) -> Dict[str, Attribute]:
        pass

    @abc.abstractproperty
    def name(self) -> str:
        pass

    @abc.abstractproperty
    def parent(self) -> Item:
        pass

    @abc.abstractproperty
    def root(self) -> Item:
        pass

    @abc.abstractproperty
    def children(self) -> Set[Item]:
        pass

    @property
    def controller(self) -> Controller:
        return self._manager._controller

    @property
    def id(self) -> str:
        return self.__id

    @property
    def itype(self) -> str:
        return ""

    @abc.abstractproperty
    def child_itypes(self) -> Optional[Tuple[str, ...]]:
        pass

    @abc.abstractproperty
    def command(self) -> Dict[Command_Type, Composed_Command]:
        pass

    @abc.abstractproperty
    def formal_children(self) -> Set[Item]:
        pass

    @abc.abstractproperty
    def last_action(self) -> Tuple[str, str, str]:
        pass

    @abc.abstractmethod
    def adopt_formally(self, child: Item) -> None:
        pass

    @abc.abstractmethod
    def leave_formal_child(self, child: Item) -> None:
        pass

    @abc.abstractmethod
    def bind(
        self,
        output_name: str,
        func: Callable[[Any], Any],
        *input_names: Template.FreeAttribute,
    ) -> None:
        pass

    @abc.abstractmethod
    def add_action(
        self, owner_id: str, after_command: Command_Type, action: Callable[[Item], None]
    ) -> None:
        pass

    @abc.abstractmethod
    def add_action_on_set(self, owner_id: str, action: Callable[[Item], None]) -> None:
        pass

    @abc.abstractmethod
    def remove_action(self, owner_id: str, after_command: Command_Type) -> None:
        pass

    @abc.abstractmethod
    def remove_action_on_set(self, owner_id: str) -> None:
        pass

    @abc.abstractmethod
    def adopt(self, child: Item) -> None:
        pass

    @abc.abstractmethod
    def attribute(self, label: str) -> Attribute:
        pass

    @abc.abstractmethod
    def copy(self) -> Item:
        pass

    @abc.abstractmethod
    def free(self, output_name: str) -> None:
        pass

    @abc.abstractmethod
    def has_attribute(self, label: str) -> bool:
        pass

    @abc.abstractmethod
    def on_adoption(
        self, owner: str, func: Callable[[Parentage_Data], Command], timing: Timing
    ) -> None:
        pass

    @abc.abstractmethod
    def on_leaving(
        self, owner: str, func: Callable[[Parentage_Data], Command], timing: Timing
    ) -> None:
        pass

    @abc.abstractmethod
    def on_renaming(
        self, owner: str, func: Callable[[Renaming_Data], Command], timing: Timing
    ) -> None:
        pass

    @abc.abstractmethod
    def _create_child_attr_list(self, value_type: AttributeType, child_attr_label: str) -> None:
        pass

    @abc.abstractmethod
    def duplicate(self) -> Item:
        pass

    @abc.abstractmethod
    def has_children(self) -> bool:
        pass

    @abc.abstractmethod
    def is_null(self) -> bool:
        pass

    @abc.abstractmethod
    def is_parent_of(self, child: Item) -> bool:
        pass

    @abc.abstractmethod
    def is_ancestor_of(self, child: Item) -> bool:
        pass

    @abc.abstractmethod
    def leave(self, child: Item) -> None:
        pass

    @abc.abstractmethod
    def pass_to_new_parent(self, child: Item, new_parent: Item) -> None:
        pass

    @abc.abstractmethod
    def pick_child(self, name: str) -> Item:
        pass

    @abc.abstractmethod
    def rename(self, name: str) -> None:
        pass

    @abc.abstractmethod
    def set(self, attribute_name: str, value: Any) -> None:
        pass

    @abc.abstractmethod
    def multiset(self, vals_to_labels: Dict[str, Any]) -> None:
        pass

    @abc.abstractmethod
    def _set_parent_attributes(self, parent: Item) -> None:
        pass

    @abc.abstractmethod
    def __call__(self, attr_name: str) -> Any:
        pass

    @abc.abstractmethod
    def _adopt(self, child: Item) -> None:
        pass

    @abc.abstractmethod
    def _accept_parent(self, item: Item) -> None:
        pass

    @abc.abstractmethod
    def _apply_binding_info(self) -> None:
        pass

    @abc.abstractmethod
    def _can_be_parent_of_item_type(self, item: Item) -> bool:
        pass

    @abc.abstractmethod
    def _copy_bindings(self, dupl: Item) -> None:
        pass

    @abc.abstractmethod
    def _check_can_be_parent_of(self, item: Item) -> bool:
        pass

    @abc.abstractmethod
    def _leave_child(self, child: Item) -> None:
        pass

    @abc.abstractmethod
    def _leave_parent(self, parent: Item) -> None:
        pass

    @abc.abstractmethod
    def _rename(self, name: str) -> None:
        pass

    @abc.abstractmethod
    def _duplicate_items(self) -> Item:
        pass

    class AdoptionOfAncestor(Exception):
        pass

    class AdoptingNULL(Exception):
        pass

    class BlankName(Exception):
        pass

    class CannotAdoptItemOfType(Exception):
        pass

    class FormalChildNotFound(Exception):
        pass

    class ItemAdoptsItself(Exception):
        pass

    class NonexistentAttribute(Exception):
        pass

    class NonexistentCommandType(Exception):
        pass

    class NonexistentChildValueGroup(Exception):
        pass

    class Undefined_Action_Type(Exception):
        pass


from te_tree.core.attributes import (
    Append_To_Attribute_List,
    Remove_From_Attribute_List,
    AbstractAttribute,
)
from typing import Tuple, List, get_args


class ItemImpl(Item):

    class __ItemNull(Item):
        def __init__(self, *args, **kwargs) -> None:
            self.__children: Set[Item] = set()
            self._child_attr_lists: Dict = dict()

        @property
        def attributes(self) -> Dict[str, Attribute]:
            return {}

        @property
        def name(self) -> str:
            return "NULL"

        @property
        def parent(self) -> Item:
            return self

        @property
        def root(self) -> Item:
            return self

        @property
        def children(self) -> Set[Item]:
            raise self.CannotAccessChildrenOfNull

        @property
        def itype(self) -> str:
            return ""  # pragma: no cover

        @property
        def child_itypes(self) -> Optional[Tuple[str, ...]]:
            return None  # pragma: no cover

        @property
        def command(self) -> Dict[Command_Type, Composed_Command]:
            return {}  # pragma: no cover

        @property
        def formal_children(self) -> Set[Item]:
            return set()

        @property
        def last_action(self) -> Tuple[str, str, str]:
            return ("", "", "")

        def adopt_formally(self, child: Item) -> None:
            raise self.NullCannotAdoptFormally  # pragma: no cover

        def add_action(self, *args) -> None:
            pass

        def add_action_on_set(self, *args) -> None:
            pass

        def remove_action(self, *args) -> None:
            pass

        def remove_action_on_set(self, *args) -> None:
            pass

        def leave_formal_child(self, child: Item) -> None:
            raise Item.FormalChildNotFound(child)  # pragma: no cover

        def bind(self, *args) -> None:
            raise self.SettingDependencyOnNull

        def copy(self) -> Item:
            return self  # pragma: no cover

        def free(self, *args) -> None:
            raise self.SettingDependencyOnNull

        def adopt(self, child: Item) -> None:
            if child.parent is not self:
                child.parent.leave(child)

        def attribute(self, label: str) -> Attribute:
            raise Item.NonexistentAttribute  # pragma: no cover

        def has_attribute(self, label: str) -> bool:
            return False

        def on_adoption(self, *args) -> None:
            pass  # pragma: no cover

        def on_leaving(self, *args) -> None:
            pass  # pragma: no cover

        def on_renaming(self, *args) -> None:
            pass  # pragma: no cover

        def _create_child_attr_list(self, *args) -> None:
            raise self.AddingAttributeToNullItem

        def duplicate(self) -> ItemImpl.__ItemNull:
            return self

        def has_children(self) -> bool:
            return True

        def is_null(self) -> bool:
            return True  # pragma: no cover

        def is_parent_of(self, child: Item) -> bool:
            return child.parent is self

        def is_ancestor_of(self, child: Item) -> bool:
            return child == self

        def leave(self, child: Item) -> None:
            raise self.NullCannotLeaveChild

        def pass_to_new_parent(self, child: Item, new_parent: Item) -> None:
            new_parent.adopt(child)

        def pick_child(self, name: str) -> Item:
            raise self.CannotAccessChildrenOfNull

        def rename(self, name: str) -> None:
            return

        def set(self, attr_name: str, value: Any) -> None:
            raise Item.NonexistentAttribute  # pragma: no cover

        def multiset(self, vals_to_labels: Dict[str, Any]) -> None:
            raise Item.NonexistentAttribute  # pragma: no cover

        def __call__(self, attr_name: str) -> Any:
            raise Item.NonexistentAttribute  # pragma: no cover

        def _adopt(self, child: Item) -> None:
            return  # pragma: no cover

        def _accept_parent(self, item: Item) -> None:
            raise Item.AdoptingNULL

        def _apply_binding_info(self) -> None:
            pass  # pragma: no cover

        def _can_be_parent_of_item_type(self, item: Item) -> bool:
            return True  # pragma: no cover

        def _copy_bindings(self, dupl: Item) -> None:
            pass  # pragma: no cover

        def _check_can_be_parent_of(self, item: Item) -> bool:
            return True  # pragma: no cover

        def _leave_child(self, child: Item) -> None:
            return

        def _leave_parent(self, parent: Item) -> None:
            return

        def _rename(self, name: str) -> None:
            return

        def _duplicate_items(self) -> Item:
            return self  # pragma: no cover

        def _set_parent_attributes(self, parent: Item) -> None:
            pass  # pragma: no cover

        class AddingAttributeToNullItem(Exception):
            pass

        class CannotAccessChildrenOfNull(Exception):
            pass

        class NullCannotAdoptFormally(Exception):
            pass

        class NullCannotLeaveChild(Exception):
            pass

        class SettingDependencyOnNull(Exception):
            pass

    NULL = __ItemNull()

    def __init__(
        self,
        name: str,
        attributes: Dict[str, Attribute],
        manager: ItemCreator,
        itype: str = "",
        child_itypes: Optional[Tuple[str, ...]] = None,
        ignore_duplicit_names: bool = False,
    ) -> None:

        self.__ignore_duplicit_names: bool = ignore_duplicit_names
        super().__init__(name, attributes, manager)
        self.__attributes: Dict[str, Attribute] = {
            "name": manager._attrfac.new_from_dict(**manager.attr.text(init_value=itype))
        }
        if "name" in attributes:
            attributes.pop("name")
        self.__attributes.update(attributes)
        self.__children: Set[Item] = set()
        self.__formal_children: Set[Item] = set()
        self.__parent: Item = self.NULL
        self._bindings: Dict[str, Item.BindingInfo] = dict()
        self.__command: Dict[Command_Type, Composed_Command] = {
            "adopt": Adopt_Composed(),
            "leave": Leave_Composed(),
            "rename": Rename_Composed(),
        }
        self.__itype = itype
        self.__child_itypes = child_itypes
        self.__actions: Dict[Command_Type, Dict[str, Callable[[Item], None]]] = {
            "rename": dict(),
            "adopt": dict(),
            "leave": dict(),
        }
        self.__last_action: Tuple[str, str, str] = ("", "", "")
        self._rename(name)

    @property
    def attributes(self) -> Dict[str, Attribute]:
        attributes = self.__attributes.copy()
        attributes.pop("name")
        return attributes

    @property
    def name(self) -> str:
        return self.__attributes["name"].value

    @property
    def parent(self) -> Item:
        return self.__parent

    @property
    def root(self) -> Item:
        return self if self.__parent is self.NULL else self.__parent.root

    @property
    def children(self) -> Set[Item]:
        return self.__children.copy()

    @property
    def itype(self) -> str:
        return self.__itype

    @property
    def child_itypes(self) -> Optional[Tuple[str, ...]]:
        return self.__child_itypes

    @property
    def command(self) -> Dict[Command_Type, Composed_Command]:
        return self.__command

    @property
    def formal_children(self) -> Set[Item]:
        return self.__formal_children.copy()

    @property
    def id(self) -> str:
        return self.itype + " " + super().id

    @property
    def child_names(self) -> List[str]:
        return [c.name for c in self.__children]

    @property
    def last_action(self) -> Tuple[str, str, str]:
        return self.__last_action

    def add_action(
        self, owner_id: str, after_command: Command_Type, action: Callable[[Item], None]
    ) -> None:
        self.__actions[after_command][owner_id] = action

    def add_action_on_set(self, owner_id: str, action: Callable[[Item], None]) -> None:
        def attr_action() -> None:
            action(self)

        for attr in self.__attributes.values():
            attr.add_action_on_set(owner_id, attr_action)

    def remove_action(self, owner_id: str, after_command: Command_Type) -> None:
        if owner_id in self.__actions[after_command]:
            self.__actions[after_command].pop(owner_id)

    def remove_action_on_set(self, owner_id: str) -> None:
        for attr in self.__attributes.values():
            attr.remove_action_on_set(owner_id)

    def adopt_formally(self, child: Item) -> None:
        if child in self.__children:
            raise ItemImpl.AlreadyAChild(child)
        else:
            self.__formal_children.add(child)

    def leave_formal_child(self, child: Item) -> None:
        if child not in self.__formal_children:
            raise Item.FormalChildNotFound(child)
        else:
            self.__formal_children.remove(child)

    def attribute(self, label: str) -> Attribute:
        if not label in self.__attributes:
            raise Item.NonexistentAttribute(
                f"Item {self.name} of type {self.itype} has not attribute named {label}."
            )
        else:
            return self.__attributes[label]

    def bind(
        self,
        output_name: str,
        func: Callable[[Any], Any],
        *input_info: str | Template.FreeAttribute,
        binding_label: str = "",
    ) -> None:

        if not self.has_attribute(output_name):
            return
        output = self.attribute(output_name)
        input_info = list(input_info)
        self.__create_attr_info_from_attr_type(input_info)
        inputs = self.__collect_input_attributes(input_info)
        dependency = output.add_dependency(func, *inputs, label=binding_label)
        for info in input_info:
            label = info.label
            if info.owner == "parent" and label in self._parent_attributes:
                self._parent_attributes[label].watch_dependency(dependency)
        self._bindings[output_name] = ItemImpl.BindingInfo(func, input_info, label=binding_label)

    def __create_attr_info_from_attr_type(
        self, input_info: List[str | Template.FreeAttribute]
    ) -> None:
        for k in range(len(input_info)):
            if isinstance(input_info[k], str):
                input_info[k] = freeatt(input_info[k])

    def __collect_input_attributes(
        self, input_info: Tuple[Template.FreeAttribute, ...]
    ) -> List[AbstractAttribute]:
        inputs: List[AbstractAttribute] = list()
        for info in input_info:
            if info.owner == "child":
                inputs.append(self.__get_child_attr_list(info))
            elif info.owner == "parent":
                inputs.append(self.__get_parent_attribute(info))
            else:
                inputs.append(self.attribute(info.label))
        return inputs

    def __get_child_attr_list(self, info: Template.FreeAttribute) -> Attribute_List:
        if info.label not in self._child_attr_lists:
            self._create_child_attr_list(info.info["atype"], info.label)
        return self._child_attr_lists[info.label]

    def __get_parent_attribute(self, info: Template.FreeAttribute) -> AbstractAttribute:
        if not info.label in self._parent_attributes:
            stub = self._manager._attrfac.new_from_dict(**info.info)
            if not self.parent.is_null():
                self._parent_attributes[info.label] = Parent_Attribute(
                    self.parent.attribute(info.label), stub
                )
            else:
                self._parent_attributes[info.label] = Parent_Attribute(stub, stub)
        return self._parent_attributes[info.label].attr

    def free(self, output_name: str) -> None:
        self.attribute(output_name).break_dependency()
        self._bindings.pop(output_name)

    def has_attribute(self, label: str) -> bool:
        return label in self.__attributes

    def adopt(self, item: Item) -> None:
        if self is item.parent:
            return
        if self._check_can_be_parent_of(item):

            @self.controller.single_cmd()
            def perform_adoption():
                self.controller.run(*self.command["adopt"](Parentage_Data(self, item)))
                item._set_parent_attributes(parent=self)

            perform_adoption()

    def leave(self, *children: Item) -> None:
        if not children:
            return

        @self.controller.single_cmd()
        def perform_leaving():
            for child in children:
                self.controller.run(*self.command["leave"](Parentage_Data(self, child)))
            children[0]._set_parent_attributes(parent=self.NULL)

        perform_leaving()

    def _set_parent_attributes(self, parent: Item) -> None:
        for label, attr in self._parent_attributes.items():
            if parent.has_attribute(label):
                attr.set(parent.attribute(label))
            else:
                attr.set(attr.stub)

    def __check_attr_type_matches_list_type(
        self, alist: Attribute_List, attribute: AbstractAttribute
    ) -> None:

        if not alist.type == attribute.type:
            raise self.ChildAttributeTypeConflict

    def _create_child_attr_list(self, value_type: AttributeType, child_attr_label: str) -> None:
        alist = self._manager._attrfac.newlist(
            atype=value_type, name=child_attr_label + " (children)"
        )

        for child in self.__children:
            if child_attr_label in child.attributes:
                self.__check_attr_type_matches_list_type(alist, child.attribute(child_attr_label))
                alist.append(child.attribute(child_attr_label))

        def adopt_cmd(data: Parentage_Data) -> Command:
            if not data.child.has_attribute(child_attr_label):
                return Empty_Command()
            self.__check_attr_type_matches_list_type(alist, data.child.attribute(child_attr_label))
            cmd_data = Edit_AttrList_Data(alist, data.child.attribute(child_attr_label))
            return Append_To_Attribute_List(cmd_data)

        def leave_child_cmd(data: Parentage_Data) -> Command:
            if not data.child.has_attribute(child_attr_label):
                return Empty_Command()
            cmd_data = Edit_AttrList_Data(alist, data.child.attribute(child_attr_label))
            return Remove_From_Attribute_List(cmd_data)

        def converter(data: Parentage_Data) -> Set_Attr_Data:
            value_getter = lambda: alist.value
            return Set_Attr_Data(alist, value_getter)

        self.command["adopt"].add(alist.id, adopt_cmd, "post")
        self.command["adopt"].add_composed(alist.id, converter, alist.command["set"], "post")
        self.command["leave"].add(alist.id, leave_child_cmd, "post")
        self.command["leave"].add_composed(alist.id, converter, alist.command["set"], "post")

        self._child_attr_lists[child_attr_label] = alist

    def pass_to_new_parent(self, child: Item, new_parent: Item) -> None:
        if new_parent._check_can_be_parent_of(child) and isinstance(new_parent, ItemImpl):
            self.controller.run(
                *self.command["leave"](Parentage_Data(self, child)),
                *new_parent.command["adopt"](Parentage_Data(new_parent, child)),
            )

    def pick_child(self, name: str) -> Item:
        name = strip_and_join_spaces(name)
        for child in self.__children:
            if child.name == name:
                return child
        return ItemImpl.NULL

    def rename(self, name: str) -> None:
        self.controller.run(*self.command["rename"](Renaming_Data(self, name)))

    def set(self, attrib_label: str, value: Any) -> None:
        if attrib_label == "name":
            self.rename(value)
        self.attribute(attrib_label).set(value)

    def multiset(self, attr_to_value_dict: Dict[str, Any]) -> None:
        attrs: Dict[Attribute, Any] = dict()
        for label in attr_to_value_dict:
            if label in self.__attributes:
                if label == "name":
                    continue
                attrs[self.__attributes[label]] = attr_to_value_dict[label]
            else:
                raise Item.NonexistentAttribute(label)
        Attribute.set_multiple(attrs)

    def on_adoption(
        self, owner: str, func: Callable[[Parentage_Data], Command], timing: Timing
    ) -> None:
        self.command["adopt"].add(owner, func, timing)

    def on_leaving(
        self, owner: str, func: Callable[[Parentage_Data], Command], timing: Timing
    ) -> None:
        self.command["leave"].add(owner, func, timing)

    def on_renaming(
        self, owner: str, func: Callable[[Renaming_Data], Command], timing: Timing
    ) -> None:
        self.command["rename"].add(owner, func, timing)

    def copy(self) -> Item:
        @self.controller.no_undo()
        def copy_self():
            the_copy = self._duplicate_items()
            self._copy_bindings(the_copy)
            return the_copy

        return copy_self()

    def duplicate(self) -> Item:
        the_copy = self.copy()
        self.parent.adopt(the_copy)
        return the_copy

    def has_children(self) -> bool:
        return bool(self.__children)

    def is_null(self) -> bool:
        return False  # pragma: no cover

    def is_parent_of(self, child: Item) -> bool:
        return child in self.__children

    def is_ancestor_of(self, item: Item) -> bool:
        while True:
            item = item.parent
            if item == self:
                return True
            elif item == self.NULL:
                return False

    def __call__(self, attr_name: str) -> Any:
        if attr_name not in self.attributes:
            raise Item.NonexistentAttribute(attr_name)
        else:
            return self.attribute(attr_name).value

    def _accept_parent(self, item: Item) -> None:
        if self.__parent is self.NULL:
            self.__parent = item

    def _adopt(self, child: Item) -> None:
        if child in self.__formal_children:
            self.__formal_children.remove(child)
        child._accept_parent(self)
        self.__make_child_to_rename_if_its_name_already_taken(child)
        if self is child.parent:
            self.__children.add(child)
        self.__run_actions_after_command("adopt", child)

    def _can_be_parent_of_item_type(self, item: Item) -> bool:
        return (self.__child_itypes is not None) and (item.itype in self.__child_itypes)

    def _check_can_be_parent_of(self, item: Item) -> bool:
        if self.__child_itypes is not None:
            if item.itype not in self.__child_itypes:
                raise Item.CannotAdoptItemOfType(item.itype)

        if item.is_ancestor_of(self):
            raise Item.AdoptionOfAncestor(item.name)
        elif item == self:
            raise Item.ItemAdoptsItself(item.name)
        else:
            return True

    def _duplicate_items(self) -> ItemImpl:
        dupl = ItemImpl(
            self.name,
            attributes=self.__attributes_copy(),
            manager=self._manager,
            itype=self.itype,
            child_itypes=self.__child_itypes,
            ignore_duplicit_names=self.__ignore_duplicit_names,
        )
        for attr in dupl.__attributes.values():
            if attr.dependent:
                attr.break_dependency()
        for child in self.__children:
            child_duplicate = child._duplicate_items()
            dupl._adopt(child_duplicate)
        return dupl

    def _apply_binding_info(self) -> None:
        for output_name, info in self._bindings.items():
            self.bind(output_name, info.func, *info.input_labels, binding_label=info.label)

    def _copy_bindings(self, dupl: Item) -> None:
        dupl._bindings = self._bindings.copy()
        dupl._apply_binding_info()
        for child, child_dupl in zip(self.__children, dupl.children):
            child._copy_bindings(child_dupl)

    def _leave_child(self, child: Item) -> None:
        if child in self.__children:
            self.__children.remove(child)
            child._leave_parent(self)
            self.__run_actions_after_command("leave", child)

    def _leave_parent(self, parent: Item) -> None:
        if parent is self.parent:
            if self.__parent is self.NULL:
                return
            self.__parent._leave_child(self)
            self.__parent = self.NULL

    def _rename(self, name: str) -> None:
        name = strip_and_join_spaces(name)
        self.__raise_if_name_is_blank(name)
        if not self.parent.is_null():
            assert isinstance(self.parent, ItemImpl)
            name = self.parent.__adjust_name_if_taken(self, name)
        self.attribute("name")._hard_set(name)
        self.__run_actions_after_command("rename", self)

    def __run_actions_after_command(self, after_command: Command_Type, item: Item) -> None:
        for action in self.__actions[after_command].values():
            action(item)
            self.__last_action = (self.name, after_command, item.name)

    def __attributes_copy(self) -> Dict[str, Attribute]:
        attr_copy: Dict[str, Attribute] = {}
        for label, attr in self.attributes.items():
            attr_copy[label] = attr.copy()
        return attr_copy

    def __adjust_name_if_taken(self, item: Item, cname: str) -> str:
        if self.__ignore_duplicit_names:
            return cname
        names = [c.name for c in self.__children if not c == item]
        while cname in names:
            names.remove(cname)
            cname = adjust_taken_name(cname)
        return cname

    def __make_child_to_rename_if_its_name_already_taken(self, child: Item):
        child._rename(self.__adjust_name_if_taken(child, child.name))

    def __raise_if_name_is_blank(self, name: str) -> None:
        if name == "":
            raise self.BlankName

    class AlreadyAChild(Exception):
        pass

    class ChildAttributeTypeConflict(Exception):
        pass
