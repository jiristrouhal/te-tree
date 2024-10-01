from __future__ import annotations


import sys

sys.path.insert(1, "src")


import unittest
from te_tree.core.item import ItemCreator, Item, ItemImpl
import math, decimal


NullItem = ItemImpl.NULL


class Test_Naming_The_Item(unittest.TestCase):

    def setUp(self) -> None:
        self.iman = ItemCreator()

    def test_create_named_item(self):
        item = self.iman.new(name="Item 1")
        self.assertEqual(item.name, "Item 1")

    def test_leading_and_trailing_spaces_of_name_are_trimmed(self):
        item = self.iman.new(name="  Item A   ")
        self.assertEqual(item.name, "Item A")

    def test_create_item_with_empty_name_raises_error(self):
        self.assertRaises(Item.BlankName, self.iman.new, name="")

    def test_renaming_item(self):
        item = self.iman.new(name="Item B")
        item.rename(name="Item C")
        self.assertEqual(item.name, "Item C")

    def test_grouped_spaces_and_other_in_a_proposed_name_are_automatically_joined_into_single_space(
        self,
    ):
        item = self.iman.new(name="The      Item")
        self.assertEqual(item.name, "The Item")

        item.rename("New        name")
        self.assertEqual(item.name, "New name")

    def test_white_characters_are_replaced_with_spaces(self):
        for c in ("\n", "\t", "\r", "\v", "\f"):
            item = self.iman.new(name=f"New{c}name")
            self.assertEqual(item.name, "New name")

    def test_renaming_item_with_blank_name_raises_error(self):
        item = self.iman.new(name="Item A")
        self.assertRaises(Item.BlankName, item.rename, "    ")


class Test_NULL_Item(unittest.TestCase):

    def test_properties(self):
        self.assertDictEqual(NullItem.attributes, {})
        self.assertEqual(NullItem.name, "NULL")
        self.assertEqual(NullItem.parent, NullItem)
        self.assertEqual(NullItem.root, NullItem)

    def test_parent_child_relationships(self):
        self.assertTrue(NullItem.is_ancestor_of(NullItem))
        self.assertTrue(NullItem.is_parent_of(NullItem))

        self.assertTrue(NullItem.has_children())

        mg = ItemCreator()
        child = mg.new("Child")
        parent = mg.new("Parent")
        self.assertEqual(child.parent, NullItem)
        self.assertEqual(parent.parent, NullItem)
        NullItem.pass_to_new_parent(child, parent)
        self.assertEqual(child.parent, parent)

        self.assertEqual(NullItem.duplicate(), NullItem)

    def test_leaving_child_has_no_effect(self):
        mg = ItemCreator()
        child = mg.new("Child")
        self.assertTrue(NullItem.is_parent_of, child)
        NullItem._leave_child(child)
        self.assertTrue(NullItem.is_parent_of, child)

    def test_leaving_parent_has_no_effect(self):
        mg = ItemCreator()
        NullItem._leave_parent(NullItem)
        self.assertTrue(NullItem.is_parent_of, NullItem)

    def test_adding_null_item_under_a_nonnull_parent_raises_error(self):
        mg = ItemCreator()
        parent = mg.new("Parent")
        self.assertRaises(Item.AdoptingNULL, parent.adopt, NullItem)
        self.assertRaises(Item.AdoptingNULL, NullItem._accept_parent, parent)

    def test_adopting_child_by_null_is_equivalent_to_leaving_parent(self):
        mg = ItemCreator()
        child = mg.new("Child")
        parent = mg.new("Parent")
        parent.adopt(child)

        self.assertFalse(NullItem.is_parent_of(child))
        self.assertTrue(parent.is_parent_of(child))
        NullItem.adopt(child)
        self.assertTrue(NullItem.is_parent_of(child))
        self.assertFalse(parent.is_parent_of(child))

    def test_renaming(self):
        NullItem.rename("New Name")
        self.assertEqual(NullItem.name, "NULL")
        NullItem._rename("New Name")
        self.assertEqual(NullItem.name, "NULL")

    def test_adding_attributes_or_attribute_lists_raises_exceptino(self):
        self.assertRaises(
            NullItem.AddingAttributeToNullItem,
            NullItem._create_child_attr_list,
            "integer",
            "label",
        )

    def test_leaving_item_raises_exception(self) -> None:
        item = ItemCreator().new("Item")
        self.assertEqual(item.parent, NullItem)
        self.assertRaises(NullItem.NullCannotLeaveChild, NullItem.leave, item)

    def test_picking_child_on_null_raises_exception(self) -> None:
        self.assertRaises(
            NullItem.CannotAccessChildrenOfNull,
            NullItem.pick_child,
            "some child's name",
        )

    def test_setting_dependency_on_null_raises_exception(self) -> None:
        self.assertRaises(
            NullItem.SettingDependencyOnNull,
            NullItem.bind,
        )
        self.assertRaises(
            NullItem.SettingDependencyOnNull,
            NullItem.free,
        )

    def test_accessing_children_of_null_raises_exception(self):
        with self.assertRaises(NullItem.CannotAccessChildrenOfNull):
            NullItem.children


class Test_Accessing_Item_Attributes(unittest.TestCase):

    def setUp(self) -> None:
        self.iman = ItemCreator()
        self.item = self.iman.new("Item X", attr_info={"label_1": "integer", "label_2": "integer"})

    def test_defining_no_attributes(self) -> None:
        item = self.iman.new(name="Item X")
        self.assertDictEqual(item.attributes, {})

    def test_defining_attributes(self) -> None:
        self.assertEqual(list(self.item.attributes.keys()), ["label_1", "label_2"])


class Test_Undo_And_Redo_Renaming(unittest.TestCase):

    def test_single_undo_and_redo(self) -> None:
        mg = ItemCreator()
        item = mg.new(name="Apple")
        item.rename("Orange")
        mg.undo()
        self.assertEqual(item.name, "Apple")
        mg.redo()
        self.assertEqual(item.name, "Orange")
        mg.undo()
        self.assertEqual(item.name, "Apple")


