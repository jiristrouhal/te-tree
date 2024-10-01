from __future__ import annotations

import sys

sys.path.insert(1, "src")
import dataclasses


import unittest
from te_tree.cmd.commands import Controller, Command


@dataclasses.dataclass
class Integer_Owner:
    i: int


@dataclasses.dataclass
class IncrementIntData:
    obj: Integer_Owner
    step: int = 1


@dataclasses.dataclass
class MultiplyIntData:
    obj: Integer_Owner
    factor: int = 1


@dataclasses.dataclass
class IncrementOtherIntData:
    obj: Integer_Owner
    other: Integer_Owner


@dataclasses.dataclass
class IncrementIntAttribute(Command):
    data: IncrementIntData

    def run(self) -> None:
        self.data.obj.i += self.data.step

    def undo(self) -> None:
        self.data.obj.i -= self.data.step

    def redo(self) -> None:
        self.data.obj.i += self.data.step


class Test_Running_A_Command(unittest.TestCase):

    def setUp(self) -> None:
        self.obj = Integer_Owner(i=5)
        self.controller = Controller()

    def test_single_undo_returns_the_object_state_back_to_previous_state(self):
        self.controller.run(IncrementIntAttribute(IncrementIntData(self.obj)))
        self.assertEqual(self.obj.i, 6)
        self.controller.undo()
        self.assertEqual(self.obj.i, 5)

    def test_single_undo_and_single_redo_returns_the_object_to_state_after_first_run(
        self,
    ):
        self.controller.run(IncrementIntAttribute(IncrementIntData(self.obj)))
        self.controller.undo()
        self.controller.redo()
        self.assertEqual(self.obj.i, 6)

    def test_second_undo_does_nothing_after_a_single_command_run(self):
        self.controller.run(IncrementIntAttribute(IncrementIntData(self.obj)))
        self.controller.undo()
        self.controller.undo()
        self.assertEqual(self.obj.i, 5)

    def test_after_executing_new_command_redo_has_no_effect(self):
        self.controller.run(IncrementIntAttribute(IncrementIntData(self.obj, step=5)))
        self.controller.undo()
        self.controller.run(IncrementIntAttribute(IncrementIntData(self.obj, step=7)))
        self.assertEqual(self.obj.i, 12)
        self.controller.redo()
        self.assertEqual(self.obj.i, 12)

    def test_examining_if_there_are_undos_available(self):
        self.assertFalse(self.controller.any_undo)
        self.controller.run(IncrementIntAttribute(IncrementIntData(self.obj)))
        self.assertTrue(self.controller.any_undo)
        self.controller.undo()
        self.assertFalse(self.controller.any_undo)

    def test_calling_undo_and_forget_does_not_add_to_redo_stack(self):
        self.assertFalse(self.controller.any_undo)
        self.controller.run(IncrementIntAttribute(IncrementIntData(self.obj)))
        self.controller.undo()
        self.assertFalse(self.controller.any_undo)
        self.assertTrue(self.controller.any_redo)
        self.controller.redo()
        self.assertTrue(self.controller.any_undo)
        self.assertFalse(self.controller.any_redo)
        self.controller.undo_and_forget()
        self.assertFalse(self.controller.any_undo)
        self.assertFalse(self.controller.any_redo)
        self.controller.undo_and_forget()
        self.assertFalse(self.controller.any_undo)
        self.assertFalse(self.controller.any_redo)

    def test_examining_if_there_are_redos_available(self):
        self.assertFalse(self.controller.any_redo)
        self.controller.run(IncrementIntAttribute(IncrementIntData(self.obj)))
        self.assertFalse(self.controller.any_redo)
        self.controller.undo()
        self.assertTrue(self.controller.any_redo)


@dataclasses.dataclass
class MultiplyIntAttribute(Command):
    data: MultiplyIntData
    prev_value: int = dataclasses.field(init=False)
    new_value: int = dataclasses.field(init=False)

    def run(self) -> None:
        self.prev_value = self.data.obj.i
        self.data.obj.i *= self.data.factor
        self.new_value = self.data.obj.i

    def undo(self) -> None:
        self.data.obj.i = self.prev_value

    def redo(self) -> None:
        self.data.obj.i = self.new_value


