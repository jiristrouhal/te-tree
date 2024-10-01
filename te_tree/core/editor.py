from __future__ import annotations


from typing import Tuple, Dict, List, Any, Optional, Callable, Literal
from te_tree.core.item import ItemCreator, Item, Template, Attribute_Data_Constructor
from te_tree.core.item import (
    FileType,
    freeatt,
    freeatt_child,
    freeatt_parent,
)  # keep these imports to be further imported elsewhere
from te_tree.core.attributes import Locale_Code
from te_tree.core.item import ItemImpl

import re


CASE_TYPE_LABEL = "__Case__"


from decimal import Decimal

MergeRule = Literal["sum", "join_texts", "max", "min"]
_MergeFunc = Callable[[List[Any]], Any]


from te_tree.core.attributes import Currency_Code


class CaseTemplate:
    def __init__(self) -> None:
        self._templates: Dict[str, Template] = {}
        self._case_child_labels: List[str] = list()
        self._attributes: Dict[str, Dict[str, Any]] = {}
        self._constructor = Attribute_Data_Constructor()
        self._insertable: str = ""
        self._currency: Currency_Code = "USD"
        self._case_template: Optional[Template] = None
        self._merge_rules: Dict[str, Dict[str, _MergeFunc]] = dict()

    @property
    def attr(self) -> Attribute_Data_Constructor:
        return self._constructor

    @property
    def templates(self) -> Dict[str, Template]:
        return self._templates

    @property
    def case_child_labels(self) -> Tuple[str, ...]:
        return tuple(self._case_child_labels)

    @property
    def attributes(self) -> Dict[str, Dict[str, Any]]:
        return self._attributes.copy()

    @property
    def insertable(self) -> str:
        return self._insertable

    @property
    def currency_code(self) -> Currency_Code:
        return self._currency

    @property
    def merging_rules(self) -> Dict[str, Dict[str, _MergeFunc]]:
        return self._merge_rules.copy()

    def add(
        self,
        label: str,
        attribute_info: Dict[str, Dict[str, Any]],
        child_template_labels: Tuple[str, ...] = (),
        dependencies: Optional[List[Template.Dependency]] = None,
    ) -> None:

        label = label.strip()
        if label == "":
            raise CaseTemplate.BlankTemplateLabel

        if re.fullmatch("[\w]+", label) is None:
            raise CaseTemplate.InvalidCharactersInLabel(
                f"Invalid label '{label}'. Only alphanumeric characters"
                "(a-z, A-Z and 0-9) plus '_' are allowed."
            )

        for attr, info in attribute_info.items():
            if attr not in self._attributes:
                self._attributes[attr] = info
            elif info["atype"] != self._attributes[attr]["atype"]:
                raise CaseTemplate.ReaddingAttributeWithDifferentType(
                    f"Attribute '{attr}' has type {info['atype']}. "
                    f"Previously was added with type '{self._attributes[attr]}'."
                )

        self._templates[label] = Template(
            label, attribute_info, child_template_labels, dependencies
        )

    def set_case_template(
        self,
        attribute_info: Dict[str, Dict[str, Any]],
        child_template_labels: Tuple[str, ...],
        dependencies: Optional[List[Template.Dependency]] = None,
    ) -> None:

        self.add(CASE_TYPE_LABEL, attribute_info, child_template_labels, dependencies)

    def add_case_child_label(self, *labels: str) -> None:
        for label in labels:
            if label not in self._templates:
                raise CaseTemplate.UndefinedTemplate(label)
            self._case_child_labels.append(label)

    def add_merging_rule(self, itype: str, attribute_rules: Dict[str, MergeRule]) -> None:
        if not itype in self._templates:
            raise CaseTemplate.AddingMergeRuleToUndefinedItemType(itype)
        elif itype in self._merge_rules:
            raise CaseTemplate.MergeRuleAlreadyDefined(itype)
        # create empty dict for merging rules of item type 'itype'
        self._merge_rules[itype] = dict()
        # collect attribute labels for item type 'itype'
        attr_labels = self._templates[itype].attribute_info.keys()
        # pick available merge rule from a dictionary of this class and assign it
        # to the attribute label 'alabel'
        for alabel in attr_labels:
            if alabel not in attribute_rules:
                raise CaseTemplate.AttributeWithUndefinedMergeRule(alabel)
            rule_label = attribute_rules[alabel]
            if rule_label not in self._merge_func:
                raise CaseTemplate.UndefinedMergeFunction(rule_label)
            self._merge_rules[itype][alabel] = self._merge_func[rule_label]

    def configure(self, **kwargs) -> None:
        for label, value in kwargs.items():
            match label:
                case "currency_code":
                    self._currency = value
                case _:
                    continue

    def dependency(
        self, dependent: str, func: Callable[[Any], Any], *free: Template.FreeAttribute
    ) -> CaseTemplate.Dependency:
        return CaseTemplate.Dependency(dependent, func, free)

    def set_insertable(self, template_label: str) -> None:
        if template_label not in self._templates:
            raise CaseTemplate.UndefinedTemplate(template_label)
        self._insertable = template_label

    def _list_templates(self) -> Tuple[Template, ...]:
        returned_templates = list(self._templates.values())
        if not CASE_TYPE_LABEL in self._templates:
            returned_templates.insert(
                0, Template(CASE_TYPE_LABEL, {}, tuple(self._case_child_labels))
            )
        return tuple(returned_templates)

    _merge_func: Dict[MergeRule, _MergeFunc] = {
        "sum": lambda x: sum(Decimal(str(xi)) for xi in x),
        "max": lambda x: max(x),
        "min": lambda x: min(x),
        "join_texts": lambda d: "\n\n".join(d),
    }

    class AddingMergeRuleToUndefinedItemType(Exception):
        pass

    class AttributeWithUndefinedMergeRule(Exception):
        pass

    class BlankTemplateLabel(Exception):
        pass

    class Dependency(Template.Dependency):
        pass

    class InvalidCharactersInLabel(Exception):
        pass

    class MergeRuleAlreadyDefined(Exception):
        pass

    class ReaddingAttributeWithDifferentType(Exception):
        pass

    class UndefinedMergeFunction(Exception):
        pass

    class UndefinedTemplate(Exception):
        pass


