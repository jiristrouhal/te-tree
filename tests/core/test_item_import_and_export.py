from __future__ import annotations
import unittest
import os
import sys

sys.path.insert(1, "src")
from te_tree.core.item import ItemCreator


class Test_Setting_File_Path_For_Item_Saving_And_Loading(unittest.TestCase):

    def setUp(self) -> None:  # pragma: no cover
        os.mkdir("./__test_dir")

    def test_setting_file_path_for_export_and_import_of_items(self):
        cr = ItemCreator()
        cr.set_dir_path("./__test_dir")
        self.assertEqual(cr.file_path, "./__test_dir")

    def test_setting_file_path_to_nonexistent_directory_raises_exception(self):
        cr = ItemCreator()
        self.assertRaises(
            ItemCreator.NonexistentDirectory,
            cr.set_dir_path,
            "./__$nonexistent_directory__",
        )

    def tearDown(self):  # pragma: no cover
        if os.path.isdir("./__test_dir"):
            os.rmdir("./__test_dir")


class Test_Saving_Items_As_XML(unittest.TestCase):

    def setUp(self) -> None:  # pragma: no cover
        if not os.path.isdir("./__test_dir_2"):
            os.mkdir("./__test_dir_2")
        self.cr = ItemCreator()
        self.cr.set_dir_path("./__test_dir_2")

    def test_saving_single_item_without_assigned_template_raises_exception(
        self,
    ) -> None:
        item = self.cr.new("Item", {"x": "integer"})
        self.assertRaises(ItemCreator.NoTemplateIsAssigned, self.cr.save, item, "xml")

    def test_saving_single_item_as_xml(self) -> None:
        self.cr.add_template("Item_X", {"x": self.cr.attr.integer(3)})
        item = self.cr.from_template("Item_X")
        self.cr.save(item, "xml")
        filepath = "./__test_dir_2/Item_X.xml"
        file_was_created = os.path.isfile(filepath)
        if file_was_created:  # pragma: no cover
            os.remove(filepath)

        self.assertTrue(file_was_created)

    def tearDown(self) -> None:  # pragma: no cover
        if os.path.isdir("./__test_dir_2"):
            os.rmdir("./__test_dir_2")


def build_dir(dirpath: str) -> None:  # pragma: no cover
    if not os.path.isdir(dirpath):
        os.mkdir(dirpath)


def remove_dir(dirpath: str) -> None:  # pragma: no cover
    if os.path.isdir(dirpath):
        for f in os.listdir(dirpath):
            os.remove(os.path.join(dirpath, f))
            pass
        os.rmdir(dirpath)


class Test_Saving_Item_As_Binary(unittest.TestCase):

    DIRPATH = "./__test_dir_21"

    def setUp(self) -> None:
        build_dir(self.DIRPATH)
        self.cr = ItemCreator()
        self.cr.set_dir_path(self.DIRPATH)


class Test_Loading_Item_From_XML(unittest.TestCase):

    DIRPATH = "./__test_dir_3"

    def setUp(self) -> None:  # pragma: no cover
        build_dir(self.DIRPATH)
        self.cr = ItemCreator()
        self.cr.set_dir_path(self.DIRPATH)
        self.cr.add_template(
            "Item",
            {
                "count": self.cr.attr.integer(0),
                "description": self.cr.attr.text("..."),
                "weight": self.cr.attr.quantity("kg"),
                "double_weight": self.cr.attr.quantity("kg"),
            },
            dependencies=[self.cr.dependency("double_weight", lambda x: 2 * x, "weight")],
        )
        self.templ_item = self.cr.from_template("Item", "Item A")
        self.templ_item.set("count", 7)
        self.templ_item.set("description", "This is the description.")
        self.templ_item.set("weight", 5)
        self.cr.save(self.templ_item, "xml")

    def test_loading_nonexistent_item_raises_exception(self):
        self.assertRaises(
            ItemCreator.FileDoesNotExist,
            self.cr.load,
            self.DIRPATH,
            "Nonexistent file",
            "xml",
        )

    def test_loading_item_without_existing_template_raises_exception(self):
        other_cr = ItemCreator()  # this creator is missing the template 'Item' required for loading
        self.assertRaises(
            ItemCreator.UnknownTemplate,
            other_cr.load,
            dirpath=self.DIRPATH,
            name="Item A",
            ftype="xml",
        )

    def test_loading_item(self):
        item = self.cr.load(self.DIRPATH, "Item A", "xml")
        self.assertEqual(item.name, "Item A")
        self.assertEqual(item("count"), 7)
        self.assertEqual(item("description"), "This is the description.")
        self.assertEqual(item("weight"), 5)
        self.assertEqual(item("double_weight"), 10)

    def tearDown(self) -> None:  # pragma: no cover
        remove_dir(self.DIRPATH)