class Test_Setting_Parent_Child_Relationship(unittest.TestCase):

    def setUp(self) -> None:
        self.iman = ItemCreator()
        self.parent = self.iman.new(name="Parent")
        self.child = self.iman.new(name="Child")
        self.parent.adopt(self.child)

    def test_children_were_added(self):
        not_a_child = self.iman.new(name="Not a Child")
        self.assertTrue(self.parent.is_parent_of(self.child))
        self.assertFalse(self.parent.is_parent_of(not_a_child))
        self.assertEqual(self.child.parent, self.parent)

    def test_repeatedly_adopting_child_does_not_have_effect(self):
        self.parent.adopt(self.child)
        self.assertTrue(self.parent.is_parent_of(self.child))
        self.assertEqual(self.child.parent, self.parent)

    def test_child_having_a_parent_cannot_be_added_to_new_parent(self):
        new_parent = self.iman.new(name="New Parent")
        self.assertEqual(self.child.parent, self.parent)
        new_parent.adopt(self.child)
        self.assertEqual(self.child.parent, self.parent)

    def test_parent_can_pass_child_to_another_parent(self):
        new_parent = self.iman.new(name="New parent")
        self.parent.adopt(self.child)
        self.parent.pass_to_new_parent(self.child, new_parent)
        self.assertEqual(self.child.parent, new_parent)

    def test_item_leaving_child_makes_child_forget_the_item_as_its_parent(self):
        self.parent._leave_child(self.child)
        self.assertEqual(self.child.parent, NullItem)

    def test_item_leaving_its_parent_makes_the_parent_forget_is(self):
        self.child._leave_parent(self.parent)
        self.assertEqual(self.child.parent, NullItem)
        self.assertFalse(self.parent.is_parent_of(self.child))

    def test_not_a_null_item_cannot_be_its_own_parent(self) -> None:
        self.assertRaises(
            Item.ItemAdoptsItself,
            self.parent.pass_to_new_parent,
            self.child,
            self.child,
        )

    def test_leaving_parent_not_belonging_to_child_has_no_effect(self) -> None:
        not_a_parent = self.iman.new(name="Not a parent")
        self.child._leave_parent(not_a_parent)
        self.assertEqual(self.child.parent, self.parent)

    def test_getting_item_at_the_top_of_family_hierachy(self) -> None:
        grandparent = self.iman.new("Grandparent")
        greatgrandparent = self.iman.new("Great-grandparent")

        greatgrandparent.adopt(grandparent)
        grandparent.adopt(self.parent)
        self.parent.adopt(self.child)

        self.assertEqual(self.child.root, greatgrandparent)
        self.assertEqual(grandparent.root, greatgrandparent)
        self.assertEqual(greatgrandparent.root, greatgrandparent)

    def test_after_leaving_parent_the_child_becomes_its_own_root(self):
        self.child._leave_parent(self.parent)
        self.assertEqual(self.child.root, self.child)

    def test_grandparent_and_parent_are_predecesors_of_item(self):
        grandparent = self.iman.new("Grandparent")
        grandparent.adopt(self.parent)
        stranger = self.iman.new("Stranger")
        self.assertTrue(grandparent.is_ancestor_of(self.child))
        self.assertTrue(self.parent.is_ancestor_of(self.child))
        self.assertFalse(self.child.is_ancestor_of(self.parent))
        self.assertFalse(stranger.is_ancestor_of(self.child))

    def test_adopting_its_own_predecesor_raises_error(self):
        self.assertRaises(Item.AdoptionOfAncestor, self.child.adopt, self.parent)

        grandchild = self.iman.new("Grandchild")
        self.child.adopt(grandchild)
        self.assertRaises(Item.AdoptionOfAncestor, grandchild.adopt, self.parent)

    def test_leaving_null_has_no_effect(self):
        self.child._leave_parent(self.parent)
        self.assertEqual(self.child.parent, NullItem)
        self.child._leave_parent(NullItem)
        self.assertEqual(self.child.parent, NullItem)

    def test_passing_item_to_its_own_child_raises_error(self):
        grandchild = self.iman.new("Grandchild")
        self.child.adopt(grandchild)
        self.assertRaises(
            Item.AdoptionOfAncestor,
            self.parent.pass_to_new_parent,
            self.child,
            grandchild,
        )

    def test_adopting_item_by_its_own_parent(self) -> None:
        self.parent.adopt(self.child)


class Test_Name_Collisions_Of_Items_With_Common_Parent(unittest.TestCase):

    def setUp(self) -> None:
        self.iman = ItemCreator()

    def test_adding_new_child_with_name_already_taken_by_other_child_makes_the_name_to_adjust(
        self,
    ):
        parent = self.iman.new("Parent")
        child = self.iman.new("Child")
        parent.adopt(child)

        child2 = self.iman.new("Child")
        parent.adopt(child2)
        self.assertEqual(child2.name, "Child (1)")

    def test_adding_two_children_with_already_taken_name(self):
        parent = self.iman.new("Parent")
        child = self.iman.new("Child")
        parent.adopt(child)

        child2 = self.iman.new("Child")
        parent.adopt(child2)
        child3 = self.iman.new("Child")
        parent.adopt(child3)

        self.assertEqual(child2.name, "Child (1)")
        self.assertEqual(child3.name, "Child (2)")

    def test_adding_children_differing_in_white_characters(self):
        parent = self.iman.new("Parent")
        child = self.iman.new("The Child")
        parent.adopt(child)

        child2 = self.iman.new("The        Child")
        parent.adopt(child2)
        self.assertEqual(child2.name, "The Child (1)")


