from __future__ import annotations
import sys
import unittest
from typing import Any, Callable, Dict, Set, Tuple

sys.path.insert(1, "src")

from te_tree.core.item import Item
from te_tree.core.editor import new_editor, blank_case_template
from te_tree.core.editor import EditorUI, Item_Menu, Item_Window, Case_View


class Item_Menu_Test(Item_Menu):

    def _build_menu(self, *args) -> None:
        pass

    def _destroy_menu(self) -> None:
        pass


class Item_Window_Test(Item_Window):
    def _build_window(self, *args) -> None:
        pass

    def _destroy_window(self) -> None:
        pass

    def configure(self, **kwargs) -> None:
        pass


class Case_View_Test(Case_View):

    @property
    def selected_items(self) -> Set(Item):
        return set()

    def configure(self, **kwargs) -> None:
        pass

    def is_in_view(self, item_id: str) -> bool:
        return True

    def tree_row_values(self, item_id: str) -> Dict[str, Any]:
        return {}

    def on_selection_change(self, func: Callable[[], None]) -> None:
        pass


class Editor_UI_Test(EditorUI):

    def _compose(self) -> None:
        pass

    def _get_export_dir(self) -> str:
        return ""

    def _get_xml_path(self) -> Tuple[str, str]:
        return ("", "")


class Test_Item_Menu(unittest.TestCase):

    def setUp(self) -> None:
        case_template = blank_case_template()
        case_template.add(
            "Parent",
            {"x": case_template.attr.integer(0)},
            child_template_labels=("Child",),
        )
        case_template.add("Child", {"x": case_template.attr.integer(0)}, ())
        self.editor = new_editor(case_template)
        self.menu = Item_Menu_Test(lang={})
        self.editor_ui = Editor_UI_Test(
            self.editor, self.menu, Item_Window_Test(), Case_View_Test()
        )

    def test_opening_and_closing_action_menu(self):
        self.assertFalse(self.menu.is_open)
        self.editor_ui.open_item_menu(self.editor.root)
        self.assertTrue(self.menu.is_open)
        self.menu.close()
        self.assertFalse(self.menu.is_open)

    def test_menu_does_not_open_if_no_actions_are_provided(self):
        self.menu.open(Item_Menu_Cmds())
        self.assertFalse(self.menu.is_open)

    def test_creating_new_case_via_item_menu_opened_for_editor_root_item(self) -> None:
        self.editor_ui.open_item_menu(self.editor.root)
        self.assertTrue("new_case" in self.menu.action_labels())
        self.menu.run("new_case")
        self.assertEqual(self.editor.ncases, 1)

    def test_menu_closes_after_running_command(self):
        self.editor_ui.open_item_menu(self.editor.root)
        self.menu.run("new_case")
        self.assertFalse(self.menu.is_open)

    def test_opening_item_menu_for_nonexistent_case_raises_exception(self):
        self.assertRaises(
            EditorUI.Opening_Item_Menu_For_Nonexistent_Item,
            self.editor_ui.open_item_menu,
            self.editor.root.pick_child("Nonexistent case"),
        )

    def test_running_the_command_destroy_the_menu_and_empties_the_actions(self):
        self.menu.open(Item_Menu_Cmds({"command 1": lambda: None}))
        self.assertTrue(self.menu.is_open)
        self.assertListEqual(self.menu.action_labels(), ["command 1"])

        self.menu.run("command 1")
        self.assertFalse(self.menu.is_open)
        self.assertTrue(self.menu.actions is None)

    def test_accessing_second_level_menu_command(self):
        self.x = 1

        def command_on_2nd_level():
            self.x = 89

        self.menu.open(Item_Menu_Cmds({"Some Command": lambda: None}))  # pragma: no cover
        self.menu.actions.insert({"Command on 2nd level": command_on_2nd_level}, "group")
        self.menu.run("Command on 2nd level", "group")
        self.assertEqual(self.x, 89)


from te_tree.core.editor import Item_Menu_Cmds


