import tkinter.ttk as ttk
import tkinter as tk
from functools import partial
from typing import Callable, Any, Optional
import os

from PIL import Image, ImageTk  # type: ignore

from te_tree.core.editor import Case_View, Lang_Object, Item


class Case_View_Tk(Case_View):

    def __init__(
        self,
        window: tk.Tk | tk.Frame,
        root_item: Item,
        attrs_for_display: dict[str, tuple[str, ...]] | None = None,
        lang: Lang_Object = Lang_Object.get_lang_object(),
        icons: dict[str, str] | None = None,
    ) -> None:

        if attrs_for_display is None:
            attrs_for_display = {}
        if icons is None:
            icons = {}
        style = ttk.Style(window)
        style.configure("Treeview", indent=10)

        self._tree: ttk.Treeview = ttk.Treeview(window)
        self._icons = {label: self._get_icon(path) for label, path in icons.items()}
        collected_icons = self._icons.copy()
        for label, icon in collected_icons.items():
            if icon is None:
                self._icons.pop(label)
        yscrollbar = ttk.Scrollbar(window, orient="vertical", command=self._tree.yview)
        yscrollbar.pack(anchor=tk.W, fill=tk.Y, side=tk.LEFT)
        self._tree.configure(yscrollcommand=yscrollbar, height=25)

        self._id = str(id(self))
        self._lang = lang

        self._tree["columns"] = list(attrs_for_display.keys())
        self._attrs_for_display = attrs_for_display
        self._precision: int = 28
        self._trailing_zeros: bool = False
        self._use_thousands_separator: bool = False

        root_item.add_action(self._id, "adopt", self._new_item_under_root)
        root_item.add_action(self._id, "leave", self._remove_item)
        root_item.add_action(self._id, "rename", self._rename_item)
        root_item.add_action_on_set(self._id, self._set_displayed_values_of_item_attributes)

        self._tree.bind("<<TreeviewSelect>>", self._handle_selection_change)
        self._tree.bind("<Escape>", lambda e: self._selection_clear())
        self._tree.bind("<Down> <Up>", lambda e: self._reselect_last())

        self._item_dict: dict[str, Item] = {"": root_item}
        self._set_up_headings()
        self._reversed_sort: bool = False
        self._on_selection_change: list[Callable[[], None]] = list()

        self._last_selection: str = ""

    @property
    def id(self) -> str:
        return self._id

    @property
    def widget(self) -> ttk.Treeview:
        return self._tree

    @property
    def selected_items(self) -> set[Item]:
        return {self._item_dict[item_id] for item_id in self._tree.selection()}

    def bind(self, sequence: str, action: Callable[[tk.Event], None]) -> None:
        self._tree.bind(sequence, action)

    def configure(self, **kwargs) -> None:
        for label, arg in kwargs.items():
            match label:
                case "precision":
                    self._precision = arg
                case "trailing_zeros":
                    self._trailing_zeros = arg
                case "use_thousands_separator":
                    self._use_thousands_separator = arg
                case _:
                    continue

    def do_on_tree_item(
        self, action: Callable[[Item, tk.Event], None]
    ) -> Callable[[tk.Event], None]:
        def item_action(event: tk.Event) -> None:
            tree_item_iid = self._tree.identify_row(event.y)
            item = self._item_dict[tree_item_iid]
            return action(item, event)

        return item_action

    def is_in_view(self, item_id: str) -> bool:
        return item_id in self._item_dict

    def on_selection_change(self, func: Callable[[], None]) -> None:
        self._on_selection_change.append(func)
        selection = self._tree.selection()
        if selection:
            self._last_selection = selection[-1]
        else:
            self._last_selection = ""

    def tree_row_values(self, item_id: str) -> dict[str, Any]:
        vals: dict[str, Any] = dict()
        for label, value in zip(self._tree["columns"], self._tree.item(item_id)["values"]):
            vals[label] = value
        return vals

    def _collect_and_set_values(self, item: Item) -> list[str]:
        values: list[str] = list()
        for label_group in self._attrs_for_display:
            values.append("")
            for label in self._attrs_for_display[label_group]:
                if item.has_attribute(label):
                    attr = item.attribute(label)
                    print_args: dict[str, Any] = dict()
                    if attr.type == "real" or attr.type == "quantity":
                        print_args["precision"] = self._precision
                        print_args["trailing_zeros"] = self._trailing_zeros
                    elif attr.type == "money":
                        print_args["use_thousands_separator"] = self._use_thousands_separator
                    values[-1] = str(item.attribute(label).print(**print_args))
                    break
        return values

    def _get_icon(self, path: str) -> Optional[ImageTk.PhotoImage]:
        if os.path.isfile(path):
            return ImageTk.PhotoImage(Image.open(path))
        else:
            return None

    def _handle_selection_change(self, event: tk.Event) -> None:
        for func in self._on_selection_change:
            func()

    def _new_item(self, item: Item) -> None:
        values = self._collect_and_set_values(item)
        item_iid = self._tree.insert(
            item.parent.id,
            index=tk.END,
            iid=item.id,
            text=item.name,
            values=values,
        )
        if item.itype in self._icons:
            self._tree.item(item_iid, image=self._icons[item.itype])

        item.add_action(self._id, "adopt", self._new_item)
        item.add_action(self._id, "leave", self._remove_item)
        item.add_action(self._id, "rename", self._rename_item)
        item.add_action_on_set(self._id, self._set_displayed_values_of_item_attributes)
        self._item_dict[item.id] = item

        for child in item.children:
            self._new_item(child)

    def _new_item_under_root(self, item: Item) -> None:
        values = self._collect_and_set_values(item)
        self._tree.insert("", index=tk.END, iid=item.id, text=item.name, values=values)
        item.add_action(self._id, "adopt", self._new_item)
        item.add_action(self._id, "leave", self._remove_item)
        item.add_action(self._id, "rename", self._rename_item)
        item.add_action_on_set(self._id, self._set_displayed_values_of_item_attributes)
        self._item_dict[item.id] = item
        for child in item.children:
            self._new_item(child)

    def _pick_attr_label_from_attrs_assigned_to_caseview_column(
        self, item: Item, column_label: str
    ) -> str:
        if column_label not in self._attrs_for_display:
            raise Case_View_Tk.Undefined_Column_Label(column_label)
        else:
            for attr in self._attrs_for_display[column_label]:
                if item.has_attribute(attr):
                    return attr
        # item has no attribute corresponding to the caseview column 'column_label'
        return ""

    def _remove_item(self, item: Item) -> None:
        for child in item.children:
            self._remove_item(child)
        self._tree.delete(item.id)
        item.remove_action(self._id, "adopt")
        item.remove_action(self._id, "leave")
        item.remove_action(self._id, "rename")
        item.remove_action_on_set(self._id)
        self._item_dict.pop(item.id)

    def _rename_item(self, item: Item) -> None:
        self._tree.item(item.id, text=item.name)

    def _set_displayed_values_of_item_attributes(self, item: Item) -> None:
        values = self._collect_and_set_values(item)
        self._tree.item(item.id, values=values)

    def _selection_clear(self) -> None:
        self._tree.selection_set([])

    def _reselect_last(self):
        if self._tree.selection() and self._tree.selection() != [""]:
            return
        elif self._last_selection == "" and self._tree.get_children(""):
            self._tree.selection_set(self._tree.get_children("")[0])
        elif self._last_selection in self._item_dict:
            self._tree.selection_set(self._last_selection)

    def _set_up_headings(self) -> None:
        heading_labels = list(self._tree["columns"])
        for heading_label in heading_labels:
            self._tree.heading(
                heading_label,
                text=self._lang("Item_Attributes", heading_label),
                command=partial(self._sort_all_by, heading_label),
                anchor=tk.CENTER,
            )
            self._tree.column(heading_label, anchor=tk.E, minwidth=50, width=100)
        self._tree.heading(
            "#0",
            text=self._lang("Item_Attributes", "name"),
            command=partial(self._sort_all_by, "#0"),
            anchor=tk.CENTER,
        )
        self._tree.column("#0", minwidth=100, width=300)

    def _sort_all_by(self, column_label: str) -> None:
        selection = self._tree.selection()
        if not selection:
            parent_iid = ""
        else:
            parent_iid = self._tree.parent(selection[-1])
        self._sort_by(column_label, parent_iid=parent_iid)
        self._reversed_sort = not self._reversed_sort

    def _sort_by(self, column_label: str, parent_iid: str) -> None:
        if column_label == "#0":
            child_data = [
                (c, self._tree.item(c)["text"]) for c in self._tree.get_children(parent_iid)
            ]
            child_data.sort(key=lambda x: x[1], reverse=self._reversed_sort)
        else:
            child_data: list[str, Any] = list()
            empty_child_data: list[str, Any] = list()
            for item_id in self._tree.get_children(parent_iid):
                item = self._item_dict[item_id]
                attr_label = self._pick_attr_label_from_attrs_assigned_to_caseview_column(
                    item, column_label
                )
                if attr_label == "":
                    empty_child_data.append((item_id, None))
                else:
                    child_data.append((item_id, item(attr_label)))

            child_data.sort(key=lambda x: x[1], reverse=self._reversed_sort)
            child_data.extend(empty_child_data)

        for index, (c, _) in enumerate(child_data):
            self._tree.move(c, parent_iid, index)


    class Undefined_Column_Label(Exception):
        pass