class Test_Undo_And_Redo_Setting_Parent_Child_Relationship(unittest.TestCase):

    def setUp(self) -> None:
        self.mg = ItemCreator()
        self.parent = self.mg.new("Parent")
        self.child = self.mg.new("Child")
        self.parent.adopt(self.child)

    def test_undo_and_redo_adoption(self):
        self.mg.undo()
        self.assertFalse(self.parent.is_parent_of(self.child))
        self.assertEqual(self.child.parent, NullItem)
        self.mg.redo()
        self.assertTrue(self.parent.is_parent_of(self.child))
        self.assertEqual(self.child.parent, self.parent)
        self.mg.undo()
        self.assertFalse(self.parent.is_parent_of(self.child))
        self.assertEqual(self.child.parent, NullItem)

    def test_undo_and_redo_passing_to_new_parent(self):
        new_parent = self.mg.new("New Parent")
        self.parent.pass_to_new_parent(self.child, new_parent)

        self.assertTrue(new_parent.is_parent_of(self.child))
        self.assertFalse(self.parent.has_children())
        self.mg.undo()
        self.assertTrue(self.parent.is_parent_of(self.child))
        self.assertTrue(self.parent.has_children())
        self.assertFalse(new_parent.has_children())
        self.mg.redo()
        self.assertTrue(new_parent.is_parent_of(self.child))
        self.mg.undo()
        self.assertTrue(self.parent.is_parent_of(self.child))

    def test_change_parent_twice_and_then_undo_twice_and_redo_twice(self):
        parent2 = self.mg.new("Parent 2")
        parent3 = self.mg.new("Parent 3")
        self.parent.pass_to_new_parent(self.child, parent2)
        parent2.pass_to_new_parent(self.child, parent3)

        self.assertTrue(parent3.is_parent_of(self.child))

        self.mg.undo()
        self.assertTrue(parent2.is_parent_of(self.child))
        self.assertEqual(self.child.parent, parent2)
        self.mg.undo()
        self.assertTrue(self.parent.is_parent_of(self.child))
        self.assertEqual(self.child.parent, self.parent)

        self.mg.redo()
        self.assertTrue(parent2.is_parent_of(self.child))
        self.assertEqual(self.child.parent, parent2)
        self.mg.redo()
        self.assertTrue(parent3.is_parent_of(self.child))
        self.assertEqual(self.child.parent, parent3)
        # additional redo should not do anything
        self.mg.redo()
        self.assertTrue(parent3.is_parent_of(self.child))

    def test_undo_adoption_when_child_name_was_adjusted(self):
        child2 = self.mg.new("Child")
        self.parent.adopt(child2)
        self.assertEqual(child2.name, "Child (1)")

        self.mg.undo()
        self.assertEqual(child2.name, "Child")
        self.mg.redo()
        self.assertEqual(child2.name, "Child (1)")
        self.mg.undo()
        self.assertEqual(child2.name, "Child")

    def test_undo_passing_to_new_parent_when_child_name_was_adjusted(self):
        A_child = self.mg.new("Child")
        A_parent = self.mg.new("Parent 1")
        A_parent.adopt(A_child)

        B_child = self.mg.new("Child")
        B_parent = self.mg.new("Parent 2")
        B_parent.adopt(B_child)

        A_parent.pass_to_new_parent(A_child, B_parent)
        self.assertEqual(A_child.name, "Child (1)")

        self.mg.undo()
        self.assertEqual(A_child.name, "Child")
        self.mg.redo()
        self.assertEqual(A_child.name, "Child (1)")


class Test_Child_Duplicate(unittest.TestCase):

    def setUp(self) -> None:
        self.mg = ItemCreator()
        self.parent = self.mg.new("Parent")
        self.child = self.mg.new("Child")
        self.parent.adopt(self.child)
        self.duplicate = self.child.duplicate()

    def test_child_duplicate_has_the_same_parent_as_the_original(self):
        self.assertTrue(self.parent.is_parent_of(self.duplicate))
        self.assertEqual(self.duplicate.parent, self.parent)
        self.assertEqual(self.duplicate.name, "Child (1)")

    def test_undo_and_redo_duplicating(self):
        self.mg.undo()
        self.assertFalse(self.parent.is_parent_of(self.duplicate))
        self.assertTrue(self.duplicate.parent, NullItem)
        self.assertEqual(self.duplicate.name, "Child")

        self.mg.redo()
        self.assertTrue(self.parent.is_parent_of(self.duplicate))
        self.assertEqual(self.duplicate.name, "Child (1)")

        self.mg.undo()
        self.assertFalse(self.parent.is_parent_of(self.duplicate))
        self.assertEqual(self.duplicate.name, "Child")


class Test_Undo_And_Redo_Multiple_Operations(unittest.TestCase):

    def test_duplicating_and_renaming(self):
        mg = ItemCreator()
        parent = mg.new("Parent")
        child = mg.new("Child")
        parent.adopt(child)
        child_duplicate = child.duplicate()
        child_duplicate.rename("Second child")

        for _ in range(3):
            mg.undo()
            mg.undo()
            mg.undo()
            self.assertEqual(child_duplicate.parent, NullItem)
            self.assertFalse(parent.is_parent_of(child_duplicate))
            self.assertEqual(child_duplicate.name, "Child")
            self.assertEqual(child.parent, NullItem)
            self.assertFalse(parent.is_parent_of(child))
            mg.redo()
            self.assertEqual(child.parent, parent)
            self.assertTrue(parent.is_parent_of(child))
            self.assertEqual(child_duplicate.parent, NullItem)
            mg.redo()
            self.assertEqual(child_duplicate.parent, parent)
            self.assertEqual(child_duplicate.name, "Child (1)")
            mg.redo()
            self.assertEqual(child_duplicate.parent, parent)
            self.assertEqual(child_duplicate.name, "Second child")

    def test_undo_and_executing_new_command_erases_redo_command(self):
        mg = ItemCreator()
        parent = mg.new("Parent")
        child = mg.new("Child")
        parent.adopt(child)
        child.rename("The Child")

        mg.undo()
        self.assertEqual(child.name, "Child")
        mg.redo()
        self.assertEqual(child.name, "The Child")
        mg.undo()
        child.rename("The First Child")
        mg.redo()  # this redo has no effect
        self.assertEqual(child.name, "The First Child")
        mg.undo()
        self.assertEqual(child.name, "Child")
        mg.redo()
        self.assertEqual(child.name, "The First Child")


from te_tree.cmd.commands import Command
from te_tree.core.item import Parentage_Data
import dataclasses


