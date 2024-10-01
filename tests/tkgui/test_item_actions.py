from __future__ import annotations
import sys

sys.path.insert(1, "src")


import unittest
import tkinter as tk

from te_tree.tkgui.item_actions import Item_Window_Tk
from te_tree.core.item import ItemCreator


class Test_Item_Window(unittest.TestCase):

    def setUp(self) -> None:
        self.cr = ItemCreator()
        self.root = tk.Tk()
        self.win = Item_Window_Tk(self.root)
        self.root.grab_release()
        self.item = self.cr.new("Item", {"x": "integer", "y": "real"})

    def test_opening_and_closing_window(self) -> None:
        self.win.open(self.item)
        self.assertTrue(self.win.is_open)
        self.assertTrue(len(self.win.entries) == 3)

        self.win.close()
        self.assertFalse(self.win.is_open)
        self.assertTrue(len(self.win.entries) == 0)

    def test_setting_attributes_and_confirming_changes_closes_the_window_and_sets_the_attributes_to_new_values(
        self,
    ) -> None:
        self.item.multiset({"x": 1, "y": 2})
        self.win.open(self.item)
        self.win.entries[1].set(2)
        self.win.entries[2].set(-1)
        self.win.ok()

        self.assertFalse(self.win.is_open)
        self.assertListEqual(self.win.entries, [])

        self.assertEqual(self.item("x"), 2)
        self.assertEqual(self.item("y"), -1)
        self.cr.undo()
        self.assertEqual(self.item("x"), 1)
        self.assertEqual(self.item("y"), 2)

    def test_reverting_changes_done_in_the_item_window(self):
        self.item.multiset({"x": 1, "y": 2})
        self.win.open(self.item)
        self.win.entries[1].set(2)
        self.win.entries[2].set(-1)
        self.assertEqual(self.win.entries[1].value, "2")
        self.assertEqual(self.win.entries[2].value, "-1")
        self.win.revert()
        self.assertTrue(self.win.is_open)
        self.assertEqual(self.win.entries[1].value, "1")
        self.assertEqual(self.win.entries[2].value, "2")

    def test_cancelling_changes_done_in_the_item_window_closes_the_window_and_keeps_the_attributes_and_their_original_values(
        self,
    ):
        self.item.multiset({"x": 1, "y": 2})
        self.win.open(self.item)
        self.win.entries[1].set(2)
        self.win.entries[2].set(-1)
        self.assertEqual(self.win.entries[1].value, "2")
        self.assertEqual(self.win.entries[2].value, "-1")
        self.win.cancel()
        self.assertFalse(self.win.is_open)
        self.assertListEqual(self.win.entries, [])

    def test_bound_attributes_are_included_in_item_window(self):
        self.item.bind("y", lambda x: 2 * x, "x")
        self.win.open(self.item)
        self.assertEqual(len(self.win.entries), 3)


from te_tree.tkgui.item_actions import Item_Menu_Tk
from te_tree.core.editor import Item_Menu_Cmds


class Test_Item_Menu(unittest.TestCase):

    def setUp(self) -> None:
        self.cr = ItemCreator()
        self.root = tk.Tk()
        self.menu = Item_Menu_Tk(self.root)
        self.item = self.cr.new("Item", {"x": "integer", "y": "real"})
        self.x = 0
        self.y = 0

        def add_1_to_x():
            self.x += 1  # pragma: no cover

        def add_1_to_y():
            self.y += 1  # pragma: no cover

        self.actions = Item_Menu_Cmds({"Add 1 to x": add_1_to_x, "Add 1 to y": add_1_to_y})

    def test_opening_menu_with_custom_actions(self) -> None:
        self.menu.open(self.actions)
        last_menu_item_index = self.menu.widget.index("end")
        self.assertEqual(last_menu_item_index, 1)
        self.menu.widget.invoke(1)
        self.assertEqual(self.x, 0)
        self.assertEqual(self.y, 1)

    def test_tk_menu_is_destroyed_after_running_the_command(self):
        self.menu.open(self.actions)
        self.menu.widget.invoke(1)
        self.assertFalse(self.menu.is_open)
        self.assertFalse(self.menu.widget.winfo_exists())

    def test_cascade_actions(self):
        actions = Item_Menu_Cmds()
        actions.insert({"Cmd 1": lambda: None})  # pragma: no cover
        actions.insert(
            {"Cmd 2.1": lambda: None, "Cmd 2.2": lambda: None}, "group"
        )  # pragma: no cover
        actions.insert({}, "empty group")  # pragma: no cover
        actions.insert({"Cmd 2": lambda: None})  # pragma: no cover
        self.menu.open(actions)

        self.assertEqual(self.menu.widget.index("end"), 2)
        self.assertEqual(self.menu.widget.winfo_children()[0].index("end"), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