from te_tree.core.item import Attribute_Data_Constructor


class Editor:
    def __init__(
        self,
        case_template: CaseTemplate,
        locale_code: Locale_Code,
        lang: Optional[Lang_Object] = None,
        ignore_duplicit_names: bool = False,
    ) -> None:

        self._creator = ItemCreator(locale_code, case_template.currency_code, ignore_duplicit_names)
        self._creator.add_templates(*case_template._list_templates())
        self._root = self._creator.new("_", child_itypes=(CASE_TYPE_LABEL,))
        self._attributes = case_template.attributes
        self._insertable = case_template.insertable
        self._locale_code = locale_code
        if lang is None:
            self._lang = Lang_Object.get_lang_object()
        else:
            self._lang = lang

        self._copied_item: Optional[Item] = None

        self._selection: set[Item] = set()
        self._actions_on_selection: Dict[str, List[Callable[[], None]]] = dict()

        self._merging_rules: Dict[str, Dict[str, _MergeFunc]] = case_template.merging_rules.copy()

    @property
    def attributes(self) -> Dict[str, Dict[str, Any]]:
        return self._attributes

    @property
    def insertable(self) -> str:
        return self._insertable

    @property
    def locale_code(self) -> Locale_Code:
        return self._locale_code

    @property
    def root(self) -> Item:
        return self._root

    @property
    def ncases(self) -> int:
        return len(self._root.children)

    @property
    def export_dir_path(self) -> str:
        return self._creator.file_path

    @property
    def creator(self) -> ItemCreator:
        return self._creator

    @property
    def item_to_paste(self) -> Item | None:
        return self._copied_item

    @property
    def selection(self) -> List[Item]:
        return list(self._selection)

    @property
    def selection_is_mergeable(self) -> bool:
        return self.is_mergeable(*self._selection)

    @property
    def selection_is_groupable(self) -> bool:
        return self.is_groupable(self._selection)

    def add_action_on_selection(self, owner_id: str, action: Callable[[], None]) -> None:
        if owner_id not in self._actions_on_selection:
            self._actions_on_selection[owner_id] = list()
        self._actions_on_selection[owner_id].append(action)

    def can_paste_under_or_next_to(self, to_be_pasted: Item, other_item: Item) -> bool:
        if self._copied_item is None:
            return False
        can_paste_under = other_item._can_be_parent_of_item_type(to_be_pasted)
        can_paste_next_to = (
            other_item.parent._can_be_parent_of_item_type(to_be_pasted)
            and not other_item.parent.is_null()
        )
        return can_paste_under or can_paste_next_to

    def _cases(self) -> Set[Item]:
        return self._root.children.copy()

    def can_save_as_item(self, item: Item) -> bool:
        return item.itype == self._insertable

    def can_insert_under(self, parent: Item) -> bool:
        parent_template = self._creator.get_template(parent.itype)
        return self._insertable in parent_template.child_itypes

    def copy(self, item: Item) -> None:
        self._copied_item = item.copy()

    def copy_selection(self) -> None:
        if len(self._selection) == 1:
            self.copy(list(self._selection)[0])

    def cut(self, item: Item) -> None:
        self._copied_item = item.copy()
        item.parent.leave(item)

    def cut_selection(self) -> None:
        if len(self._selection) == 1:
            self.cut(list(self._selection)[0])

    def contains_case(self, case: Item) -> bool:
        return self._root.is_parent_of(case)

    def does_file_exist(self, item: Item, filetype: FileType) -> bool:
        return self._creator.does_file_exist(item, filetype)

    def duplicate(self, item: Item) -> Item:
        return item.duplicate()

    def duplicate_selection(self) -> None:
        if len(self._selection) == 1:
            self.duplicate(list(self._selection)[0])

    from te_tree.core.item import Parentage_Data

    def duplicate_as_case(self, item: Item) -> Item:
        case = self._creator.from_template(CASE_TYPE_LABEL, item.name)
        item_dupl = item.copy()
        self._root.controller.run(
            *self._root.command["adopt"](self.Parentage_Data(self._root, case)),
            *case.command["adopt"](self.Parentage_Data(case, item_dupl)),
        )
        return case

    def is_groupable(self, items: list[Item] | set[Item]) -> bool:
        if self._insertable == "":
            return False
        elif len(items) < 1:
            return False
        else:
            items_list = list(items)
            orig_parent = items_list.pop(0).parent
            for item in items_list:
                if item.parent != orig_parent:
                    return False
        return True

    def is_ungroupable(self, item: Item) -> bool:
        return item.itype == self.insertable and item.has_children()

    def its_case(self, item: Item) -> Item:
        if item == self._root:
            return ItemImpl.NULL
        elif self.is_case(item):
            return item
        else:
            return self.its_case(item.parent)

    def group_selection(self) -> None:
        self.group(set(self._selection))

    def ungroup_selection(self) -> None:
        if len(self._selection) == 1:
            self.ungroup(list(self._selection)[0])

    def group(self, items: set[Item]) -> Item:
        if not self.is_groupable(items):
            return ItemImpl.NULL
        else:
            orig_parent = list(items)[0].parent

            @self._creator._controller.single_cmd()
            def move_under_group_parent() -> Item:
                new_parent = self.new(
                    orig_parent,
                    self.insertable,
                    name=self._lang.label("Miscellaneous", "new_group"),
                )
                for item in items:
                    orig_parent.pass_to_new_parent(item, new_parent)
                return new_parent

            return move_under_group_parent()

    def ungroup(self, item: Item) -> None:
        if not self.is_ungroupable(item):
            return

        @self._creator._controller.single_cmd()
        def do_ungrouping() -> None:
            for child in item.children:
                item.pass_to_new_parent(child, item.parent)
            item.parent.leave(item)

        do_ungrouping()

    def insert_from_file(self, parent: Item, dirpath: str, name: str, filetype: FileType) -> Item:
        if not self.can_insert_under(parent):
            raise Editor.CannotInsertItemUnderSelectedParent(parent.name, parent.itype)

        @self._creator._controller.single_cmd()
        def load_and_adopt() -> Item:
            item = self._creator.load(dirpath, name, filetype)
            parent.adopt(item)
            return item

        return load_and_adopt()

    @staticmethod
    def is_case(item: Item) -> bool:
        if item is None or item.is_null():
            return False
        return item.itype == CASE_TYPE_LABEL

    def is_mergeable(self, *items: Item) -> bool:
        n = len(items)
        if n < 2:
            return False
        first_item = items[0]
        parent, itype = first_item.parent, first_item.itype
        if itype not in self._merging_rules:
            return False
        for k in range(1, n):
            if items[k].parent != parent or items[k].itype != itype:
                return False
        return True

    def item_types_to_create(self, parent: Item) -> Tuple[str, ...]:
        return self._creator.get_template(parent.itype).child_itypes

    def load_case(self, dirpath: str, name: str, ftype: FileType) -> Item:
        @self._creator._controller.single_cmd()
        def load_case_and_add_to_editor() -> Item:
            case = self._creator.load(dirpath, name, ftype)
            self._root.adopt(case)
            return case

        return load_case_and_add_to_editor()

    def merge_selection(self) -> Item:
        return self.merge(*self._selection)

    def merge(self, *items: Item) -> Item:
        self._check_items_are_mergeable(*items)

        @self._creator._controller.single_cmd()
        def __set_merged_item_attributes(items: List[Item], merged_item: Item) -> None:
            new_name = "; ".join([item.name for item in items])
            merged_item.rename(self._lang.label("Miscellaneous", "merged") + ": " + new_name)
            new_vals: Dict[Attribute, Any] = dict()
            for attr, func in self._merging_rules[merged_item.itype].items():
                new_vals[merged_item.attribute(attr)] = func([item(attr) for item in items])
            merged_item.attribute(attr).set_multiple(new_vals)

        @self._creator._controller.single_cmd()
        def new_merged_item() -> Item:
            parent, itype = items[0].parent, items[0].itype
            merge_result = self.new(parent, itype)
            # parent must leave the original items
            __set_merged_item_attributes(items, merge_result)
            parent.leave(*items)
            return merge_result

        return new_merged_item()

    def _check_items_are_mergeable(self, *items: Item) -> None:
        if not self.is_mergeable(*items):
            raise Exception(f"Items are not mergeable: {items}")

    def new(self, parent: Item, itype: str, name: str = "") -> Item:
        if itype not in self._creator.templates:
            raise Editor.UndefinedTemplate(itype)

        available_itypes = self.item_types_to_create(parent)
        if (available_itypes is None) or (itype not in available_itypes):
            raise Editor.InvalidChildTypeUnderGivenParent(
                f"Parent type: {parent.itype}, child type: {itype}."
            )

        @self._creator._controller.single_cmd()
        def create_and_adopt(name: str) -> Item:
            if name == "":
                name = self._lang.label("Item_Types", itype)
            item = self._creator.from_template(itype, name=name)
            parent.adopt(item)
            return item

        return create_and_adopt(name)

    def new_case(self, name: str) -> Item:
        @self._creator._controller.single_cmd()
        def create_and_adopt() -> Item:
            case = self._creator.from_template(CASE_TYPE_LABEL, name=name)
            self._root.adopt(case)
            return case

        return create_and_adopt()

    def paste_under(self, parent: Item) -> None:
        if self._copied_item is None or not self.can_paste_under_or_next_to(
            self._copied_item, parent
        ):
            return
        else:
            if not parent._can_be_parent_of_item_type(self._copied_item):
                parent = parent.parent
            parent.adopt(self._copied_item)
            self._copied_item = None

    def paste_under_selection(self) -> None:
        if len(self._selection) == 1:
            parent = list(self._selection)[0]
            self.paste_under(parent)
        elif not self._selection and self.is_case(self._copied_item):
            self.paste_under(self._root)

    def remove(self, item: Item, parent: Item) -> None:
        if parent == item.parent:
            parent.leave(item)

    def remove_case(self, case: Item) -> None:
        self._root.leave(case)

    def save(self, item: Item, filetype: FileType) -> None:
        if Editor.is_case(item) or self.can_save_as_item(item):
            self._creator.save(
                item,
                filetype,
                backup_folder_name=self._lang.label("Miscellaneous", "backup_folder_name"),
            )
        else:
            raise Editor.CannotSaveAsItem(item.name, item.itype)

    def save_as_case(self, item: Item, filetype: FileType) -> None:
        if not Editor.is_case(item):
            case = self._creator.from_template(CASE_TYPE_LABEL, item.name)
            case.adopt_formally(item)
            self._creator.save(case, filetype)
        else:
            self._creator.save(item, filetype)

    def select(self, item: Item) -> None:
        if item is self._root:
            self._selection.clear()
        else:
            self._selection = {item}
            self._selection_parent = item.parent
            self._selection_itype = item.itype
        self._run_actions_on_selection()

    def select_add(self, item: Item) -> None:
        if self._selection:
            if not item.parent == self._selection_parent:
                return
            elif not item.itype == self._selection_itype:
                return
        self._selection.add(item)

    def selection_set(self, items: List[Item]) -> None:
        if self._root in items:
            items.remove(self._root)
        self._selection = items.copy()

    def select_none(self) -> None:
        self._selection.clear()
        self._run_actions_on_selection()

    def set_dir_path(self, dirpath: str) -> None:
        self._creator.set_dir_path(dirpath)

    def undo(self) -> None:
        self._creator.undo()

    def redo(self) -> None:
        self._creator.redo()

    def _run_actions_on_selection(self) -> None:
        for group in self._actions_on_selection.values():
            for action in group:
                action()

    def print(self, item: Item, attribute_name: str, **options) -> str:
        return item.attribute(attribute_name).print(**options)

    class CannotExportCaseAsItem(Exception):
        pass

    class CannotInsertItemUnderSelectedParent(Exception):
        pass

    class CannotSaveAsItem(Exception):
        pass

    class InvalidChildTypeUnderGivenParent(Exception):
        pass

    class UndefinedTemplate(ItemCreator.UndefinedTemplate):
        pass