class Test_Connecting_External_Commands_To_The_Adopt_Command(unittest.TestCase):

    @dataclasses.dataclass
    class AdoptionDisplay:
        notification: str = ""
        message: str = ""
        count: int = 0

    @dataclasses.dataclass
    class RecordAdoption(Command):
        parent: Item
        child: Item
        display: Test_Connecting_External_Commands_To_The_Adopt_Command.AdoptionDisplay
        old_message: str = dataclasses.field(init=False)
        new_message: str = dataclasses.field(init=False)

        def run(self) -> None:
            self.old_message = self.display.message
            self.new_message = f"{self.parent.name} has adopted the {self.child.name}"
            self.display.message = self.new_message
            self.display.count += 1

        def undo(self) -> None:
            self.display.count -= 1
            self.display.message = self.old_message

        def redo(self) -> None:
            self.run()

    def setUp(self) -> None:
        self.display = self.AdoptionDisplay()
        self.mg = ItemCreator()
        self.parent = self.mg.new("Parent")

        def record_adoption(data: Parentage_Data) -> Command:
            return self.RecordAdoption(data.parent, data.child, self.display)

        self.parent.on_adoption("test", record_adoption, "pre")

    def test_adding_simple_command_to_the_adopt_command(self):
        child = self.mg.new("Child")
        self.parent.adopt(child)
        self.assertEqual(self.display.message, "Parent has adopted the Child")
        self.assertEqual(self.display.count, 1)

        self.mg.undo()
        self.assertEqual(self.display.message, "")
        self.assertEqual(self.display.count, 0)
        self.mg.redo()
        self.assertEqual(self.display.message, "Parent has adopted the Child")
        self.assertEqual(self.display.count, 1)
        self.mg.undo()
        self.assertEqual(self.display.message, "")
        self.assertEqual(self.display.count, 0)

    def test_adoption_of_two_children(self):
        child = self.mg.new("Child")
        self.parent.adopt(child)

        child2 = self.mg.new("Child 2")
        self.parent.adopt(child2)
        self.assertEqual(self.display.message, "Parent has adopted the Child 2")
        self.assertEqual(self.display.count, 2)

        self.mg.undo()
        self.assertEqual(self.display.message, "Parent has adopted the Child")
        self.assertEqual(self.display.count, 1)

        self.mg.undo()
        self.assertEqual(self.display.message, "")
        self.assertEqual(self.display.count, 0)


from te_tree.core.item import Renaming_Data


class Test_Adding_External_Command_To_Renaming(unittest.TestCase):

    @dataclasses.dataclass
    class Label:
        text: str

    @dataclasses.dataclass
    class CatchNewItemNameInLabel(Command):
        label: Test_Adding_External_Command_To_Renaming.Label
        item: Item
        orig_text: str = dataclasses.field(init=False)
        new_text: str = dataclasses.field(init=False)

        def run(self) -> None:
            self.orig_text = self.label.text
            self.label.text = self.item.name
            self.new_text = self.item.name

        def undo(self) -> None:
            self.label.text = self.orig_text

        def redo(self) -> None:
            self.label.text = self.new_text

    def setUp(self) -> None:
        self.label = Test_Adding_External_Command_To_Renaming.Label("Empty")
        self.mg = ItemCreator()
        self.item = self.mg.new("Child")

        def catch_new_item_name_in_label(
            data: Renaming_Data,
        ) -> Test_Adding_External_Command_To_Renaming.CatchNewItemNameInLabel:

            return self.CatchNewItemNameInLabel(self.label, data.item)

        self.item.on_renaming("test", catch_new_item_name_in_label, "post")

    def test_single_rename_command_undo_and_redo(self):
        self.item.rename("The Child")
        self.assertEqual(self.label.text, "The Child")

        self.mg.undo()
        self.assertEqual(self.label.text, "Empty")
        self.mg.redo()
        self.assertEqual(self.label.text, "The Child")
        self.mg.undo()
        self.assertEqual(self.label.text, "Empty")

    def test_two_rename_commands_undo_and_redo(self):
        self.item.rename("The Child")
        self.item.rename("The Awesome Child")
        self.assertEqual(self.label.text, "The Awesome Child")

        self.mg.undo()
        self.mg.undo()
        self.assertEqual(self.label.text, "Empty")
        self.assertEqual(self.item.name, "Child")
        self.mg.undo()  # does nothing
        self.assertEqual(self.label.text, "Empty")
        self.assertEqual(self.item.name, "Child")
        self.mg.redo()
        self.assertEqual(self.label.text, "The Child")
        self.assertEqual(self.item.name, "The Child")
        self.mg.redo()
        self.assertEqual(self.label.text, "The Awesome Child")
        self.assertEqual(self.item.name, "The Awesome Child")


class Test_Catching_Old_And_New_Name_On_Paper(unittest.TestCase):

    @dataclasses.dataclass
    class Paper:
        old_name: str = ""
        new_name: str = ""

    @dataclasses.dataclass
    class Catch_Old_Name(Command):
        item: Item
        paper: Test_Catching_Old_And_New_Name_On_Paper.Paper
        previous_value: str = dataclasses.field(init=False)
        new_value: str = dataclasses.field(init=False)

        def run(self) -> None:
            self.previous_value: str = self.paper.old_name
            self.paper.old_name = self.item.name
            self.new_value = self.paper.old_name

        def undo(self) -> None:
            self.paper.old_name = self.previous_value

        def redo(self) -> None:
            self.paper.old_name = self.new_value

    @dataclasses.dataclass
    class Catch_New_Name(Command):
        item: Item
        paper: Test_Catching_Old_And_New_Name_On_Paper.Paper
        previous_value: str = dataclasses.field(init=False)
        new_value: str = dataclasses.field(init=False)

        def run(self) -> None:
            self.previous_value: str = self.paper.new_name
            self.paper.new_name = self.item.name
            self.new_value = self.paper.new_name

        def undo(self) -> None:
            self.paper.new_name = self.previous_value

        def redo(self) -> None:
            self.paper.new_name = self.new_value

    def test_catching_old_and_new_item_name_on_paper_when_undoing_and_redoing_rename_operation(
        self,
    ):
        self.mg = ItemCreator()
        self.item = self.mg.new("Old name")
        self.paper = self.Paper()

        def catch_old_name(
            data: Renaming_Data,
        ) -> Test_Catching_Old_And_New_Name_On_Paper.Catch_Old_Name:
            return self.Catch_Old_Name(data.item, self.paper)

        def catch_new_name(
            data: Renaming_Data,
        ) -> Test_Catching_Old_And_New_Name_On_Paper.Catch_New_Name:
            return self.Catch_New_Name(data.item, self.paper)

        self.item.on_renaming("test", catch_old_name, "pre")
        self.item.on_renaming("test", catch_new_name, "post")

        self.item.rename("New name")
        self.assertEqual(self.paper.old_name, "Old name")
        self.assertEqual(self.paper.new_name, "New name")

        self.item.rename("Newer name")
        self.assertEqual(self.paper.old_name, "New name")
        self.assertEqual(self.paper.new_name, "Newer name")

        self.mg.undo()
        self.mg.undo()
        self.assertEqual(self.paper.old_name, "")
        self.assertEqual(self.paper.new_name, "")

        self.mg.redo()
        self.assertEqual(self.paper.old_name, "Old name")
        self.assertEqual(self.paper.new_name, "New name")
        self.mg.redo()
        self.assertEqual(self.paper.old_name, "New name")
        self.assertEqual(self.paper.new_name, "Newer name")


