import tkinter as tk
from typing import Optional, Dict, Any
from te_tree.tkgui.attr_entries import Entry_Creator, Attribute_Entry
from te_tree.core.attributes import Attribute


from typing import List
from te_tree.core.editor import Item_Menu, Item_Window, Lang_Object


class Item_Window_Tk(Item_Window):

    def __init__(
        self, root: Optional[tk.Tk | tk.Frame], lang: Optional[Lang_Object] = None
    ) -> None:
        super().__init__(lang)
        self.__root = root
        self.__win = tk.Toplevel(root)
        self.__ecr = Entry_Creator()
        self.__win.withdraw()

    @property
    def entries(self) -> List[Attribute_Entry]:
        return self.__entries.copy()

    def _build_window(self, attributes: Dict[str, Attribute]):
        self.__win = tk.Toplevel(self.__root)
        self.__win.title(self.title)
        self.__create_entries(attributes)
        self.__create_button_frame()
        try:
            self.__win.grab_set()
        except:
            pass

    def _destroy_window(self):
        self.__win.grab_release()
        self.__win.destroy()
        self.__entries.clear()

    def configure(self, **kwargs) -> None:
        for label, arg in kwargs.items():
            match label:
                case _:
                    continue

    def ok(self) -> None:
        self.__win.nametowidget("button_frame").nametowidget("ok").invoke()

    def revert(self) -> None:
        self.__win.nametowidget("button_frame").nametowidget("revert").invoke()

    def cancel(self) -> None:
        self.__win.nametowidget("button_frame").nametowidget("cancel").invoke()

    def __ok(self) -> None:
        confirmed_vals: Dict[Attribute, Any] = dict()
        for entry in self.__entries:
            confirmed_vals[entry.attr] = entry._confirmed_value()

        Attribute.set_multiple({entry.attr: confirmed_vals[entry.attr] for entry in self.__entries})
        self.close()

    def __revert(self) -> None:
        for entry in self.__entries:
            entry.revert()

    def __cancel(self) -> None:
        self.close()

    def __create_entries(self, attrs: Dict[str, Attribute]) -> None:
        """Create entries for attributes without assigned dependencies."""
        frame = tk.Frame(self.__win)
        row = 0
        self.__entries: List[Attribute_Entry] = list()
        for label, attr in attrs.items():
            self.__add_attr(label, attr, row, frame)
            row += 1
        frame.pack(side=tk.TOP, expand=2, fill=tk.BOTH)

    def __add_attr(self, label: str, attr: Attribute, row: int, frame: tk.Frame) -> None:
        attr_name = tk.Label(frame, text=self.lang.label("Item_Attributes", label))
        entry = self.__ecr.new(attr, frame)
        attr_name.grid(column=0, row=row, sticky=tk.E)
        entry.widget.grid(column=1, row=row, sticky=tk.W)
        self.__entries.append(entry)

    def __create_button_frame(self) -> None:
        bf = tk.Frame(self.__win, name="button_frame")
        tk.Button(
            bf,
            text=self.lang("Item_Window", "Revert"),
            command=lambda: self.__revert(),
            name="revert",
        ).grid(row=0, column=0)
        tk.Button(
            bf,
            text=self.lang("Item_Window", "OK"),
            command=lambda: self.__ok(),
            name="ok",
        ).grid(row=0, column=1)
        tk.Button(
            bf,
            text=self.lang("Item_Window", "Cancel"),
            command=lambda: self.__cancel(),
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
        self.__widget = tk.Menu()

    @property
    def widget(self) -> tk.Menu:
        return self.__widget

    def _build_menu(self, event: Optional[tk.Event] = None, *args) -> None:
        assert self.actions is not None
        self.__widget = self.__menu_cascade(self.__parent_widget, self.actions)
        if event is not None:
            self.__widget.tk_popup(event.x_root, event.y_root)

    def __menu_cascade(
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
                submenu = self.__menu_cascade(menu, func)
                menu.add_cascade(label=self.lang.label("Item_Menu", label), menu=submenu)
        return menu

    def _destroy_menu(self) -> None:
        self.__widget.destroy()