class Test_Running_Multiple_Commands(unittest.TestCase):

    def test_undo_and_redo_two_commands_at_once(self) -> None:
        obj = Integer_Owner(0)
        controller = Controller()
        controller.run(
            IncrementIntAttribute(IncrementIntData(obj, 2)),
            MultiplyIntAttribute(MultiplyIntData(obj, 3)),
        )
        self.assertEqual(obj.i, 6)

        controller.undo()
        self.assertEqual(obj.i, 0)
        controller.redo()
        self.assertEqual(obj.i, 6)
        controller.undo()
        self.assertEqual(obj.i, 0)


from te_tree.cmd.commands import Composed_Command, Timing


from typing import Any, Callable


class Composed_Increment(Composed_Command):
    @staticmethod
    def cmd_type():
        return IncrementIntAttribute

    def __call__(self, data: IncrementIntData):
        return super().__call__(data)

    def add(
        self, owner_id: str, func: Callable[[IncrementIntData], Command], timing: Timing
    ) -> None:
        super().add(owner_id, func, timing)

    def add_composed(
        self,
        owner_id: str,
        data_converter: Callable[[IncrementIntData], Any],
        cmd: Composed_Command,
        timing: Timing,
    ) -> None:

        return super().add_composed(owner_id, data_converter, cmd, timing)


@dataclasses.dataclass
class Increment_Other_Int(Command):
    data: IncrementOtherIntData
    prev_value: int = dataclasses.field(init=False)
    curr_value: int = dataclasses.field(init=False)

    def run(self) -> None:
        self.prev_value = self.data.other.i
        self.data.other.i = self.data.obj.i
        self.curr_value = self.data.other.i

    def undo(self) -> None:
        self.data.other.i = self.prev_value

    def redo(self) -> None:
        self.data.other.i = self.curr_value


class Test_Composed_Command(unittest.TestCase):

    def setUp(self) -> None:
        self.obj = Integer_Owner(i=0)
        self.other_int = Integer_Owner(i=0)
        self.controller = Controller()

    def get_cmd(self, data: IncrementIntData) -> Increment_Other_Int:
        return Increment_Other_Int(IncrementOtherIntData(data.obj, self.other_int))

    def test_composed_command(self):
        composed_command = Composed_Increment()

        composed_command.add("test", self.get_cmd, "post")
        self.controller.run(*composed_command(IncrementIntData(self.obj, step=5)))
        self.assertEqual(self.obj.i, 5)
        self.assertEqual(self.other_int.i, 5)
        self.controller.run(*composed_command(IncrementIntData(self.obj, step=4)))
        self.assertEqual(self.obj.i, 9)
        self.assertEqual(self.other_int.i, 9)
        self.controller.undo()
        self.assertEqual(self.obj.i, 5)
        self.assertEqual(self.other_int.i, 5)
        self.controller.redo()
        self.assertEqual(self.obj.i, 9)
        self.assertEqual(self.other_int.i, 9)
        self.controller.undo()
        self.assertEqual(self.obj.i, 5)
        self.assertEqual(self.other_int.i, 5)

    def test_adding_command_under_invalid_timing_key(self):
        composed_command = Composed_Increment()
        with self.assertRaises(KeyError):
            composed_command.add(
                owner_id="test", func=self.get_cmd, timing="invalid key"
            )

    def test_adding_composed_command_under_invalid_timing_key(self):
        composed_command = Composed_Increment()

        def data_converter(
            input_data: IncrementIntData,
        ) -> IncrementIntData:  # pragma: no cover
            return input_data

        with self.assertRaises(KeyError):
            composed_command.add_composed(
                owner_id="test",
                cmd=self.get_cmd,
                data_converter=data_converter,
                timing="invalid key",
            )

    def test_adding_composed_command_to_composed_command(self):
        composed_command_pre = Composed_Increment()
        composed_command = Composed_Increment()
        composed_command_post = Composed_Increment()

        composed_command_post.add("test", self.get_cmd, "post")

        def data_converter(input_data: IncrementIntData) -> IncrementIntData:
            return input_data

        # each composed command should increment the integer by 5

        # the composed_command_pre adds the first 5 to the integer
        composed_command.add_composed(
            "test", data_converter, composed_command_pre, "pre"
        )
        # the post-command of the composed_command follows, adding another 5

        # at last, the composed_command_post adds 5, which yields 15 in total
        composed_command.add_composed(
            "test", data_converter, composed_command_post, "post"
        )

        # the increment is set the same for all three composed commands
        self.controller.run(*composed_command(IncrementIntData(self.obj, step=5)))
        self.assertEqual(self.obj.i, 15)

        # after resetting the integer to zero, is is possible to set up the data converter
        # such that the increment for the pre and post composed_command differs from the
        # origina increment

        self.obj.i = 0

        def data_converter(input_data: IncrementIntData) -> IncrementIntData:
            return IncrementIntData(input_data.obj, step=2)

            # return IncrementIntData(input_data)

        # replaces the original pre- composed_command
        composed_command.add_composed(
            "test", data_converter, composed_command_pre, "pre"
        )
        composed_command.add_composed(
            "test", data_converter, composed_command_post, "post"
        )
        self.controller.run(*composed_command(IncrementIntData(self.obj, step=5)))
        self.assertEqual(self.obj.i, 9)