class Test_Accessing_Nonexistent_Attribute(unittest.TestCase):

    def test_accessing_nonexistent_attribute(self):
        mg = ItemCreator()
        item = mg.new("Water", {"Volume": "integer"})
        self.assertRaises(Item.NonexistentAttribute, item.set, "Nonexistent attribute", 5)
        self.assertRaises(Item.NonexistentAttribute, item, "Nonexistent attribute")
        self.assertRaises(Item.NonexistentAttribute, item.attribute, "Nonexistent attribute")

    def test_accessing_existing_attribute(self):
        mg = ItemCreator()
        item = mg.new("Water", {"Volume": "integer"})
        item.set("Volume", 5)
        self.assertEqual(item("Volume"), 5)
        self.assertEqual(item.attribute("Volume").value, 5)


class Test_Attributes_Of_Duplicated_Item(unittest.TestCase):

    def setUp(self) -> None:
        self.mg = ItemCreator()
        self.item = self.mg.new("item", {"a": "integer", "b": "real"})
        self.item.set("a", 4)
        self.item.set("b", 2.5)

    def test_attributes_of_copied_item_have_the_originals_values(self):
        item_duplicate = self.item.duplicate()
        self.assertEqual(item_duplicate("a"), 4)
        self.assertEqual(item_duplicate("b"), 2.5)

    def test_attributes_of_copied_item_are_independent_on_the_originals_attributes(
        self,
    ):
        item_duplicate = self.item.duplicate()
        self.item.set("a", 8)
        self.item.set("b", -1.23)
        self.assertEqual(self.item("a"), 8)
        self.assertEqual(item_duplicate("a"), 4)
        self.assertEqual(item_duplicate("b"), 2.5)


class Test_Children_Of_Duplicated_Item(unittest.TestCase):

    def test_item_is_copied_with_its_children(self) -> None:
        mg = ItemCreator()
        parent = mg.new("parent")
        child = mg.new("child")
        grandchild = mg.new("grandchild")
        parent.adopt(child)
        child.adopt(grandchild)

        child_duplicate = child.duplicate()
        self.assertTrue(child_duplicate.has_children())
        self.assertEqual(child_duplicate.name, "child (1)")


class Test_Undo_And_Redo_Duplicating_Item(unittest.TestCase):

    def test_duplicating_a_single_child(self):
        mg = ItemCreator()
        parent = mg.new("Parent")
        child = mg.new("Child")
        parent.adopt(child)

        child_duplicate = child.duplicate()
        self.assertTrue(parent.is_parent_of(child_duplicate))
        self.assertEqual(child_duplicate.name, "Child (1)")
        mg.undo()
        self.assertFalse(parent.is_parent_of(child_duplicate))
        self.assertEqual(child_duplicate.name, "Child")
        mg.redo()
        self.assertTrue(parent.is_parent_of(child_duplicate))
        self.assertEqual(child_duplicate.name, "Child (1)")
        mg.undo()
        self.assertFalse(parent.is_parent_of(child_duplicate))
        self.assertEqual(child_duplicate.name, "Child")

    def test_duplicating_item_with_arbitrary_tree_of_descendants_behaves_like_single_command(
        self,
    ):
        mg = ItemCreator()
        parent = mg.new("Parent")
        child = mg.new("Child")
        grandchild = mg.new("Grandchild")
        parent.adopt(child)
        child.adopt(grandchild)

        parent.rename("The Parent")
        self.assertEqual(parent.name, "The Parent")
        child_duplicate = child.duplicate()

        mg.undo()  # this undo reverts the duplicate operation
        mg.undo()  # this undo reverts the renaming
        self.assertEqual(parent.name, "Parent")
        self.assertFalse(parent.is_parent_of(child_duplicate))
        mg.redo()
        mg.redo()
        self.assertEqual(parent.name, "The Parent")
        self.assertTrue(parent.is_parent_of(child_duplicate))
        mg.undo()
        mg.undo()
        self.assertEqual(parent.name, "Parent")
        self.assertFalse(parent.is_parent_of(child_duplicate))


class Test_Binding_Attributes_Owned_By_The_Same_Item(unittest.TestCase):

    def setUp(self) -> None:
        self.mg = ItemCreator()
        self.integer = self.mg.attr.integer()
        self.item = self.mg.new("Item", {"x": "integer", "y": "integer", "z": "integer"})
        self.item.set("y", -1)
        self.item.bind("y", self.square, freeatt("x"))

    @staticmethod
    def square(x: int) -> int:
        return x * x

    def test_two_attributes_owned_by_the_the_same_item_are_bound_by_a_specified_function(
        self,
    ):
        self.item.set("x", 2)
        self.assertEqual(self.item("y"), 4)

    def test_freeing_attribute_removes_its_dependency_on_other_attribute(self):
        self.item.set("x", 2)
        self.item.free("y")
        self.item.set("x", 3)
        self.assertEqual(self.item("y"), 4)

    def test_calling_set_on_bound_attribute_has_no_effect(self):
        self.item.set("x", 2)
        self.item.set("y", -16651651653)
        self.assertEqual(self.item("y"), 4)

    def test_copying_item_preserves_the_dependency(self):
        self.item.set("x", 3)
        item2 = self.item.duplicate()
        item2.set("x", 5)
        self.assertEqual(self.item("x"), 3)
        self.assertEqual(item2("x"), 5)
        self.assertEqual(self.item("y"), 9)
        self.assertEqual(item2("y"), 25)

    def test_multivariable_binding(self):
        self.item.free("y")
        self.item.bind("z", lambda x, y: x + y, "x", "y")
        self.item.set("x", 2)
        self.item.set("y", 3)
        self.assertEqual(self.item("z"), 5)

    def test_chain_of_bindings(self) -> None:
        self.item.free("y")

        self.item.bind("y", lambda t: t + 1, "x")
        self.item.bind("z", lambda t: 2 * t, "y")

        self.item.set("x", 3)
        self.assertEqual(self.item("y"), 4)
        self.assertEqual(self.item("z"), 8)

    def test_redo_and_undo_setting_free_value(self):
        self.item.set("x", 2)
        self.item.set("x", 3)
        self.item.set("x", 4)
        self.mg.undo()
        self.assertEqual(self.item("y"), 9)
        self.mg.undo()
        self.assertEqual(self.item("y"), 4)
        self.mg.redo()
        self.assertEqual(self.item("y"), 9)
        self.mg.redo()
        self.assertEqual(self.item("y"), 16)
        self.mg.undo()
        self.assertEqual(self.item("y"), 9)
        self.mg.undo()
        self.assertEqual(self.item("y"), 4)