def new_editor(
    case_template: CaseTemplate,
    locale_code: Locale_Code = "en_us",
    lang: Optional[Lang_Object] = None,
    ignore_duplicit_names: bool = False,
) -> Editor:

    return Editor(case_template, locale_code, lang, ignore_duplicit_names)


def blank_case_template() -> CaseTemplate:
    return CaseTemplate()


from typing import Set


class Item_Menu_Cmds:

    def __init__(self, init_cmds: Dict[str, Callable[[], Item | None]] = {}) -> None:
        self._items: Dict[str, Item_Menu_Cmds | Callable[[], Item | None] | None] = dict()
        self._children: Dict[str, Item_Menu_Cmds] = dict()
        self._custom_cmds_after_menu_cmd: Set[Callable[[], None]] = set()

        self.insert(init_cmds)

    @property
    def items(self) -> Dict[str, Item_Menu_Cmds | Callable[[], None | Item]]:
        return self._items.copy()

    def add_post_cmd(self, cmd: Callable[[], None]) -> None:
        self._custom_cmds_after_menu_cmd.add(cmd)

    def cmd(self, label: str, *cmd_path: str) -> Callable[[], None | Item]:
        if cmd_path:
            return self._children[cmd_path[0]].cmd(label, *cmd_path[1:])
        else:
            cmd = self._items[label]
            assert callable(cmd)
            return cmd

    def insert(self, commands: Dict[str, Callable[[], None | Item]], *cmd_path: str) -> None:
        if not commands:
            return
        if cmd_path:
            if cmd_path[0] not in self._children:
                self._children[cmd_path[0]] = Item_Menu_Cmds()
            self._children[cmd_path[0]].insert(commands, *cmd_path[1:])
            self._items[cmd_path[0]] = self._children[cmd_path[0]]
        else:
            self._items.update(commands.copy())

    def insert_sep(self) -> None:
        self._items[f"__sep__{len(self._items)}"] = None

    def labels(self, *cmd_path: str) -> List[str]:
        if cmd_path:
            if cmd_path[0] not in self._children:
                return []
            return self._children[cmd_path[0]].labels(*cmd_path[1:])
        else:
            return list(self._items.keys())

    def run(self, label, *cmd_path) -> None:
        self.cmd(label, *cmd_path)()
        for cmd in self._custom_cmds_after_menu_cmd:
            cmd()