@dataclasses.dataclass
class Increment_With_Message(Command):
    data: IncrementIntData

    def run(self) -> None:
        self.data.obj.i += self.data.step

    def undo(self) -> None:
        self.data.obj.i -= self.data.step

    def redo(self) -> None:
        self.data.obj.i += self.data.step

    @property
    def message(self) -> str:
        return "Increment"


class Test_Command_History(unittest.TestCase):

    def test_writing_command_history_line(self):
        controller = Controller()
        obj = Integer_Owner(i=0)
        controller.run(Increment_With_Message(IncrementIntData(obj, step=5)))
        self.assertEqual(obj.i, 5)
        self.assertEqual(controller.history, "\n\n-  Increment\n")
        controller.run(Increment_With_Message(IncrementIntData(obj, step=5)))
        self.assertEqual(controller.history, "\n\n-  Increment\n" "x  Increment\n")
        controller.undo()
        controller.redo()
        self.assertEqual(
            controller.history,
            "\n\n-  Increment\n"
            "x  Increment\n"
            "- Undo: Increment\n"
            "x Redo: Increment\n",
        )


from te_tree.cmd.commands import Empty_Command


class Test_Empty_Command(unittest.TestCase):

    def test_empty_command(self) -> None:
        controller = Controller()
        controller.run(Empty_Command())
        controller.run(Empty_Command())
        controller.run(Empty_Command())
        controller.run(Empty_Command())
        self.assertEqual(controller.history.strip(), "")
        self.assertEqual(controller.history.strip(), "")
        controller.undo()
        controller.undo()
        self.assertEqual(controller.history.strip(), "")
        controller.redo()
        self.assertEqual(controller.history.strip(), "")


class Test_Denoting_Multiple_Commands_As_A_Single_One(unittest.TestCase):

    def test_two_commands(self) -> None:
        controller = Controller()
        obj = Integer_Owner(i=0)

        @controller.single_cmd()
        def increment_two_times() -> None:
            controller.run(IncrementIntAttribute(IncrementIntData(obj, step=5)))
            controller.run(IncrementIntAttribute(IncrementIntData(obj, step=5)))

        increment_two_times()
        self.assertFalse(controller.any_cmd_to_run)
        self.assertEqual(obj.i, 10)
        increment_two_times()
        self.assertFalse(controller.any_cmd_to_run)
        self.assertEqual(obj.i, 20)

        controller.undo()
        self.assertEqual(obj.i, 10)

    def test_nested_command_groupings(self):
        controller = Controller()
        obj = Integer_Owner(i=0)

        @controller.single_cmd()
        def increment_two_times() -> None:
            controller.run(IncrementIntAttribute(IncrementIntData(obj, step=5)))
            controller.run(IncrementIntAttribute(IncrementIntData(obj, step=5)))

        @controller.single_cmd()
        def increment_two_times_two_times() -> None:
            increment_two_times()
            increment_two_times()

        increment_two_times_two_times()
        self.assertEqual(obj.i, 20)

        controller.undo()
        self.assertEqual(obj.i, 0)


if __name__ == "__main__":
    unittest.main()