from typing import List


class Test_Binding_Item_Attribute_To_Its_Children(unittest.TestCase):

    def setUp(self) -> None:
        self.mg = ItemCreator()
        self.integer = self.mg.attr.integer()
        self.parent = self.mg.new("Parent", {"y": "integer"})

    @staticmethod
    def sum_x(x: List[int]) -> int:
        return sum(x)

    def test_parent_attribute_can_be_bound_to_any_attribute_that_is_expected_to_be_owned_by_some_of_its_children(
        self,
    ):
        self.parent.bind("y", self.sum_x, freeatt_child("x", self.integer))
        self.assertEqual(self.parent("y"), 0)

    def test_parent_attribute_is_automatically_updates_when_adopting_or_leaving_a_child(
        self,
    ):
        self.parent.bind("y", self.sum_x, freeatt_child("x", self.integer))
        child = self.mg.new("Child", {"x": "integer"})
        child.set("x", 1)
        self.parent.adopt(child)
        self.assertEqual(self.parent("y"), 1)
        self.parent.leave(child)
        self.assertEqual(self.parent("y"), 0)

    def test_children_not_containing_the_input_attribute_are_neglected(self):
        self.parent.bind("y", self.sum_x, freeatt_child("x", self.integer))
        child = self.mg.new("Child", {"x": "integer"})
        child.set("x", 1)
        self.parent.adopt(child)
        self.assertEqual(self.parent("y"), 1)
        child_without_x = self.mg.new("Child", {"z": "integer"})
        self.parent.adopt(child_without_x)
        self.assertEqual(self.parent("y"), 1)

    def test_adding_child_with_attribute_of_type_that_does_not_match_the_dependency_raises_exception(
        self,
    ):
        self.parent.bind("y", self.sum_x, freeatt_child("x", self.integer))
        child = self.mg.new("Child", {"x": "text"})
        self.assertRaises(ItemImpl.ChildAttributeTypeConflict, self.parent.adopt, child)

    def test_passing_child_to_other_parent(self) -> None:
        parent = self.mg.new("The first parent", {"y": "integer"})
        parent.bind("y", self.sum_x, freeatt_child("x", self.integer))
        child = self.mg.new("Child", {"x": "integer"})
        child.set("x", 1)
        other_parent = self.mg.new("The other parent")

        parent.adopt(child)
        self.assertEqual(parent("y"), 1)
        self.assertTrue(child.attribute("x") in parent._child_attr_lists["x"])

        parent.pass_to_new_parent(child, other_parent)
        self.assertFalse(parent.is_parent_of(child))
        self.assertTrue(other_parent.is_parent_of(child))
        self.assertFalse(child.attribute("x") in parent._child_attr_lists["x"])
        self.assertEqual(parent("y"), 0)

        other_parent.pass_to_new_parent(child, parent)
        self.assertTrue(child.attribute("x") in parent._child_attr_lists["x"])
        self.assertEqual(parent("y"), 1)

    def test_binding_to_already_existing_list_of_childrens_attributes(self):
        parent = self.mg.new("Some parent", {"y": "integer", "z": "integer"})
        parent.bind("y", sum, freeatt_child("x", self.integer))
        parent.bind("z", sum, freeatt_child("x", self.integer))
        self.assertEqual(parent("y"), 0)
        self.assertEqual(parent("z"), 0)
        child = self.mg.new("Child", {"x": "integer"})
        child.set("x", 2)
        parent.adopt(child)
        self.assertEqual(parent("y"), 2)
        self.assertEqual(parent("z"), 2)

    def test_adopting_child_without_input_attribute_has_no_effect(self):
        parent = self.mg.new("Some parent", {"y": "integer"})
        parent.bind("y", sum, freeatt_child("x", self.integer))
        child = self.mg.new("Child", {"not an x": "integer"})
        child.set("not an x", 1)

        self.assertEqual(parent("y"), 0)
        parent.adopt(child)
        self.assertEqual(parent("y"), 0)
        parent.leave(child)
        self.assertEqual(parent("y"), 0)

    def test_adding_dependency_on_children_attributes_when_already_having_children(
        self,
    ):
        parent = self.mg.new("Some parent", {"y": "integer"})
        child = self.mg.new("Child", {"x": "integer"})
        other_child = self.mg.new("Other Child")
        child.set("x", 2)
        parent.adopt(child)
        parent.adopt(other_child)

        parent.bind("y", sum, freeatt_child("x", self.integer))
        self.assertEqual(parent("y"), 2)

    def test_switching_roles_of_parent_and_child_both_depending_on_child_attributes_of_the_same_name(
        self,
    ):
        parent = self.mg.new("Parent", {"x": "integer", "y": "integer"})
        child = self.mg.new("Child", {"x": "integer", "y": "integer"})
        integer = self.mg.attr.integer(0)
        parent.adopt(child)

        parent.set("x", 5)
        parent.set("y", -1)
        child.set("x", 5)
        child.set("y", -1)

        parent.bind("y", sum, freeatt_child("x", integer))
        child.bind("y", sum, freeatt_child("x", integer))

        self.assertEqual(parent("y"), 5)
        self.assertEqual(child("y"), 0)

        parent.leave(child)
        child.adopt(parent)

        self.assertEqual(parent("y"), 0)
        self.assertEqual(child("y"), 5)


from te_tree.core.item import freeatt, freeatt_parent, freeatt_child


