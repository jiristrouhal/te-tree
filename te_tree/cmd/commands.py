from __future__ import annotations
import abc
from typing import List, Any, Callable, Literal, Dict, Type


class Command(abc.ABC):  # pragma: no cover
    def __init__(self, data: Any) -> None:
        self.data = data

    @property
    def message(self) -> str:
        return ""

    @abc.abstractmethod
    def run(self) -> None:
        pass

    @abc.abstractmethod
    def undo(self) -> None:
        pass

    @abc.abstractmethod
    def redo(self) -> None:
        pass


class Empty_Command(Command):
    """
    This commands' purpose is to avoid running other commands if certain condition is not satisfied (e.g. data for command are invalid).
    Running of the empty command is NOT reflected in the controller history.
    """

    def __init__(self, *args, custom_message: str = "") -> None:
        self.__message = custom_message

    @property
    def message(self) -> str:
        return self.__message

    def run(self) -> None:
        pass

    def undo(self) -> None:
        pass

    def redo(self) -> None:
        pass


class Controller:

    def __init__(self) -> None:
        self.__undo_stack: List[List[Command]] = list()
        self.__redo_stack: List[List[Command]] = list()
        self.__run_stack: List[Command] = list()
        self.__history: List[str] = list()
        self.__last_symbol: str = "- "
        self.__waiting: int = 0

    @property
    def any_undo(self) -> bool:
        return bool(self.__undo_stack)

    @property
    def any_redo(self) -> bool:
        return bool(self.__redo_stack)

    @property
    def any_cmd_to_run(self) -> bool:
        return bool(self.__run_stack)

    @property
    def history(self) -> str:
        return 2 * "\n" + "\n".join(self.__history) + "\n"

    def __switch_last_symbol(self) -> None:
        if self.__last_symbol == "x ":
            self.__last_symbol = "- "
        else:
            self.__last_symbol = "x "

    def clear_history(self) -> None:
        self.__history.clear()

    def run(self, *cmds: Command) -> None:
        self.__run_stack.extend(list(cmds))
        if self.__waiting == 0:
            self.__actually_run()

    def __actually_run(self) -> None:
        cmd_list: List[Command] = []
        for item in self.__run_stack:
            cmd_list.append(item)
        self.__run_stack.clear()

        for cmd in cmd_list:
            cmd.run()
        self.__undo_stack.append(cmd_list)
        self.__redo_stack.clear()

        for cmd in cmd_list:
            if cmd.message.strip() != "":
                self.__write_to_history(f"{self.__last_symbol} {cmd.message}")
        self.__switch_last_symbol()

    def undo(self) -> None:
        if not self.__undo_stack:
            return
        batch = self.__undo_stack.pop()
        for cmd in reversed(batch):
            cmd.undo()
            if cmd.message.strip() != "":
                self.__write_to_history(f"{self.__last_symbol}Undo: {cmd.message}")
        self.__redo_stack.append(batch)
        self.__switch_last_symbol()

    def redo(self) -> None:
        if not self.__redo_stack:
            return
        batch = self.__redo_stack.pop()
        for cmd in batch:
            cmd.redo()
            if cmd.message.strip() != "":
                self.__write_to_history(f"{self.__last_symbol}Redo: {cmd.message}")
        self.__undo_stack.append(batch)
        self.__switch_last_symbol()

    def __write_to_history(self, record: str) -> None:
        if record.strip() == "":
            return
        # print(record)
        self.__history.append(record)

    def undo_and_forget(self) -> None:
        if not self.__undo_stack:
            return
        batch = self.__undo_stack.pop()
        for cmd in reversed(batch):
            cmd.undo()
            if cmd.message.strip() != "":
                self.__history.append(f"{self.__last_symbol}Undo: {cmd.message}")

    def _go(self) -> None:
        if self.__waiting > 0:
            self.__waiting -= 1
        if self.__waiting == 0:
            self.__actually_run()

    def _wait(self) -> None:
        self.__waiting += 1

    def single_cmd(self) -> Callable[[Callable], Callable]:
        def outer_wrapper(foo: Callable) -> Callable:
            def inner_wrapper(*args, **kwargs):
                self._wait()
                value = foo(*args, **kwargs)
                self._go()
                return value

            return inner_wrapper

        return outer_wrapper

    def no_undo(self) -> Callable[[Callable], Callable]:
        def outer_wrapper(foo: Callable) -> Callable:
            def inner_wrapper(*args, **kwargs):
                first_forgotten_cmd_index = len(self.__undo_stack)
                value = foo(*args, **kwargs)
                self.__undo_stack = self.__undo_stack[:first_forgotten_cmd_index]
                return value

            return inner_wrapper

        return outer_wrapper


Timing = Literal["pre", "post"]
from typing import Tuple


class Composed_Command(abc.ABC):

    @abc.abstractstaticmethod
    def cmd_type(*args) -> Type[Command]:
        return Command  # pragma: no cover

    def __init__(self) -> None:
        self.composed_pre: Dict[str, Tuple[Callable[[Any], Any], Composed_Command]] = dict()
        self.pre: Dict[str, Callable[[Any], Command]] = dict()
        self.post: Dict[str, Callable[[Any], Command]] = dict()
        self.composed_post: Dict[str, Tuple[Callable[[Any], Any], Composed_Command]] = dict()

    @abc.abstractmethod
    def __call__(self, data: Any) -> Tuple[Command, ...]:

        pre: List[Command] = list()
        for converter, composed_cmd in self.composed_pre.values():
            converted_data = converter(data)
            pre.extend(composed_cmd(converted_data))

        for func in self.pre.values():
            cmd = func(data)
            pre.append(cmd)

        main = self.cmd_type()(data)
        post: List[Command] = []
        for func in self.post.values():
            cmd = func(data)
            post.append(cmd)

        for converter, composed_cmd in self.composed_post.values():
            post.extend(composed_cmd(converter(data)))
        return *pre, main, *post

    @abc.abstractmethod
    def add(self, owner_id: str, creator: Callable[[Any], Command], timing: Timing) -> None:

        if timing == "pre":
            self.pre[owner_id] = creator
        elif timing == "post":
            self.post[owner_id] = creator
        else:
            raise KeyError(f"Invalid timing key: {timing}.")

    @abc.abstractmethod
    def add_composed(
        self,
        owner_id: str,
        data_converter: Callable[[Any], Any],
        cmd: Composed_Command,
        timing: Timing,
    ) -> None:
        if timing == "pre":
            self.composed_pre[owner_id] = (data_converter, cmd)
        elif timing == "post":
            self.composed_post[owner_id] = (data_converter, cmd)
        else:
            raise KeyError(f"Invalid timing key: {timing}.")
