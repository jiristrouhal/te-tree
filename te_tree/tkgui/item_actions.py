import tkinter as tk
from typing import Optional, Any

from te_tree.tkgui.attr_entries import Entry_Creator, Attribute_Entry
from te_tree.core.attributes import Attribute
from te_tree.core.editor import Item_Menu, Item_Window, Lang_Object


class Item_Window_Tk(Item_Window):

    def __init__(
        self, root: Optional[tk.Tk | tk.Frame], lang: Optional[Lang_Object] = None
    ) -> None:
        super().__init__(lang)
        self._root = root
        self._win = tk.Toplevel(root)
        self._ecr = Entry_Creator()
        self._win.withdraw()

    @property
    def entries(self) -> list[Attribute_Entry]:
        return self._entries.copy()

    def _build_window(self, attributes: dict[str, Attribute]):
        self._win = tk.Toplevel(self._root)
        self._win.title(self.title)
        self._create_entries(attributes)
        self._create_button_frame()
        try:
            self._win.grab_set()
        except:
            pass

    def _destroy_window(self):
        self._win.grab_release()
        self._win.destroy()
        self._entries.clear()

    def configure(self, **kwargs) -> None:
        for label, arg in kwargs.items():
            match label:
                case _:
                    continue

    def ok(self) -> None:
        self._win.nametowidget("button_frame").nametowidget("ok").invoke()

    def revert(self) -> None:
        self._win.nametowidget("button_frame").nametowidget("revert").invoke()

    def cancel(self) -> None:
        self._win.nametowidget("button_frame").nametowidget("cancel").invoke()

    def _ok(self) -> None:
        confirmed_vals: dict[Attribute, Any] = dict()
        for entry in self._entries:
            confirmed_vals[entry.attr] = entry._confirmed_value()

        Attribute.set_multiple({entry.attr: confirmed_vals[entry.attr] for entry in self._entries})
        self.close()

    def _revert(self) -> None:
        for entry in self._entries:
            entry.revert()

    def _cancel(self) -> None:
        self.close()

    def _create_entries(self, attrs: dict[str, Attribute]) -> None:
        """Create entries for attributes without assigned dependencies."""
        frame = tk.Frame(self._win)
        row = 0
        self._entries: list[Attribute_Entry] = list()
        for label, attr in attrs.items():
            self._add_attr(label, attr, row, frame)
            row += 1
        frame.pack(side=tk.TOP, expand=2, fill=tk.BOTH)

    def _add_attr(self, label: str, attr: Attribute, row: int, frame: tk.Frame) -> None:
        attr_name = tk.Label(frame, text=self.lang.label("Item_Attributes", label))
        entry = self._ecr.new(attr, frame)
        attr_name.grid(column=0, row=row, sticky=tk.E)
        entry.widget.grid(column=1, row=row, sticky=tk.W)
        self._entries.append(entry)

    def _create_button_frame(self) -> None:
        bf = tk.Frame(self._win, name="button_frame")
        tk.Button(
            bf,
            text=self.lang("Item_Window", "Revert"),
            command=lambda: self._revert(),
            name="revert",
        ).grid(row=0, column=0)
        tk.Button(
            bf,
            text=self.lang("Item_Window", "OK"),
            command=lambda: self._ok(),
            name="ok",
        ).grid(row=0, column=1)
        tk.Button(
            bf,
            text=self.lang("Item_Window", "Cancel"),
            command=lambda: self._cancel(),
            name="cancel",
        ).grid(row=0, column=2)
        bf.pack(side=tk.BOTTOM)


from te_tree.core.editor import Item_Menu_Cmds, Lang_Object
from functools import partial


class Item_Menu_Tk(Item_Menu):

    def __init__(
        self, root: tk.Tk | tk.Frame, lang: Lang_Object = Lang_Object.get_lang_object()
    ) -> None:
        self.__parent_widget = root
        super().__init__(lang=lang)
        self._widget = tk.Menu()

    @property
    def widget(self) -> tk.Menu:
        return self._widget

    def _build_menu(self, event: Optional[tk.Event] = None, *args) -> None:
        assert self.actions is not None
        self._widget = self._menu_cascade(self.__parent_widget, self.actions)
        if event is not None:
            self._widget.tk_popup(event.x_root, event.y_root)

    def _menu_cascade(
        self, parent: tk.Tk | tk.Menu | tk.Frame, actions: Item_Menu_Cmds
    ) -> tk.Menu:
        menu = tk.Menu(parent, tearoff=0)
        for label, func in actions.items.items():
            if callable(func):
                menu.add_command(
                    label=self.lang.label("Item_Menu", label),
                    command=partial(actions.run, label),
                )
            elif func is None:
                menu.add_separator()
            else:
                assert type(func) == type(actions)
                submenu = self._menu_cascade(menu, func)
                menu.add_cascade(label=self.lang.label("Item_Menu", label), menu=submenu)
        return menu

    def _destroy_menu(self) -> None:
        self._widget.destroy()