class Test_Examples_Of_Calculations_On_Child_Attributes(unittest.TestCase):

    def setUp(self) -> None:
        self.mg = ItemCreator()
        self.real = self.mg.attr.real(0)
        self.bool = self.mg.attr.boolean(False)
        self.parent = self.mg.new("Parent", {"y": self.real})

    def test_calculating_average_of_child_attribute(self):
        childA = self.mg.new("Parent", {"x": self.real})
        childB = self.mg.new("Parent", {"x": self.real})
        childA.set("x", 5)
        childB.set("x", 3)

        def arithmetic_average(x: List[decimal.Decimal]) -> decimal.Decimal | float:
            if not x:
                return math.nan
            return decimal.Decimal(sum(x)) / len(x)

        self.parent.bind("y", arithmetic_average, freeatt_child("x", self.real))
        self.assertTrue(math.isnan(self.parent("y")))

        self.parent.adopt(childA)
        self.assertEqual(self.parent("y"), 5)
        self.parent.adopt(childB)
        self.assertEqual(self.parent("y"), 4)
        self.parent.leave(childA)
        self.assertEqual(self.parent("y"), 3)
        self.parent.leave(childB)
        self.assertTrue(math.isnan(self.parent("y")))

    def test_summing_over_child_attributes_coplying_with_condition(self):
        childA = self.mg.new("Parent", {"x": "real", "switch": "bool"})
        childB = self.mg.new("Parent", {"x": "real", "switch": "bool"})
        self.parent.adopt(childA)
        self.parent.adopt(childB)

        def sumif(x: List[float], val: List[int]) -> float:
            return sum([xi for xi, vi in zip(x, val) if vi == True])

        self.parent.bind(
            "y",
            sumif,
            freeatt_child("x", self.real),
            freeatt_child("switch", self.bool),
        )

        childA.set("switch", 0)
        childB.set("switch", 0)
        childA.set("x", 2)
        childB.set("x", 3)
        self.assertEqual(self.parent("y"), 0)

        childA.set("switch", 1)
        self.assertEqual(self.parent("y"), 2)

        childB.set("switch", 1)
        self.assertEqual(self.parent("y"), 5)

        self.mg.undo()
        self.assertEqual(self.parent("y"), 2)
        self.mg.undo()
        self.assertEqual(self.parent("y"), 0)
        self.mg.redo()
        self.assertEqual(self.parent("y"), 2)
        self.mg.redo()
        self.assertEqual(self.parent("y"), 5)


class Test_Picking_Child_Item_By_Name(unittest.TestCase):

    def test_picking_child_by_name(self):
        mg = ItemCreator()
        parent = mg.new("Parent")
        alice = mg.new("Alice")
        bob = mg.new("Bob")
        not_a_child = mg.new("Not a Child")

        parent.adopt(alice)
        parent.adopt(bob)

        self.assertEqual(parent.pick_child("Bob"), bob)
        self.assertEqual(parent.pick_child("Alice"), alice)
        self.assertEqual(parent.pick_child("Not a Child"), NullItem)


class Test_Leaving_Child(unittest.TestCase):

    def test_running_leaving_child_command(self):
        mg = ItemCreator()
        parent = mg.new("Parent")
        child = mg.new("Child")
        parent.adopt(child)
        parent.leave(child)
        self.assertFalse(parent.has_children())
        self.assertFalse(parent.is_parent_of(child))
        mg.undo()
        self.assertTrue(parent.has_children())
        self.assertTrue(parent.is_parent_of(child))

    def test_passing_to_new_parent(self):
        mg = ItemCreator()
        parent = mg.new("Parent")
        new_parent = mg.new("New Parent")
        child = mg.new("Child")
        parent.adopt(child)

        parent.pass_to_new_parent(child, new_parent)
        self.assertFalse(parent.has_children())
        self.assertFalse(parent.is_parent_of(child))
        self.assertTrue(new_parent.has_children())
        self.assertTrue(new_parent.is_parent_of(child))


class Test_Running_Additional_Command_When_Leaving_Child(unittest.TestCase):

    def setUp(self) -> None:
        @dataclasses.dataclass
        class Message:
            text: str = ""

        @dataclasses.dataclass
        class Write_Message(Command):
            data: Write_Message_Data
            old_text: str = ""
            new_text: str = ""

            def run(self) -> None:
                self.old_text = self.data.message.text
                self.data.message.text = f"{self.data.message_start} {self.data.child.name}"
                self.new_text = self.data.message.text

            def undo(self) -> None:
                self.data.message.text = self.old_text

            def redo(self) -> None:
                self.data.message.text = self.new_text

        @dataclasses.dataclass
        class Write_Message_Data:
            message_start: str
            message: Message
            child: Item

        self.mg = ItemCreator()
        self.parent = self.mg.new("Parent")
        self.child = self.mg.new("Child")
        self.parent.adopt(self.child)
        self.message_before = Message()
        self.message_after = Message()

        def write_message_before(data: Parentage_Data) -> Command:
            return Write_Message(Write_Message_Data("Leaving", self.message_before, self.child))

        def write_message_after(data: Parentage_Data) -> Command:
            return Write_Message(Write_Message_Data("Left", self.message_after, self.child))

        self.parent.on_leaving("test", write_message_before, "pre")
        self.parent.on_leaving("test", write_message_after, "post")

    def test_writing_message_before_and_after_leaving_child(self):
        self.parent.leave(self.child)
        self.assertEqual(self.message_before.text, "Leaving Child")
        self.assertEqual(self.message_after.text, "Left Child")
        self.mg.undo()
        self.assertEqual(self.message_before.text, "")
        self.assertEqual(self.message_after.text, "")
        self.mg.redo()
        self.assertEqual(self.message_before.text, "Leaving Child")
        self.assertEqual(self.message_after.text, "Left Child")
        self.mg.undo()
        self.assertEqual(self.message_before.text, "")
        self.assertEqual(self.message_after.text, "")

    def test_writing_message_before_and_after_passing_child_to_other_parent(self):
        other_parent = self.mg.new("Other Parent")

        self.parent.pass_to_new_parent(self.child, other_parent)
        self.assertEqual(self.message_before.text, "Leaving Child")
        self.assertEqual(self.message_after.text, "Left Child")


from te_tree.core.attributes import Attribute_Data_Constructor