import abc
from functools import partial
import os


class EditorUI(abc.ABC):

    def __init__(
        self,
        editor: Editor,
        item_menu: Item_Menu,
        item_window: Item_Window,
        caseview: Case_View,
        lang: Optional[Lang_Object] = None,
    ) -> None:

        self._editor = editor
        self._item_menu = item_menu
        self._item_window = item_window
        self._caseview = caseview
        self._compose()
        if lang is None:
            lang = Lang_Object.get_lang_object()
        self._lang = lang
        self._caseview.on_selection_change(self._pass_caseview_selection_to_editor)

    @property
    def caseview(self) -> Case_View:
        return self._caseview

    @property
    def editor(self) -> Editor:
        return self._editor

    def _pass_caseview_selection_to_editor(self) -> None:
        self.editor.selection_set(self.caseview.selected_items)

    @abc.abstractmethod
    def _compose(self) -> None:
        pass

    def configure(self, **kwargs) -> None:
        self._caseview.configure(**kwargs)
        self._item_window.configure(**kwargs)

    def delete_item(self, item: Item, *args) -> None:
        if item != self._editor.root:
            item.parent.leave(item)

    def open_item_menu(self, item: Item, *args) -> None:
        if item.is_null():
            raise EditorUI.Opening_Item_Menu_For_Nonexistent_Item
        elif item == self._editor.root:
            self._item_menu.open(self._root_item_actions(), *args)
        elif item.itype == CASE_TYPE_LABEL:
            self._item_menu.open(self._case_actions(item), *args)
        else:
            self._item_menu.open(self._item_actions(item), *args)

    def import_case_from_xml(self) -> None:
        case_dir_path, case_name = self._get_xml_path()
        if case_name.strip() == "":
            return
        self._editor.load_case(case_dir_path, case_name, "xml")

    def save_selected_cases_to_xml(self) -> None:
        if not self.caseview.selected_items:
            return
        selected_cases: Set[Item] = {
            self._editor.its_case(item) for item in self.caseview.selected_items
        }
        for selected_case in selected_cases:
            self.save_case_to_existing_xml(selected_case)

    def save_case_to_xml(self, case: Item) -> None:
        dir_path = self._get_export_dir()
        if not os.path.isdir(dir_path):
            return
        self._editor.set_dir_path(dir_path)
        self._editor.save(case, "xml")

    def save_case_to_existing_xml(self, case: Item) -> None:
        if not self._editor.does_file_exist(case, "xml"):
            self.save_case_to_xml(case)
        else:
            self._editor.save(case, "xml")

    @abc.abstractmethod
    def _get_xml_path(self) -> Tuple[str, str]:
        pass

    @abc.abstractmethod
    def _get_export_dir(self) -> str:
        pass

    def _root_item_actions(self) -> Item_Menu_Cmds:
        actions = Item_Menu_Cmds()
        actions.insert({"import_from_xml": self.import_case_from_xml})
        actions.insert({"new_case": self._new_case})
        if self._editor.can_paste_under_or_next_to(self._editor.item_to_paste, self._editor.root):
            actions.insert({"paste": lambda: self._editor.paste_under(self._editor.root)})
        return actions

    def _case_actions(self, case: Item) -> Item_Menu_Cmds:
        actions = Item_Menu_Cmds()
        for itype in self._editor.item_types_to_create(case):
            actions.insert({itype: partial(self._editor.new, case, itype)}, "add")
        actions.insert({"edit": lambda: self.open_item_window(case)})
        actions.insert_sep()
        actions.insert(
            {
                "copy": lambda: self._editor.copy(case),
                "duplicate": lambda: self._editor.duplicate(case),
                "cut": lambda: self._editor.cut(case),
            }
        )
        if self._editor.can_paste_under_or_next_to(self._editor.item_to_paste, case):
            actions.insert({"paste": lambda: self._editor.paste_under(case)})
        actions.insert_sep()
        if self._editor.does_file_exist(case, "xml"):
            actions.insert({"save_to_existing_xml": lambda: self.save_case_to_existing_xml(case)})
        actions.insert({"export_to_xml": lambda: self.save_case_to_xml(case)})
        actions.insert_sep()
        actions.insert({"delete": lambda: self._editor.remove_case(case)})
        return actions

    def _item_actions(self, item: Item) -> Item_Menu_Cmds:
        actions = Item_Menu_Cmds()
        for itype in self._editor.item_types_to_create(item):
            actions.insert(
                {itype: partial(self._create_new_and_open_edit_window, item, itype)},
                "add",
            )
        actions.insert({"edit": lambda: self.open_item_window(item)})
        actions.insert_sep()
        actions.insert(
            {
                "copy": lambda: self._editor.copy(item),
                "duplicate": lambda: self._editor.duplicate(item),
                "cut": lambda: self._editor.cut(item),
            }
        )
        if self._editor.can_paste_under_or_next_to(self._editor.item_to_paste, item):
            actions.insert({"paste": lambda: self._editor.paste_under(item)})
        actions.insert_sep()
        if item in self._editor.selection and self._editor.selection_is_mergeable:
            actions.insert({"merge": self._editor.merge_selection})
            actions.insert_sep()
        if item in self._editor.selection and self._editor.selection_is_groupable:
            actions.insert({"group": self._editor.group_selection})
        if self._editor.is_ungroupable(item):
            actions.insert({"ungroup": lambda: self._editor.ungroup(item)})
        actions.insert({"delete": lambda: self._editor.remove(item, item.parent)})
        return actions

    def _create_new_and_open_edit_window(self, parent: Item, itype: str, *args) -> None:
        new_item = self._editor.new(parent, itype)
        self.open_item_window(new_item, *args)

    def open_item_window(self, item: Item, *args) -> None:
        if item is not self._editor.root:
            self._item_window.open(item)

    def _new_case(self) -> None:
        self._editor.new_case(self._lang.label("Item_Types", "Case"))

    class Opening_Item_Menu_For_Nonexistent_Item(Exception):
        pass


