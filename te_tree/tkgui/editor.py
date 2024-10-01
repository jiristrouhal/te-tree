import tkinter as tk

from te_tree.core.editor import EditorUI, Editor, Lang_Object
from te_tree.tkgui.item_actions import Item_Menu_Tk, Item_Window_Tk
from te_tree.tkgui.caseview import Case_View_Tk

from typing import Tuple, Dict
from tkinter.filedialog import askopenfilename, askdirectory
import os


class Editor_Tk(EditorUI):

    def __init__(
        self,
        editor: Editor,
        master_window: tk.Tk | tk.Frame,
        displayable_attributes: Dict[str, Tuple[str, ...]],
        lang: Lang_Object,
        icons: Dict[str, str] = {},
    ) -> None:

        self.__editor = editor
        self.__win = master_window
        self.__item_window = Item_Window_Tk(self.__win, lang=lang)
        self.__item_menu = Item_Menu_Tk(self.__win, lang=lang)
        self.__caseview: Case_View_Tk = Case_View_Tk(
            self.__win, editor.root, displayable_attributes, lang=lang, icons=icons
        )
        super().__init__(editor, self.__item_menu, self.__item_window, self.__caseview, lang=lang)

    def _compose(self) -> None:  # pragma: no cover
        self.__caseview.widget.pack(expand=1, fill=tk.BOTH)
        self.__caseview.widget.bind(
            "<Button-3>", self.__caseview.do_on_tree_item(self.open_item_menu)
        )
        self.__caseview.widget.bind("<Double-Button-1>", self.__double_left_click_action)
        self.__caseview.widget.bind("<Control-z>", lambda e: self.__editor.undo())
        self.__caseview.widget.bind("<Control-y>", lambda e: self.__editor.redo())
        self.__caseview.widget.bind("<Delete>", self.__caseview.do_on_tree_item(self.delete_item))
        self.__caseview.widget.bind("<Control-c>", lambda e: self.__editor.copy_selection())
        self.__caseview.widget.bind("<Control-d>", lambda e: self.__editor.duplicate_selection())
        self.__caseview.widget.bind("<Control-v>", lambda e: self.__editor.paste_under_selection())
        self.__caseview.widget.bind("<Control-x>", lambda e: self.__editor.cut_selection())
        self.__caseview.widget.bind("<Control-g>", lambda e: self.__editor.group_selection())
        self.__caseview.widget.bind("<Control-G>", lambda e: self.__editor.ungroup_selection())
        self.__caseview.widget.bind("<Control-s>", lambda e: self.save_selected_cases_to_xml())

    def __double_left_click_action(self, event: tk.Event) -> str:
        self.__caseview.do_on_tree_item(self.open_item_window)(event)
        return "break"

    def _get_xml_path(self) -> Tuple[str, str]:
        case_full_path = askopenfilename(defaultextension="xml", filetypes=[("xml", "xml")])
        if case_full_path is None:
            return "", ""
        else:
            return (
                os.path.dirname(case_full_path),
                os.path.basename(case_full_path).split(".")[0],
            )

    def _get_export_dir(self) -> str:
        return askdirectory(initialdir=self.editor.export_dir_path)