class Test_Defining_Item_Attributes_Via_Special_Methods(unittest.TestCase):

    def test_define_item_via_template(self):
        cr = ItemCreator()
        cr.add_template(
            "Item",
            attributes={
                "x": cr.attr.integer(5),
                "y": cr.attr.real(7.5),
                "description": cr.attr.text("..."),
                "cost": cr.attr.money(15.1),
                "weight": cr.attr.quantity(unit="kg", init_value=2.5),
            },
        )
        item = cr.from_template("Item")
        self.assertEqual(item("x"), 5)
        self.assertEqual(item("y"), 7.5)
        self.assertEqual(item("description"), "..."),
        self.assertEqual(item("cost"), 15.1),
        self.assertEqual(item("weight"), 2.5)

    def test_using_dictionary_specifying_undefined_attribute_type_raises_exception(
        self,
    ):
        cr = ItemCreator()
        self.assertRaises(
            Attribute_Data_Constructor.UndefinedAttributeType,
            cr.add_template,
            "Item",
            attributes={"x": {"atype": "invalid_attribute_type", "init_value": 5}},
        )

    def test_missing_attribute_type_in_attribute_info_raises_exception(self):
        cr = ItemCreator()
        self.assertRaises(
            Attribute_Data_Constructor.MissingAttributeType,
            cr.add_template,
            "Item",
            attributes={"x": {}},
        )


class Test_Formal_Adoption(unittest.TestCase):

    def setUp(self) -> None:
        self.cr = ItemCreator()
        self.parent = self.cr.new("Parent")
        self.child = self.cr.new("Child")
        self.parent.adopt_formally(self.child)

    def test_child_adopted_formally_does_not_know_about_its_formal_parent(self):
        self.assertTrue(self.child in self.parent.formal_children)
        self.assertTrue(self.child.parent is ItemImpl.NULL)
        self.assertFalse(self.parent.is_parent_of(self.child))

    def test_actually_adopting_child_removes_it_from_formal_child_set(self):
        self.parent.adopt(self.child)
        self.assertFalse(self.child in self.parent.formal_children)

    def test_actual_child_cannot_be_adopted_formally(self):
        self.parent.adopt(self.child)
        self.assertRaises(ItemImpl.AlreadyAChild, self.parent.adopt_formally, self.child)

    def test_leaving_formal_child(self):
        self.parent.adopt_formally(self.child)
        self.parent.leave_formal_child(self.child)
        self.assertRaises(Item.FormalChildNotFound, self.parent.leave_formal_child, self.child)


class Test_Creating_Item_From_Template(unittest.TestCase):

    def test_creating_item_from_nonexistent_template_raises_exception(self):
        cr = ItemCreator()
        self.assertRaises(ItemCreator.UndefinedTemplate, cr.from_template, "Nonexistent template")


class Test_Setting_Mutliple_Attributes_At_Once(unittest.TestCase):

    def test_setting_multiple_item_attributes_at_once(self):
        cr = ItemCreator()
        item = cr.new("Item", {"x": "integer", "y": "integer"})
        item.multiset({"x": 5, "y": 15})
        self.assertEqual(item("x"), 5)
        self.assertEqual(item("y"), 15)
        self.assertRaises(Item.NonexistentAttribute, item.multiset, {"nonexistent_attributes": 6})


class Test_Simple_Actions_After_Item_Commands(unittest.TestCase):

    def setUp(self) -> None:
        self.cr = ItemCreator()
        self.parent = self.cr.new("Parent", {"weight": "integer"})
        self.item = self.cr.new("Item", {"description": "text"})

    def test_action_after_renaming(self):
        self.new_name = self.parent.name

        def record_new_name(item: Item) -> None:
            self.new_name = item.name

        self.parent.add_action("test", "rename", record_new_name)
        self.parent.rename("The Parent")
        self.assertEqual(self.new_name, "The Parent")
        self.cr.undo()
        self.assertEqual(self.new_name, "Parent")


class Test_Binding_Attribute_To_Items_Parent(unittest.TestCase):

    def setUp(self) -> None:
        self.cr = ItemCreator()
        self.parent = self.cr.new("Parent", {"x": "integer"})
        self.parent.set("x", 1)
        self.child = self.cr.new("Child", {"x": "integer"})

    def test_binding_to_parents_attribute(self):
        integer = self.cr.attr.integer(0.0)
        self.parent.adopt(self.child)
        self.child.bind("x", lambda x: 2 * x, freeatt_parent("x", integer))
        self.assertEqual(self.child("x"), 2)
        self.parent.set("x", 4)
        self.assertEqual(self.child("x"), 8)

    def test_binding_to_parents_attribute_if_parent_is_null_sets_the_attribute_to_default_value(
        self,
    ):
        integer = self.cr.attr.integer(0.0)
        self.child.bind("x", lambda x: 2 * x, freeatt_parent("x", integer))
        self.assertListEqual(list(self.child._parent_attributes.keys()), ["x"])
        self.parent.adopt(self.child)
        self.assertEqual(self.child("x"), 2)
        self.parent.set("x", 4)
        self.assertEqual(self.child("x"), 8)


from te_tree.core.item import freeatt_child


class Test_Copying_Item_With_Multiple_Types_Of_Children(unittest.TestCase):

    def setUp(self) -> None:
        self.cr = ItemCreator()
        self.parent = self.cr.new("Parent", {"x": "integer"})
        int_attr = self.cr.attr.integer(3)
        self.parent.bind("x", lambda x: sum(x), freeatt_child("x", int_attr))
        self.parent.set("x", 1)
        self.item = self.cr.new("Item", {"x": "integer"})
        self.item.bind("x", lambda x: sum(x), freeatt_child("x", int_attr))
        self.child_A = self.cr.new("Child", {"x": int_attr})
        self.child_B = self.cr.new("Child", {"y": int_attr})
        self.parent.adopt(self.item)
        self.item.adopt(self.child_A)
        self.item.adopt(self.child_B)
        self.assertEqual(self.parent("x"), 3)

    def test_copying_the_parent(self):
        item_copy = self.item.copy()
        self.assertEqual(item_copy("x"), 3)
        self.parent.adopt(item_copy)
        self.assertEqual(self.parent("x"), 6)


import time


class Test_Getting_Time_String(unittest.TestCase):

    def test_getting_time_string(self) -> None:
        curr_time = time.mktime(time.struct_time([2023, 8, 21, 15, 54, 0, 0, 0, 0]))
        strtime = ItemCreator.get_strtime(curr_time)
        self.assertEqual(strtime, "2023-08-21_16-54-00")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
