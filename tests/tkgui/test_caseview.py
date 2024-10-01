from __future__ import annotations
import sys

sys.path.insert(1, "src")


import unittest
import tkinter as tk
from te_tree.tkgui.caseview import Case_View_Tk
from te_tree.core.item import ItemCreator


class Test_View_For_Empty_Editor(unittest.TestCase):

    def setUp(self):
        root = tk.Tk()
        self.cr = ItemCreator()
        self.root_item = self.cr.new("Root item")
        self.caseview = Case_View_Tk(root, self.root_item)

    def test_case_view_initially_contains_no_items(self):
        self.assertTrue(self.caseview.widget.winfo_exists())
        self.assertEqual(self.caseview.widget.get_children(""), ())


class Test_View_For_Item_Manipulations(unittest.TestCase):

    def setUp(self):
        root = tk.Tk()
        self.cr = ItemCreator()
        self.root_item = self.cr.new("Root item")
        self.caseview = Case_View_Tk(root, self.root_item)

    def test_new_child_is_shown_in_treeview(self):
        child = self.cr.new(
            "Child",
        )
        self.assertEqual(len(self.caseview.widget.get_children("")), 0)
        self.root_item.adopt(child)
        self.assertEqual(len(self.caseview.widget.get_children("")), 1)
        self.cr.undo()
        self.assertEqual(len(self.caseview.widget.get_children("")), 0)

    def test_child_treeview_iid_is_equal_to_child_id(self):
        child = self.cr.new("Child")
        self.root_item.adopt(child)
        self.assertEqual(self.caseview.widget.get_children("")[0], child.id)

    def test_new_grandchild_is_shown_in_caseview_under_its_parent(self):
        child = self.cr.new("Child")
        self.root_item.adopt(child)
        self.assertEqual(self.root_item.last_action, (self.root_item.name, "adopt", child.name))
        grandchild = self.cr.new("Grandchild")
        child.adopt(grandchild)
        self.assertEqual(child.last_action, (child.name, "adopt", grandchild.name))
        self.assertEqual(len(self.caseview.widget.get_children(child.id)), 1)

    def test_renaming_item_is_reflected_in_caseview(self):
        child = self.cr.new("Child")
        self.root_item.adopt(child)
        self.assertEqual(self.caseview.widget.item(child.id)["text"], "Child")
        child.rename("The Child")
        self.assertEqual(child.last_action, (child.name, "rename", child.name))
        self.assertEqual(self.caseview.widget.item(child.id)["text"], "The Child")
        self.cr.undo()
        self.assertEqual(self.caseview.widget.item(child.id)["text"], "Child")

    def test_removing_parent_with_child(self):
        parent = self.cr.new("Parent")
        self.root_item.adopt(parent)
        child = self.cr.new("Child")
        parent.adopt(child)

        self.root_item.leave(parent)
        self.cr.undo()

        self.assertEqual(self.caseview.widget.item(parent.id)["text"], "Parent")
        self.assertTrue(parent.is_parent_of(child))
        self.assertEqual(self.caseview.widget.item(child.id)["text"], "Child")


class Test_View_For_Item_Attribute_Manipulations(unittest.TestCase):

    def setUp(self):
        root = tk.Tk()
        self.cr = ItemCreator()
        self.root_item = self.cr.new("Root item")
        self.caseview = Case_View_Tk(
            root,
            self.root_item,
            attrs_for_display={"y": ("y",), "description": ("description",)},
        )

    def test_displayed_attributes_in_the_tree_correspond_to_values_of_newly_added_item(
        self,
    ):
        child = self.cr.new("Child", {"y": "integer", "description": "text"})
        child.set("y", 5)
        child.set("description", "some text")
        self.root_item.adopt(child)
        self.assertEqual(self.caseview.widget.item(child.id)["values"], [5, "some text"])

    def test_changing_value_of_the_item_is_reflected_in_treeview(self):
        child = self.cr.new("Child", {"y": "integer"})
        child.set("y", 7)
        self.root_item.adopt(child)
        self.assertEqual(self.caseview.widget.item(child.id)["values"], [7, ""])
        child.set("y", 9)
        self.assertEqual(self.caseview.widget.item(child.id)["values"], [9, ""])

    def test_setting_attributes_not_included_in_caseview_has_no_effect(self):
        child = self.cr.new("Child", {"y": "integer", "z": "integer"})
        self.root_item.adopt(child)
        child.set("y", 4)
        child.set("z", 8)
        self.assertEqual(self.caseview.widget.item(child.id)["values"], [4, ""])

    def test_displayed_values_of_dependent_attributes_are_automatically_updated(self):
        child = self.cr.new("Child", {"x": "integer", "y": "integer"})
        self.root_item.adopt(child)
        child.set("x", 0)
        child.bind("y", lambda x: 2 * x, "x")
        child.set("x", 3)
        self.assertEqual(self.caseview.widget.item(child.id)["values"], [6, ""])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