class Test_Defining_Cascade_Menu(unittest.TestCase):

    def setUp(self) -> None:
        self.menu = Item_Menu_Test(lang={})
        self.cmd_tree = Item_Menu_Cmds()

    def test_cascade_menu_for_single_level_of_commands(self):
        cmds = {
            "command 1": lambda: None,
            "command 2": lambda: None,
        }  # pragma: no cover
        self.cmd_tree.insert(cmds)

        self.assertListEqual(self.cmd_tree.labels(), ["command 1", "command 2"])
        self.assertListEqual(self.cmd_tree.labels("command 1"), [])

    def test_cascade_menu_with_commands_on_second_level_of_menu_hierarchy(self):
        cmds = {
            "command 1": lambda: None,
            "command 2": lambda: None,
        }  # pragma: no cover
        self.cmd_tree.insert(cmds, "cmd group 1")

        self.assertListEqual(self.cmd_tree.labels(), ["cmd group 1"])
        self.assertListEqual(self.cmd_tree.labels("cmd group 1"), ["command 1", "command 2"])

    def test_cascade_menu_with_commands_on_second_level_of_menu_hierarchy_and_two_on_first(
        self,
    ):
        cmds_1st_level = {
            "command 1": lambda: None,
            "command 2": lambda: None,
        }  # pragma: no cover
        cmds_2nd_level = {
            "command 2.1": lambda: None,
            "command 2.2": lambda: None,
        }  # pragma: no cover

        self.cmd_tree.insert(cmds_2nd_level, "cmd group")
        self.cmd_tree.insert(cmds_1st_level)

        self.assertListEqual(self.cmd_tree.labels(), ["cmd group", "command 1", "command 2"])
        self.assertListEqual(self.cmd_tree.labels("cmd group"), ["command 2.1", "command 2.2"])

    def test_groups_without_commands_are_skipped(self):
        self.cmd_tree.insert({"cmd 1": lambda: None}, "nonempty cmd group")  # pragma: no cover
        self.cmd_tree.insert({}, "empty cmd group")
        self.assertListEqual(self.cmd_tree.labels(), ["nonempty cmd group"])

    def test_three_level_hierarchy(self):
        cmds_1st_level = {
            "command 1": lambda: None,
            "command 2": lambda: None,
        }  # pragma: no cover
        cmds_2nd_level = {
            "command 2.1": lambda: None,
            "command 2.2": lambda: None,
        }  # pragma: no cover
        cmds_3rd_level = {
            "command 3.1": lambda: None,
            "command 3.2": lambda: None,
        }  # pragma: no cover

        self.cmd_tree.insert(cmds_3rd_level, "cmd group", "cmd subgroup")
        self.cmd_tree.insert(cmds_2nd_level, "cmd group")
        self.cmd_tree.insert(cmds_1st_level)

        self.assertListEqual(self.cmd_tree.labels(), ["cmd group", "command 1", "command 2"])
        self.assertListEqual(
            self.cmd_tree.labels("cmd group"),
            ["cmd subgroup", "command 2.1", "command 2.2"],
        )
        self.assertListEqual(
            self.cmd_tree.labels("cmd group", "cmd subgroup"),
            ["command 3.1", "command 3.2"],
        )

    def test_accessing_commands_under_nonexistent_menu_label_returns_empty_list(self):
        self.assertListEqual(self.cmd_tree.labels("nonexistent group"), list())


class Test_Item_Window(unittest.TestCase):

    def setUp(self) -> None:
        case_template = blank_case_template()
        case_template.add(
            "Parent",
            {"x": case_template.attr.integer(0)},
            child_template_labels=("Child",),
        )
        case_template.add_case_child_label("Parent")
        case_template.add("Child", {"x": case_template.attr.integer(0)}, ())
        self.editor = new_editor(case_template)
        self.menu = Item_Menu_Test(lang={})
        self.item_win = Item_Window_Test()
        self.editor_ui = Editor_UI_Test(
            self.editor, self.menu, self.item_win, Case_View_Test(), lang={}
        )
        self.new_case = self.editor.new_case("Case X")
        self.item = self.editor.new(self.new_case, "Parent")

    def test_open_and_close_item_window_for_case(self):
        self.assertFalse(self.item_win.is_open)
        self.editor_ui.open_item_window(self.new_case)
        self.assertTrue(self.item_win.is_open)

    def test_opening_window_for_item_under_new_case(self):
        self.editor_ui.open_item_menu(self.item)
        self.menu.run("edit")
        self.assertTrue(self.item_win.is_open)
        self.item_win.close()
        self.assertFalse(self.item_win.is_open)

    def test_command_labels_are_empty_list_if_no_commands_provided_via_Item_Menu_Cmds(
        self,
    ):
        self.menu = Item_Menu_Test(lang={})
        self.menu.open(Item_Menu_Cmds())
        self.assertListEqual(self.menu.action_labels(), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