class Test_Saving_And_Loading_Items_With_Children(unittest.TestCase):

    DIRPATH = "./__test_dir_4"

    def setUp(self) -> None:  # pragma: no cover
        build_dir(self.DIRPATH)
        self.cr = ItemCreator()
        self.cr.set_dir_path(self.DIRPATH)
        self.cr.add_template("Item", {}, ("Item",))
        self.parent = self.cr.from_template("Item", "Parent")
        self.child = self.cr.from_template("Item", "Child")
        self.parent.adopt(self.child)

    def test_saving_and_loading_item_with_single_child(self) -> None:
        self.cr.save(self.parent, "xml")
        loaded_parent = self.cr.load(self.DIRPATH, "Parent", "xml")
        self.assertTrue(loaded_parent.has_children())
        loaded_child = loaded_parent.pick_child("Child")
        self.assertFalse(loaded_child.is_null())
        self.assertEqual(loaded_child.name, "Child")

    def test_saving_and_loading_items_with_multiple_levels_of_descendants(self):
        grandchildA = self.cr.from_template("Item", "Grandchild A")
        grandchildB = self.cr.from_template("Item", "Grandchild B")
        self.child.adopt(grandchildA)
        self.child.adopt(grandchildB)
        self.cr.save(self.parent, "xml")

        loaded_parent = self.cr.load(self.DIRPATH, "Parent", "xml")
        loaded_child = loaded_parent.pick_child("Child")
        self.assertFalse(loaded_child.pick_child("Grandchild A").is_null())
        self.assertFalse(loaded_child.pick_child("Grandchild B").is_null())

    def tearDown(self) -> None:  # pragma: no cover
        remove_dir(self.DIRPATH)


from typing import List
from decimal import Decimal
import math

from te_tree.core.item import freeatt_child
from te_tree.core.attributes import NBSP


class Test_Loading_Item_With_Attribute_Depending_On_Items_Children(unittest.TestCase):

    DIRPATH = "./__test_dir_5"

    def setUp(self) -> None:  # pragma: no cover
        build_dir(self.DIRPATH)
        self.cr = ItemCreator()
        self.cr.set_dir_path(self.DIRPATH)

    def test_saving_and_loading_parent_calculating_average_of_its_childrens_attribute(
        self,
    ):
        real = self.cr.attr.real()

        def average(x: List[float | Decimal]) -> float | Decimal:
            if len(x) == 0:
                return math.nan
            return sum(x) / len(x)

        self.cr.add_template(
            "ChildType",
            {"x": self.cr.attr.real(1)},
        )

        self.cr.add_template(
            "ParentType",
            {"avg": self.cr.attr.real(0)},
            ("ChildType",),
            dependencies=[self.cr.dependency("avg", average, freeatt_child("x", real))],
        )

        parent = self.cr.from_template("ParentType", "Parent")
        child_1 = self.cr.from_template("ChildType", "Child 1")
        child_2 = self.cr.from_template("ChildType", "Child 2")
        child_1.set("x", 3)
        child_2.set("x", 2)
        parent.adopt(child_1)
        parent.adopt(child_2)
        self.cr.save(parent, "xml")

        loaded_parent = self.cr.load(self.DIRPATH, "Parent", "xml")
        self.assertEqual(loaded_parent("avg"), 2.5)
        loaded_parent.pick_child("Child 1").set("x", 0)
        self.assertEqual(loaded_parent("avg"), 1)

    def test_saving_and_loading_item_with_quantity_attribute(self):
        mass = self.cr.attr.quantity("g", exponents={"k": 3, "m": -3})
        self.cr.add_template("Item_Type", {"mass": mass})

        item = self.cr.from_template("Item_Type", "Item")
        item.set("mass", 2000)
        item.attribute("mass").set_prefix("k")
        self.assertEqual(item.attribute("mass").print(), f"2{NBSP}kg")
        self.cr.save(item, "xml")

        loaded_item = self.cr.load(self.DIRPATH, name="Item", ftype="xml")
        self.assertEqual(loaded_item.attribute("mass").print(), f"2{NBSP}kg")

    def test_saving_and_loading_item_with_quantity_attribute_with_nonempty_default_prefix(
        self,
    ):
        mass = self.cr.attr.quantity("kg", exponents={"k": 3, "m": -3})
        self.cr.add_template("Item_Type", {"mass": mass})

        item = self.cr.from_template("Item_Type", "Item")
        item.set("mass", 2)
        item.attribute("mass").set_prefix("")
        self.assertEqual(item.attribute("mass").print(), f"2000{NBSP}g")
        self.assertEqual(item("mass"), 2)
        self.cr.save(item, "xml")

        loaded_item = self.cr.load(self.DIRPATH, name="Item", ftype="xml")
        self.assertEqual(loaded_item.attribute("mass").print(), f"2000{NBSP}g")
        self.assertEqual(loaded_item("mass"), 2)

    def test_saving_and_loading_item_with_child_with_quantity_attribute(self):
        mass = self.cr.attr.quantity("kg", exponents={"k": 3, "m": -3})
        self.cr.add_template("Item_Type", {"mass": mass}, ("Item_Type",))

        parent = self.cr.from_template("Item_Type", "Parent")
        child = self.cr.from_template("Item_Type", "Child")
        parent.adopt(child)

        child.set("mass", 2)
        child.attribute("mass").set_prefix("")
        self.cr.save(parent, "xml")

        loaded_parent = self.cr.load(self.DIRPATH, name="Parent", ftype="xml")
        loaded_child = list(loaded_parent.children)[-1]

        self.assertEqual(loaded_child.attribute("mass").print(), f"2000{NBSP}g")
        self.assertEqual(loaded_child("mass"), 2)

    def tearDown(self) -> None:  # pragma: no cover
        remove_dir(self.DIRPATH)