from typing import Callable
from te_tree.core.attributes import Attribute
import abc


class Item_Window(abc.ABC):

    def __init__(self, lang: Optional[Lang_Object] = None) -> None:
        if lang is None:
            lang = Lang_Object_NULL()
        self._lang = lang
        self._open: bool = False

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def lang(self) -> Lang_Object:
        return self._lang

    @property
    def title(self) -> str:
        return self._lang.label("Item_Window", "Title")

    def open(self, item: Item) -> None:
        name_attr = item._manager._attrfac.new("name", item.name)
        rename_action = lambda: item._rename(name_attr.value)

        name_attr.add_action_on_set("item_window", rename_action)
        attributes: Dict[str, Attribute] = {"name": name_attr}
        attributes.update(item.attributes)
        self._build_window(attributes)
        self._open = True

    def close(self) -> None:
        self._destroy_window()
        self._open = False

    @abc.abstractmethod
    def configure(self, **kwargs) -> None:
        pass

    @abc.abstractmethod
    def _build_window(self, attributes: Dict[str, Attribute]):
        pass  # pragma: no cover

    @abc.abstractmethod
    def _destroy_window(self):
        pass  # pragma: no cover


class Item_Menu(abc.ABC):

    def __init__(self, lang: Lang_Object) -> None:
        self._actions: Optional[Item_Menu_Cmds] = None
        self._open: bool = False
        self._lang = lang

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def actions(self) -> Optional[Item_Menu_Cmds]:
        return self._actions

    @property
    def lang(self) -> Lang_Object:
        return self._lang

    def action_labels(self, *cmd_path) -> List[str]:
        if self._actions is not None:
            return self._actions.labels(*cmd_path)
        else:
            return []

    def close(self) -> None:
        self._open = False
        self._destroy_menu()
        self._actions = None

    def open(self, actions: Item_Menu_Cmds, *args) -> None:
        if not actions.labels():
            return
        else:
            self._actions = actions
            self._open = True
            self._build_menu(*args)
            self._actions.add_post_cmd(self.close)

    def run(self, action_label: str, *cmd_path: str) -> None:
        if self._actions is not None:
            self._actions.run(action_label, *cmd_path)

    @abc.abstractmethod
    def _build_menu(self, *args) -> None:
        pass  # pragma: no cover

    @abc.abstractmethod
    def _destroy_menu(self) -> None:
        pass  # pragma: no cover


