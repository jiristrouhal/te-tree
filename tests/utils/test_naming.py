import unittest
import sys

sys.path.insert(1, "src")

import te_tree.utils.naming as naming


class Test_Adjusting_Already_Taken_Name(unittest.TestCase):

    def test_adjusting_already_existing_name_once(self):
        name = "Banana"
        name_1 = naming.adjust_taken_name(name)
        self.assertEqual(name_1, "Banana (1)")

    def test_adjusting_name_with_number_over_ten(self):
        name = "Lemon (10)"
        self.assertEqual(naming.adjust_taken_name(name), "Lemon (11)")

    def test_adjusting_name_for_the_second_time_with_trailing_spaces(self):
        name = "Pear (1)  "
        expected = "Pear (2)"
        self.assertEqual(naming.adjust_taken_name(name), expected)

    def test_negative_number_in_the_bracket(self):
        name = "Strawberry (-5)"
        expected = "Strawberry (-4)"
        self.assertEqual(naming.adjust_taken_name(name), expected)

    def test_plus_sign_in_the_bracket(self):
        name = "Strawberry (+6)"
        expected = "Strawberry (7)"
        self.assertEqual(naming.adjust_taken_name(name), expected)

    def test_high_number(self):
        high_int = 100**78
        name = f"Grape ({high_int})"
        expected = f"Grape ({high_int+1})"
        self.assertEqual(naming.adjust_taken_name(name), expected)

    def test_adjusting_already_existing_name_for_the_second_time(self):
        names = {
            "Banana (1)": "Banana (2)",
            "Apple  (3)": "Apple  (4)",
            "Orange (9)": "Orange (10)",
            "Pineapple (10)": "Pineapple (11)",
            "Mango (8": "Mango (9)",
            "Pear (7)  ": "Pear (8)",
            "Plum (  3)": "Plum (4)",
            "Gooseberry (6   )": "Gooseberry (7)",
            "Pomegranate (0)": "Pomegranate (1)",
            "Blackberry ()": "Blackberry (1)",
        }
        for name, expected_name in names.items():
            self.assertEqual(naming.adjust_taken_name(name), expected_name)

    def test_empty_parentheses_at_the_name_end(self):
        name = "Fig ()"
        self.assertEqual(naming.adjust_taken_name(name), "Fig (1)")


class Test_Stripping_And_Joining_Spaces(unittest.TestCase):

    def test_joining(self):
        text = "a    b c"
        self.assertEqual(naming.strip_and_join_spaces(text), "a b c")

    def test_stripping(self):
        text = "  x y "
        self.assertEqual(naming.strip_and_join_spaces(text), "x y")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