from decimal import Decimal
from te_tree.core.item import freeatt_child, freeatt_parent


class Test_Saving_And_Loading_Item_With_Bound_Attribute(unittest.TestCase):

    DIRPATH = "./__test_dir_6"

    def setUp(self) -> None:  # pragma: no cover
        build_dir(self.DIRPATH)

    def test_saving_and_loading_parent_with_single_child(self):
        cr = ItemCreator()
        cr.set_dir_path(self.DIRPATH)
        amount = cr.attr.real(1)
        rel_amount = cr.attr.real(-1)

        total_amount_dep = cr.dependency(
            "total_amount",
            lambda x, own_x: sum(x) + own_x,
            freeatt_child("amount", amount),
            "amount",
            label="total amount dependency",
        )

        def rel_amount_func(own_amount, parent_total_amount) -> Decimal:
            if parent_total_amount == 0:
                return Decimal(-1)
            else:
                return Decimal(own_amount) / Decimal(parent_total_amount)

        rel_amount_dep = cr.dependency(
            "relative_amount",
            rel_amount_func,
            "amount",
            freeatt_parent("total_amount", amount),
            label="relative amount dependency",
        )

        cr.add_template(
            "Child",
            {"amount": amount, "relative_amount": rel_amount},
            (),
            dependencies=[rel_amount_dep],
        )
        cr.add_template(
            "Parent",
            {"amount": amount, "total_amount": amount},
            ("Child",),
            dependencies=[total_amount_dep],
        )

        parent = cr.from_template("Parent", "Parent")
        child = cr.from_template("Child", "Child")
        parent.adopt(child)

        parent.set("amount", 4)
        child.set("amount", 1)
        self.assertEqual(parent("total_amount"), 5)
        self.assertEqual(child("relative_amount"), Decimal("0.2"))
        child.set("amount", 4)
        self.assertEqual(child("relative_amount"), 0.5)
        child.set("amount", 1)

        cr.save(parent, "xml")
        loaded_parent = cr.load(self.DIRPATH, "Parent", "xml")
        loaded_child = loaded_parent.pick_child("Child")
        self.assertEqual(loaded_parent("total_amount"), 5)
        self.assertEqual(loaded_child("amount"), 1)
        self.assertEqual(loaded_child("relative_amount"), Decimal("0.2"))
        loaded_child.set("amount", 4)

        self.assertEqual(loaded_child("relative_amount"), Decimal("0.5"))

    def tearDown(self) -> None:  # pragma: no cover
        remove_dir(self.DIRPATH)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