class Case_View(abc.ABC):

    @abc.abstractproperty
    def selected_items(self) -> Set(Item):
        pass

    @abc.abstractmethod
    def configure(self, **kwargs) -> None:
        pass

    @abc.abstractmethod
    def is_in_view(self, item_id: str) -> bool:
        pass

    @abc.abstractmethod
    def on_selection_change(self, func: Callable[[], None]) -> None:
        pass

    @abc.abstractmethod
    def tree_row_values(self, item_id: str) -> Dict[str, Any]:
        pass


import xml.etree.ElementTree as et


class Lang_Object(abc.ABC):
    def __init__(self, *args) -> None:
        pass

    @abc.abstractmethod
    def label(self, *path: str) -> str:
        pass

    def __call__(self, *path: str) -> str:
        return self.label(*path)

    @staticmethod
    def get_lang_object(xml_lang_file_path: Optional[str] = None) -> Lang_Object:
        if xml_lang_file_path is None:
            return Lang_Object_NULL()
        else:
            return Lang_Object_Impl(xml_lang_file_path)

    class Xml_Language_File_Does_Not_Exist(Exception):
        pass


class Lang_Object_NULL(Lang_Object):

    def __init__(self, *args) -> None:
        pass

    def label(self, *path) -> str:
        return path[-1]


class Lang_Object_Impl(Lang_Object):

    def __init__(self, xml_lang_file_path: str) -> None:
        if not os.path.isfile(xml_lang_file_path):
            raise Lang_Object.Xml_Language_File_Does_Not_Exist(xml_lang_file_path)
        self._root: et.Element = et.parse(xml_lang_file_path).getroot()

    def label(self, *path: str) -> str:
        item = self._root
        for p in path:
            item = item.find(p)
            if item is None:
                return path[-1]
        try:
            return item.attrib["Text"]
        except:
            return path[-1]
