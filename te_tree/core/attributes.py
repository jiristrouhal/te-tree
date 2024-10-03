from __future__ import annotations

from typing import Literal, Any, Callable, get_args, Tuple, Dict
import abc
import dataclasses

from te_tree.cmd.commands import Command, Composed_Command, Timing, Controller


NBSP = "\u00A0"


from decimal import Decimal, getcontext

getcontext().prec = 28
Locale_Code = Literal["cs_cz", "en_us"]


class Dependency(abc.ABC):

    def __init__(
        self,
        output: AbstractAttribute,
        func: Callable[[Any], Any],
        *inputs: AbstractAttribute,
        label: str = "",
    ):
        self._output = output
        self.func = func
        self.__label = label
        if not inputs:
            raise Dependency.NoInputs
        self._inputs = list(inputs)
        if self._output.dependent:
            raise Attribute.DependencyAlreadyAssigned
        self.__check_input_types()
        self._check_for_dependency_cycle(self._output, path=self._output.name)
        self.__set_up_command(*self._inputs)

    @abc.abstractmethod
    def release(self) -> None:
        pass  # pragma: no cover

    @property
    def output(self) -> AbstractAttribute:
        return self._output

    def __check_input_types(self) -> None:
        values = self.collect_input_values()
        try:
            result = self(*values)
            self._output.is_valid(result)
        except Dependency.InvalidArgumentType:
            raise Dependency.WrongAttributeTypeForDependencyInput([type(v) for v in values])

    def collect_input_values(self) -> List[Any]:
        return [item.value for item in self._inputs]

    def replace_input(self, input: AbstractAttribute, new_input: AbstractAttribute) -> None:
        if input not in self._inputs:
            raise Dependency.AttributeIsNotInput(input.name)
        if new_input in self._inputs and new_input is not input:
            raise Dependency.SingleAttributeForMultipleInputs
        if new_input.type != input.type:
            raise Dependency.WrongAttributeTypeForDependencyInput(
                f"Expected type '{new_input.type}', received '{input.type}'."
            )
        id = self._inputs.index(input)
        self._inputs[id] = new_input
        self.__set_up_command(new_input)
        input.command["set"].composed_post.pop(self.output.id)

    def _check_for_dependency_cycle(self, output: AbstractAttribute, path: str) -> None:
        if output in self._inputs:
            raise Dependency.CyclicDependency(path + " -> " + output.name)
        for input in self._inputs:
            if not input.dependent:
                continue
            input.dependency._check_for_dependency_cycle(output, path + " -> " + input.name)

    def _add_set_up_command_to_input(self, *inputs: AbstractAttribute) -> None:
        for input in inputs:
            input.command["set"].add_composed(
                self._output.id,
                self._data_converter,
                self._output.command["set"],
                "post",
            )

    def _data_converter(self, *args) -> Set_Attr_Data:
        value_getter = lambda: self(*self.collect_input_values())
        return Set_Attr_Data(self._output, value_getter)

    def _set_output_value(self, *args) -> Command:
        return Set_Attr(self._data_converter(*args), custom_message=self.__label)

    def __set_up_command(self, *inputs: AbstractAttribute):
        self._output.factory.run(self._set_output_value())
        self._add_set_up_command_to_input(*inputs)

    def __call__(self, *values) -> Any:
        try:
            result = self.func(*values)
            return result
        except ValueError:
            return float("nan")
        except ZeroDivisionError:
            return float("nan")
        except TypeError:
            raise self.InvalidArgumentType(
                f"Func {self.func.__annotations__} received values: {list(values)}, "
                f"expected types :{[i.type for i in self._inputs]}"
            )
        except:  # pragma: no cover
            return None  # pragma: no cover

    class AttributeIsNotInput(Exception):
        pass

    class CyclicDependency(Exception):
        pass

    class InputAlreadyUsed(Exception):
        pass

    class InvalidArgumentType(Exception):
        pass

    class NoInputs(Exception):
        pass

    class NonexistentInput(Exception):
        pass

    class SingleAttributeForMultipleInputs(Exception):
        pass

    class WrongAttributeTypeForDependencyInput(Exception):
        pass


class DependencyImpl(Dependency):
    class NullDependency(Dependency):  # pragma: no cover
        def __init__(self) -> None:
            self.func: Callable = lambda x: None
            self.attributes: List[AbstractAttribute] = list()

        def release(self) -> None:
            pass

        def __str__(self) -> str:
            return "NULL"

    NULL = NullDependency()

    def release(self) -> None:
        for input in self._inputs:
            input.command["set"].composed_post.pop(self.output.id)
            self._inputs.remove(input)
        self.output._forget_dependency()


@dataclasses.dataclass
class Set_Attr_Data:
    attr: AbstractAttribute
    value: Callable[[], Any]


@dataclasses.dataclass
class Set_Attr(Command):
    data: Set_Attr_Data
    custom_message: str = ""
    old_value: Any = dataclasses.field(init=False)
    new_value: Any = dataclasses.field(init=False)

    @property
    def message(self) -> str:
        msg = f"Set Attribute | {self.data.attr.name}: Set to {self.new_value}"
        if self.custom_message.strip() != "":
            msg += f" ({self.custom_message})"
        return msg

    def run(self) -> None:
        if isinstance(self.data.attr, Attribute_List):
            self.old_value = {attr: attr.value for attr in self.data.attr.attributes}
            values = {
                attr: value for attr, value in zip(self.data.attr.attributes, self.data.value())
            }
            self.data.attr._value_update(values, f"Set_Attr - {self.data.attr.name}")
            self.new_value = values.copy()
        else:
            self.old_value = self.data.attr.value
            values = self.data.value()
            self.data.attr._value_update(values, f"Set_Attr - {self.data.attr.name}")
            self.new_value = self.data.attr.value

    def undo(self) -> None:
        self.data.attr._value_update(self.old_value, f"UNDO Set_Attr - {self.data.attr.name}")

    def redo(self) -> None:
        self.data.attr._value_update(self.new_value, f"REDO Set_Attr - {self.data.attr.name}")


class Set_Attr_Composed(Composed_Command):
    @staticmethod
    def cmd_type():
        return Set_Attr

    def __call__(self, data: Set_Attr_Data):
        return super().__call__(data)

    def add(self, owner: str, func: Callable[[Set_Attr_Data], Command], timing: Timing) -> None:
        super().add(owner, func, timing)

    def add_composed(
        self,
        owner_id: str,
        data_converter: Callable[[Set_Attr_Data], Any],
        cmd: Composed_Command,
        timing: Timing,
    ) -> None:
        return super().add_composed(owner_id, data_converter, cmd, timing)


@dataclasses.dataclass
class Edit_AttrList_Data:
    alist: Attribute_List
    attribute: AbstractAttribute


@dataclasses.dataclass
class Append_To_Attribute_List(Command):
    data: Edit_AttrList_Data
    composed_post_set: Tuple[Callable, Composed_Command] = dataclasses.field(init=False)

    @property
    def message(self) -> str:
        return f"Append attribute to list | Attribute '{self.data.attribute.name}' appended to '{self.data.alist.name}'."

    def run(self) -> None:
        self.data.alist._add(self.data.attribute)

        def get_list_set_data(data: Set_Attr_Data) -> Set_Attr_Data:
            value_getter = lambda: self.data.alist.value + [data.value()]
            return Set_Attr_Data(self.data.alist, value_getter)

        self.data.attribute.command["set"].add_composed(
            owner_id=self.data.alist.id,
            data_converter=get_list_set_data,
            cmd=self.data.alist.command["set"],
            timing="post",
        )

    def undo(self) -> None:
        self.data.alist._remove(self.data.attribute)
        # do not trigger value update of this list when the value of the attribute just removed is set
        self.composed_post_set = self.data.attribute.command["set"].composed_post.pop(
            self.data.alist.id
        )

    def redo(self) -> None:
        self.data.alist._add(self.data.attribute)
        self.data.attribute.command["set"].composed_post[
            self.data.alist.id
        ] = self.composed_post_set


@dataclasses.dataclass
class Remove_From_Attribute_List(Command):
    data: Edit_AttrList_Data
    composed_post_set: Tuple[Callable, Composed_Command] = dataclasses.field(init=False)

    def run(self) -> None:
        self.data.alist._remove(self.data.attribute)
        self.composed_post_set = self.data.attribute.command["set"].composed_post.pop(
            self.data.alist.id
        )

    def undo(self) -> None:
        self.data.alist._add(self.data.attribute)
        self.data.attribute.command["set"].composed_post[
            self.data.alist.id
        ] = self.composed_post_set

    def redo(self) -> None:
        self.data.alist._remove(self.data.attribute)
        self.composed_post_set = self.data.attribute.command["set"].composed_post.pop(
            self.data.alist.id
        )

    @property
    def message(self) -> str:
        return f"Remove attribute from list | Attribute '{self.data.attribute.name}' removed from '{self.data.alist.name}'."


class AbstractAttribute(abc.ABC):
    NullDependency = DependencyImpl.NULL

    def __init__(self, factory: Attribute_Factory, atype: AttributeType, name: str = "") -> None:
        if not isinstance(name, str):
            raise AbstractAttribute.Invalid_Name
        self.__name = name
        self.__type = atype
        self.command: Dict[Command_Type, Composed_Command] = {"set": Set_Attr_Composed()}
        self.__id = str(id(self))
        self.__factory = factory
        self._dependency: Dependency = DependencyImpl.NULL

    @property
    def name(self) -> str:
        return self.__name

    @abc.abstractproperty
    def value(self) -> Any:
        pass  # pragma: no cover

    @property
    def factory(self) -> Attribute_Factory:
        return self.__factory

    @property
    def id(self) -> str:
        return self.__id

    @property
    def type(self) -> AttributeType:
        return self.__type

    @property
    def dependency(self) -> Dependency:
        return self._dependency

    @property
    def dependent(self) -> bool:
        return self._dependency is not Attribute.NullDependency

    def add_dependency(
        self,
        func: Callable[[Any], Any],
        *attributes: AbstractAttribute,
        label: str = "",
    ) -> Dependency:
        self._dependency = DependencyImpl(self, func, *attributes, label=label)
        return self._dependency

    def break_dependency(self) -> None:
        if not self.dependent:
            raise Attribute.NoDependencyIsSet(self.name)
        self._dependency.release()

    @abc.abstractmethod
    def copy(self) -> AbstractAttribute:
        pass  # pragma: no cover

    def _forget_dependency(self) -> None:
        self._dependency = self.NullDependency

    @abc.abstractmethod
    def is_valid(self, value: Any) -> bool:
        pass  # pragma: no cover

    @abc.abstractmethod
    def set(self, value: Any) -> None:
        pass  # pragma: no cover

    def rename(self, name: str) -> None:
        if not isinstance(name, str):
            raise AbstractAttribute.Invalid_Name
        self.__name = name

    @abc.abstractmethod
    def on_set(
        self, owner: str, func: Callable[[Set_Attr_Data], Command], timing: Timing
    ) -> None:  # pragma: no cover

        pass

    @abc.abstractmethod
    def _value_update(self, new_value: Any, msg: str = "") -> None:
        pass  # pragma: no cover

    class Invalid_Name(Exception):
        pass


from typing import Iterator

Attr_List_Command_Type = Literal["append", "remove"]


class Attribute_List(AbstractAttribute):

    def __init__(
        self,
        factory: Attribute_Factory,
        atype: AttributeType,
        name: str = "",
        init_attributes: List[Any] | None = None,
    ) -> None:

        super().__init__(factory, atype, name)
        self.__attributes: List[AbstractAttribute] = list()
        self._set_commands: Dict[str, Callable[[Set_Attr_Data], Command]] = dict()

        if isinstance(init_attributes, list):
            for attr_value in init_attributes:
                attr = factory.new(atype)
                attr.set(attr_value)
                self.append(attr)

    @property
    def value(self) -> List[Any]:
        return [attr.value for attr in self.__attributes]

    @property
    def attributes(self) -> List[AbstractAttribute]:
        return self.__attributes.copy()

    def add_dependency(
        self, func: Callable[[Any], Any], *attributes: AbstractAttribute
    ) -> Dependency:
        if any([item.dependent for item in self.__attributes]):
            raise Attribute_List.ItemIsAlreadyDependent
        super().add_dependency(func, *attributes)
        for item in self.__attributes:
            item._dependency = self._dependency
        return self._dependency

    def break_dependency(self) -> None:
        super().break_dependency()
        for item in self.__attributes:
            item._dependency = DependencyImpl.NULL

    def append(self, attribute: AbstractAttribute) -> None:
        if isinstance(attribute, Attribute_List):
            self._check_hierarchy_collision(attribute, self)
        self.__check_new_attribute_type(attribute)
        value_getter = lambda: self.value
        self.factory.run(
            Append_To_Attribute_List(Edit_AttrList_Data(self, attribute)),
            *self.command["set"](Set_Attr_Data(self, value_getter)),
        )

    def copy(self) -> Attribute_List:
        the_copy = self.factory.newlist(self.type, name=self.name)
        for item in self.__attributes:
            the_copy.__attributes.append(item.copy())
        return the_copy

    def is_valid(self, values: List[Any]) -> bool:
        return all([attr.is_valid(value) for attr, value in zip(self.__attributes, values)])

    def remove(self, attribute: AbstractAttribute) -> None:
        if attribute not in self.__attributes:
            raise Attribute_List.NotInList(attribute)
        value_getter = lambda: self.value
        self.factory.run(
            Remove_From_Attribute_List(Edit_AttrList_Data(self, attribute)),
            *self.command["set"](Set_Attr_Data(self, value_getter)),
        )

    def on_set(self, owner: str, func: Callable[[Set_Attr_Data], Command], timing: Timing) -> None:
        self.command["set"].add(owner, func, timing)
        self._set_commands[owner] = func

    def set(self, value: Any = None) -> None:
        value_getter = lambda: self.value
        self.factory.run(*self.command["set"](Set_Attr_Data(self, value_getter)))

    def _add(self, attributes: AbstractAttribute) -> None:
        self.__attributes.append(attributes)

    @staticmethod
    def _check_hierarchy_collision(alist: Attribute_List, root_list: Attribute_List) -> None:
        if alist is root_list:
            raise Attribute_List.ListContainsItself
        for attr in alist:
            if isinstance(attr, Attribute_List):
                attr._check_hierarchy_collision(attr, root_list)

    def _remove(self, attributes: AbstractAttribute) -> None:
        self.__attributes.remove(attributes)

    def _value_update(self, values: Dict[AbstractAttribute, Any], msg: str = "") -> None:
        for attr in self.__attributes:
            if isinstance(attr, Attribute_List):
                vals = {attr: value for attr, value in zip(attr.attributes, values[attr])}
                attr._value_update(vals)
            else:
                attr._value_update(values[attr])

    def __iter__(self) -> Iterator[AbstractAttribute]:
        return self.__attributes.__iter__()

    def __getitem__(self, index: int) -> AbstractAttribute:
        return self.__attributes[index]

    def __check_new_attribute_type(self, attr: AbstractAttribute) -> None:
        if not attr.type == self.type:
            raise Attribute_List.WrongAttributeType(
                f"Type {attr.type} of the attribute does not match the type of the list {self.type}."
            )

    class ItemIsAlreadyDependent(Exception):
        pass

    class ListContainsItself(Exception):
        pass

    class NotInList(Exception):
        pass

    class NotMatchingListLengths(Exception):
        pass

    class WrongAttributeType(Exception):
        pass


Command_Type = Literal["set"]
from typing import Set, List


class Attribute(AbstractAttribute):
    default_value: Any = ""
    minimum_value: Any = ""

    def __init__(
        self,
        factory: Attribute_Factory,
        atype: AttributeType = "text",
        init_value: Any = None,
        name: str = "",
        custom_condition: Callable[[Any], bool] = lambda x: True,
    ) -> None:

        self.__custom_condition = custom_condition
        super().__init__(factory, atype, name)
        if init_value is not None and self.is_valid(init_value):
            self._value = init_value
        else:
            self._value = self.default_value
        self.__actions: List[Callable[[Attribute], None]] = list()

        self.__actions_on_set: Dict[str, Callable[[], None]] = dict()

    @property
    def value(self) -> Any:
        return self._value

    @property
    def custom_condition(self) -> bool:
        return self.__custom_condition

    def add_action_on_set(self, owner_id: str, action: Callable[[], None]) -> None:
        self.__actions_on_set[owner_id] = action

    def remove_action_on_set(self, owner_id: str) -> None:
        self.__actions_on_set.pop(owner_id)

    def _hard_set(self, value: Any):
        if self.is_valid(value):
            self._value = value

    def after_set(self, action: Callable[[Attribute], None]) -> None:
        if action not in self.__actions:
            self.__actions.append(action)

    def copy(self) -> Attribute:
        the_copy = self.factory.new(self.type, init_value=self._value, name=self.name)
        return the_copy

    def on_set(self, owner: str, func: Callable[[Set_Attr_Data], Command], timing: Timing) -> None:
        self.command["set"].add(owner, func, timing)

    @abc.abstractmethod
    def print(self, *options) -> str:
        pass  # pragma: no cover

    def read(self, text: str, overwrite_dependent: bool = False) -> None:
        value = self.__class__.value_from_text(text=text)
        if self.is_valid(value):
            self.set(value, overwrite_dependent)

    def set(self, value: Any, overwrite_dependent: bool = False) -> None:
        if not overwrite_dependent and self._dependency is not DependencyImpl.NULL:
            return
        if self.is_valid(value):
            self._run_set_command(value)

    def set_validity_condition(self, func: Callable[[Any], bool]) -> None:
        self.__custom_condition = func

    def is_valid(self, value: Any, raise_value_type_exception: bool = True) -> bool:
        if not self._is_type_valid(value):
            if raise_value_type_exception:
                raise Attribute.InvalidValueType(type(value))
            else:
                return False
        return self._is_value_valid(value) and self.__custom_condition(value)

    @abc.abstractstaticmethod
    def value_from_text(text: str, *args) -> Any:
        pass  # pragma: no cover

    @abc.abstractmethod
    def _is_type_valid(self, value: Any) -> bool:
        pass  # pragma: no cover

    def _get_set_commands(self, value: Any) -> List[Command]:
        value_getter = lambda: value
        return list(self.command["set"](Set_Attr_Data(self, value_getter)))

    @abc.abstractmethod
    def _is_value_valid(self, value: Any) -> bool:
        pass  # pragma: no cover

    def _run_set_command(self, value: Any) -> None:
        self.factory.controller.run(*self._get_set_commands(value))

    def _value_update(self, value: Any, msg: str = "") -> None:
        self._value = value
        self.__run_actions_after_setting_the_value()

    def __run_actions_after_setting_the_value(self) -> None:
        for action in self.__actions:
            action(self)
        for action_on_set in self.__actions_on_set.values():
            action_on_set()

    @staticmethod
    def set_multiple(new_values: Dict[Attribute, Any]) -> None:
        facs: List[Attribute_Factory] = list()
        cmds: List[List[Command]] = list()
        for attr, value in new_values.items():
            if attr.dependent:
                continue  # ignore dependent attributes
            if (
                not attr.factory in facs
            ):  # Attribute_Factory is not hashable, two lists circumvent the problem
                facs.append(attr.factory)
                cmds.append(list())
            cmds[facs.index(attr.factory)].extend(attr._get_set_commands(value))

        for fac, cmd_list in zip(facs, cmds):
            fac.controller.run(*cmd_list)

    class DependencyAlreadyAssigned(Exception):
        pass

    class InvalidAttributeType(Exception):
        pass

    class InvalidDefaultValue(Exception):
        pass

    class InvalidValueType(Exception):
        pass

    class InvalidValue(Exception):
        pass

    class NoDependencyIsSet(Exception):
        pass


from math import inf


class Number_Attribute(Attribute):
    default_value = 0
    minimum_value: float = -inf

    class CannotExtractNumber(Exception):
        pass

    _reading_exception: Type[Exception] = CannotExtractNumber

    @property
    def comma_as_dec_separator(self) -> bool:  # pragma: no cover
        return self.factory.locale_code in Number_Attribute.Comma_Separator

    @abc.abstractmethod
    def _is_type_valid(self, value: Any) -> bool:  # pragma: no cover
        pass

    @abc.abstractmethod  # pragma: no cover
    def print(self, use_thousands_separator: bool = False, *options) -> str:

        pass

    @staticmethod
    def value_from_text(text: str) -> Any:
        text = text.strip().replace(",", ".")
        text = Number_Attribute.remove_thousands_separators(text)
        try:
            value = Decimal(text)
            return value
        except:
            raise Number_Attribute._reading_exception

    @staticmethod
    def _is_a_number(value: Any) -> bool:
        return isinstance(value, int) or isinstance(value, Decimal) or isinstance(value, float)

    @staticmethod
    def _is_text_a_number(value: str) -> bool:
        DECIMAL_PATT = "(([\-\+]?[0-9]+)|([\-\+][0-9]*))(\.[0-9]*)?"
        return re.fullmatch(f"{DECIMAL_PATT}", value) is not None

    Comma_Separator: Set[str] = {
        "cs_cz",
    }

    def _adjust_decimal_separator(self, value: str) -> str:
        if self.factory.locale_code in Number_Attribute.Comma_Separator:
            value = value.replace(".", ",")
        return value

    @staticmethod
    def _set_thousands_separator(value_str: str, use_thousands_separator: bool) -> str:
        if use_thousands_separator:
            return value_str.replace(",", NBSP)
        else:
            return value_str.replace(",", "")

    @staticmethod
    def is_int(value) -> bool:
        return int(value) == value

    @staticmethod
    def remove_thousands_separators(value_str: str) -> str:
        for sep in (" ", NBSP, "\t"):
            value_str = value_str.replace(sep, "")
        return value_str


class Integer_Attribute(Number_Attribute):
    class CannotExtractInteger(Exception):
        pass

    _reading_exception: Type[Exception] = CannotExtractInteger

    def _is_type_valid(self, value: Any) -> bool:
        if Number_Attribute._is_a_number(value):
            return Decimal(int(value)) == Decimal(str(value))
        else:
            return False

    def _is_value_valid(self, value: Any) -> bool:
        return True

    def print(self, use_thousands_separator: bool = False, *options) -> str:

        value_str = f"{self._value:,}"
        value_str = self._set_thousands_separator(value_str, use_thousands_separator)
        return value_str

    @staticmethod
    def value_from_text(text: str, *args) -> Any:
        text = text.strip().replace(",", ".")
        text = Integer_Attribute.remove_thousands_separators(text)
        try:
            value = Decimal(text)
            int_value = int(value)
            if value != int_value:
                raise
            return int_value
        except:
            raise Integer_Attribute._reading_exception


class Real_Attribute(Number_Attribute):
    class CannotExtractReal(Exception):
        pass

    _reading_exception: Type[Exception] = CannotExtractReal

    def __init__(
        self,
        factory: Attribute_Factory,
        atype: AttributeType,
        init_value: Any = None,
        name: str = "",
        custom_condition: Callable[[Any], bool] = lambda x: True,
    ) -> None:

        if init_value is not None:
            try:
                init_value = Decimal(str(init_value))
            except:
                raise Attribute.InvalidValueType(init_value)
        super().__init__(factory, atype, init_value, name, custom_condition)
        if init_value is not None and self.is_valid(init_value):
            init_value = Decimal(str(init_value))

    def _is_type_valid(self, value: Decimal | float | int) -> bool:
        return Number_Attribute._is_a_number(value)

    def _is_value_valid(self, value: Any) -> bool:
        return True

    def print(
        self,
        use_thousands_separator: bool = False,
        trailing_zeros: bool = False,
        adjust: Optional[Callable[[float | Decimal], float | Decimal]] = None,
        precision: int = 28,
        *args,
    ) -> str:
        if adjust is None:
            value = self._value
        else:
            try:
                value = adjust(self._value)
                if not self.is_valid(value):
                    raise Real_Attribute.InvalidAdjustedValue(value)
            except Exception:
                raise Real_Attribute.InvalidAdjustedValue(f"Original value: {self._value}.")

        str_value = format(value, f",.{precision}f")
        str_value = self._set_thousands_separator(str_value, use_thousands_separator)
        if "." in str_value and not trailing_zeros:
            str_value = str_value.rstrip("0").rstrip(".")
        str_value = self._adjust_decimal_separator(str_value)
        return str_value

    def set(self, value: Decimal | float | int, overwrite_dependent: bool = False) -> None:
        if not overwrite_dependent and self.dependent:
            return
        if self.is_valid(value):
            value = Decimal(str(value))
            self._run_set_command(value)
        else:  # pragma: no cover
            raise Attribute.InvalidValue(value)

    @staticmethod
    def value_from_text(text: str, *args) -> Any:
        text = text.strip().replace(",", ".")
        text = Real_Attribute.remove_thousands_separators(text)
        try:
            value = Decimal(text)
            return value
        except:
            raise Real_Attribute._reading_exception

    class InvalidAdjustedValue(Exception):
        pass


class Real_Attribute_Dimensionless(Real_Attribute):
    pass


Currency_Code = Literal["USD", "EUR", "CZK", "JPY"]
Currency_Symbol = Literal["$", "€", "Kč", "¥"]


@dataclasses.dataclass
class Currency:
    code: Currency_Code
    symbol: Currency_Symbol
    decimals: Literal[0, 2] = 2
    symbol_before_value: bool = True


class Monetary_Attribute(Number_Attribute):

    def __init__(
        self,
        factory: Attribute_Factory,
        atype: AttributeType,
        init_value: Any = None,
        name: str = "",
        custom_condition: Callable[[Any], bool] = lambda x: True,
        enforce_sign: bool = False,
    ) -> None:

        super().__init__(factory, atype, init_value, name, custom_condition)
        self.__enforce_sign = enforce_sign

    Currencies: Dict[Currency_Code, Currency] = {
        "USD": Currency("USD", "$"),
        "EUR": Currency("EUR", "€"),
        "CZK": Currency("CZK", "Kč", symbol_before_value=False),
        "JPY": Currency("JPY", "¥", decimals=0),
    }

    def prefer_symbol_before_value(self) -> bool:
        preferred_by: Set[Locale_Code] = {"en_us"}
        return self.factory.locale_code in preferred_by

    def _is_type_valid(self, value: float | int | Decimal) -> bool:
        return Number_Attribute._is_a_number(value)

    def _is_value_valid(self, value: float | int | Decimal) -> bool:
        return True

    def set(self, value: float | Decimal, overwrite_dependent: bool = False) -> None:
        # For the sake of clarity, the input to the set method has to be kept in the same type as the
        # '_value' attribute.

        # The string must then be explicitly excluded from input types, as it would normally be
        # accepted by the Decimal.
        if isinstance(value, str):
            raise Attribute.InvalidValueType(value)
        super().set(Decimal(str(value)), overwrite_dependent)

    def print(
        self,
        use_thousands_separator: bool = False,
        trailing_zeros: bool = True,
        enforce_plus: bool = False,
        show_symbol: bool = True,
        *options,
    ) -> str:

        currency = self.Currencies[self.factory.currency_code]

        if not trailing_zeros and int(self._value) == self._value:
            n_places = 0
        else:
            n_places = currency.decimals
        value_str = format(round(self._value, n_places), ",." + str(n_places) + "f")
        value_str = self._set_thousands_separator(value_str, use_thousands_separator)
        # decimal separator is adjusted AFTER setting thousands separator to avoid collisions when comma
        # is used for one or the other
        value_str = self._adjust_decimal_separator(value_str)

        if show_symbol:
            value_str = self.__add_symbol_to_printed_value(value_str, currency)
        if (self.__enforce_sign or enforce_plus) and self._value > 0:
            value_str = "+" + value_str
        return value_str

    @staticmethod
    def value_from_text(text: str, *args) -> Any:
        text = text.strip()
        text = Monetary_Attribute.remove_thousands_separators(text)
        if text == "":
            raise Monetary_Attribute.ReadingBlankText
        sign, symbol, value = Monetary_Attribute.__extract_sign_symbol_and_value(text)
        return Decimal(sign + value)

    SYMBOL_PATTERN = "(?P<symbol>[^\s\d\.\,]+)"
    VALUE_PATTERN = "(?P<value>[0-9]+([\.\,][0-9]*)?)"
    SYMBOL_FIRST = f"({SYMBOL_PATTERN}{VALUE_PATTERN})"
    VALUE_FIRST = f"({VALUE_PATTERN}[ \t{NBSP}]?{SYMBOL_PATTERN})"

    @staticmethod
    def __extract_sign_symbol_and_value(text: str) -> Tuple[str, str, str]:
        sign, text = Monetary_Attribute.__extract_sign(text)
        thematch = re.match(Monetary_Attribute.SYMBOL_FIRST, text)
        if thematch is None:
            thematch = re.match(Monetary_Attribute.VALUE_FIRST, text)
        if thematch is None:
            raise Monetary_Attribute.CannotExtractValue(text)
        if thematch["symbol"] not in get_args(Currency_Symbol):
            raise Monetary_Attribute.UnknownCurrencySymbol(thematch["symbol"])
        return sign, thematch["symbol"], thematch["value"].replace(",", ".")

    @staticmethod
    def __extract_sign(text: str) -> Tuple[str, str]:
        if text[0] in ("+", "-"):
            sign, text = text[0], text[1:]
        else:
            sign = "+"
        return sign, text

    def __add_symbol_to_printed_value(self, value: str, currency: Currency) -> str:

        if self.prefer_symbol_before_value() and currency.symbol_before_value:
            if value[0] in ("-", "+"):
                value_str = value[0] + currency.symbol + value[1:]
            else:
                value_str = currency.symbol + value
        else:
            value_str = value + NBSP + currency.symbol
        return value_str

    class CannotExtractValue(Exception):
        pass

    class CurrencyNotDefined(Exception):
        pass

    class ReadingBlankText(Exception):
        pass

    class UnknownCurrencySymbol(Exception):
        pass


class Text_Attribute(Attribute):

    def _is_type_valid(self, value: Any) -> bool:
        return isinstance(value, str)

    def _is_value_valid(self, value: Any) -> bool:
        return True

    def print(self, *options) -> str:
        return str(self._value)

    @staticmethod
    def value_from_text(text: str) -> str:
        return text


class Name_Attribute(Attribute):

    def _is_type_valid(self, value: Any) -> bool:
        return isinstance(value, str)

    def _is_value_valid(self, value: Any) -> bool:
        return re.fullmatch("[^\s!\"#$%&'()*+,./:;<=>?@\^_`{|}~-].*", value) is not None

    def print(self, *options) -> str:
        return str(self._value)

    @staticmethod
    def value_from_text(text: str) -> str:
        return text


import datetime
import re


class Date_Attribute(Attribute):
    default_value = datetime.date.today()
    minimum_value = datetime.date(datetime.MINYEAR, 1, 1)
    # all locale codes must be entered in lower case
    __date_formats: Dict[str, str] = {"cs_cz": "%d.%m.%Y", "en_us": "%Y-%m-%d"}

    DEFAULT_SEPARATOR = "-"
    SEPARATOR = "[\.\,\-_]"
    YEARPATT = "(?P<year>[0-9]{3,4})"
    MONTHPATT = "(?P<month>0?[1-9]|1[0-2])"
    DAYPATT = "(?P<day>0?[1-9]|[12][0-9]|3[01])"

    YMD_PATT = YEARPATT + SEPARATOR + MONTHPATT + SEPARATOR + DAYPATT
    DMY_PATT = DAYPATT + SEPARATOR + MONTHPATT + SEPARATOR + YEARPATT

    def _is_type_valid(self, value: Any) -> bool:
        return isinstance(value, datetime.date)

    def _is_value_valid(self, value: Any) -> bool:
        return True

    def print(self, *options) -> str:
        date_format = self.__date_formats[self.factory.locale_code]
        return datetime.date.strftime(self._value, date_format)

    @staticmethod
    def __extract_date_from_string(text: str) -> None | Dict:
        text = Date_Attribute.__remove_spaces(text)
        date_match = re.fullmatch(Date_Attribute.YMD_PATT, text)
        if date_match is None:
            date_match = re.fullmatch(Date_Attribute.DMY_PATT, text)
        if date_match is None:
            return None
        return date_match.groupdict()

    def value_from_text(text: str) -> datetime.date:
        date = Date_Attribute.__extract_date_from_string(text)
        if date is None:
            raise Date_Attribute.CannotExtractDate(text)
        else:
            year, month, day = map(int, (date["year"], date["month"], date["day"]))
            return datetime.date(year, month, day)

    @staticmethod
    def __remove_spaces(text: str) -> str:
        for sp in (" ", NBSP, "\t"):
            text = text.replace(sp, "")
        return text

    class CannotExtractDate(Exception):
        pass


from te_tree.utils.naming import strip_and_join_spaces


class Choice_Attribute(Attribute):
    default_value = ""

    def __init__(
        self,
        factory: Attribute_Factory,
        atype: AttributeType,
        name: str = "",
        custom_condition: Callable[[Any], bool] = lambda x: True,
        init_value: Any = None,
        options: List[Any] | None = None,
    ) -> None:

        if options is None:
            options = []
        super().__init__(factory, atype="choice", name=name, custom_condition=custom_condition)
        self.__options: Dict[str, Any] = dict()
        if options:
            self.add_options(*options)
            if init_value is None:
                self._value = options[0]
            elif init_value in options:
                self._value = init_value
            else:
                raise Choice_Attribute.UndefinedOption(init_value)
        if not options and init_value is not None:
            raise Choice_Attribute.UndefinedOption(init_value)

    @property
    def options(self) -> List[str]:
        return list(self.__options.keys())

    @property
    def value(self) -> Any:
        if self.options:
            return self._value
        else:
            raise Choice_Attribute.NoOptionsAvailable

    def add_options(self, *options: Any) -> None:
        for op in options:
            str_op = strip_and_join_spaces(str(op))
            if str_op not in self.__options:  # prevent duplicities
                self.__options[str_op] = op
                if self._value == "":
                    self._value = options[0]
            else:
                raise Choice_Attribute.DuplicateOption(str_op)

    def clear_options(self) -> None:
        self.__options.clear()

    def copy(self) -> Choice_Attribute:
        return self.factory.new_from_dict(
            **self.factory.data_constructor.choice(self.__options.values(), self.value)
        )

    def _is_type_valid(self, value: Any) -> bool:
        return True

    def _is_value_valid(self, value: str) -> bool:
        if value not in self.__options:
            raise Choice_Attribute.UndefinedOption(
                f"Unknown option: '{value}'; available options are: {self.options}"
            )
        return True

    def is_option(self, value: Any) -> bool:
        return value in self.options

    def print(self, lower_case: bool = False, *options) -> str:

        return self._str_value(self._value, lower_case)

    def print_options(self, lower_case: bool = False) -> Tuple[str, ...]:
        result = tuple([self._str_value(op, lower_case) for op in self.options])
        return result

    def read(self, text: str, overwrite_dependent: bool = False) -> None:
        text = text.strip()
        for op in self.__options:
            if op == text:
                self.set(op, overwrite_dependent)
                return
        raise Choice_Attribute.UndefinedOption(
            f"Unknown option: '{text}'; available options are: {self.options}"
        )

    @staticmethod
    def value_from_text(text: str) -> Any:
        return text.strip()

    def remove_options(self, *options: Any) -> None:
        if self._value in options:
            raise Choice_Attribute.CannotRemoveChosenOption(self._value)
        for op in options:
            if op in self.__options:
                self.__options.pop(op)
            else:
                raise Choice_Attribute.UndefinedOption(
                    f"Unknown option: {op}; available options are: {self.options}"
                )

    def set(self, option: str, overwrite_dependent: bool = False) -> None:
        if not overwrite_dependent and self._dependency is not DependencyImpl.NULL:
            return
        if not self.__options:
            raise Choice_Attribute.NoOptionsAvailable
        if self.is_valid(option):
            option_value = self.__options[option]
            self._run_set_command(option_value)

    @classmethod
    def _str_value(cls, value, lower_case: bool = False) -> str:
        return str(value).lower() if lower_case else str(value)

    class CannotRemoveChosenOption(Exception):
        pass

    class DuplicateOption(Exception):
        pass

    class NoOptionsAvailable(Exception):
        pass

    class UndefinedOption(Exception):
        pass


class Bool_Attribute(Attribute):
    default_value = False
    minimum_value = False

    def _is_type_valid(self, value: Any) -> bool:
        return bool(value) == value

    def _is_value_valid(self, value: Any) -> bool:
        return True

    def print(self, *options) -> str:
        return str(bool(self._value))

    @staticmethod
    def value_from_text(text: str) -> bool:
        if text.strip() in ("true", "True"):
            return True
        elif text.strip() in ("false", "False"):
            return False
        else:
            raise Bool_Attribute.CannotReadBooleanFromText(text)

    class CannotReadBooleanFromText(Exception):
        pass


@dataclasses.dataclass
class Unit:
    symbol: str
    exponents: Dict[str, int]
    from_basic: Callable[[float | Decimal], Decimal | float]
    to_basic: Callable[[float | Decimal], Decimal]
    space: bool = True
    default_prefix: str = ""

    def __post_init__(self) -> None:
        self.exponents[""] = 0


from typing import Optional


class Quantity(Real_Attribute):

    __default_exponents = {"n": -9, "μ": -6, "m": -3, "k": 3, "M": 6, "G": 9}
    EXPONENT_SYMBOLS = "⁺⁻¹²³⁴⁵⁶⁷⁸⁹"
    UNIT_PATTERN = f"([a-zA-Zα-ωΑ-Ω°%‰‱]+[{EXPONENT_SYMBOLS}]*)+"
    PREFIX_PATTERN = "([TGMkhdcmμnp]?|da)"
    COMPLETE_UNIT_PATTERN = PREFIX_PATTERN + UNIT_PATTERN

    def __init__(
        self,
        factory: Attribute_Factory,
        atype: AttributeType,
        init_value: Optional[float | Decimal | int] = None,
        name: str = "",
        unit: str = "",
        exponents: Optional[Dict[str, int]] = None,
        space_after_value: bool = True,
        custom_condition: Callable[[Decimal | float | int], bool] = lambda x: True,
    ) -> None:

        super().__init__(
            factory,
            atype="quantity",
            init_value=init_value,
            name=name,
            custom_condition=custom_condition,
        )
        self.__prefix = ""
        self.__units: Dict[str, Unit] = dict()
        self.__scaled_units: List[Tuple[str, str]] = list()
        default_prefix, base_unit = self._separate_prefix_from_unit(unit)
        assert base_unit.strip() != ""

        self.add_unit(base_unit, exponents=exponents, space_after_value=space_after_value)
        self.__space_after_value = space_after_value
        self.__unit: Unit = self.__units[base_unit]
        self.set_prefix(default_prefix)
        self.__default_unit = self.__unit
        self.__unit.default_prefix = default_prefix

    @property
    def unit(self) -> str:
        return self.__unit.symbol

    @property
    def default_unit(self) -> Unit:
        return self.__default_unit

    @property
    def default_scaled_unit(self) -> str:
        return self.default_unit.default_prefix + self.default_unit.symbol

    @property
    def type(self) -> AttributeType:
        return "quantity"

    @property
    def prefix(self) -> str:
        return self.__prefix

    @property
    def scaled_units(self) -> List[Tuple[str, str]]:
        return self.__scaled_units

    @property
    def scaled_units_single_str(self) -> List[str]:
        return [item[0] + item[1] for item in self.__scaled_units]

    def add_prefix(self, unit: str, prefix: str, exponent: int) -> None:
        self.__check_unit_is_defined(unit)
        Quantity.__check_exponent(prefix, exponent)
        self.__unit.exponents[prefix] = exponent

    def add_unit(
        self,
        symbol: str,
        exponents: Optional[Dict[str, int]] = None,
        from_basic: Optional[Callable[[Decimal | float], Decimal]] = None,
        to_basic: Optional[Callable[[Decimal | float], Decimal]] = None,
        space_after_value: bool = True,
    ) -> None:

        if symbol in self.__units:
            raise Quantity.UnitAlreadyDefined(symbol)
        if from_basic is None:
            from_basic = lambda x: Decimal(x)
        if to_basic is None:
            to_basic = lambda x: Decimal(x)
        Quantity._check_conversion_from_and_to_basic_units(from_basic, to_basic)
        self.__units[symbol] = Quantity.__create_unit(
            symbol,
            exponents,
            space_after_value,
            from_basic=from_basic,
            to_basic=to_basic,
        )
        self.__scaled_units.extend([(prefix, symbol) for prefix in self.__units[symbol].exponents])

    def convert(self, value: Decimal | float, source_unit: str, target_unit: str) -> Decimal:
        new_value = Decimal(str(value))
        src_prefix, src_unit = self._separate_prefix_from_unit(source_unit)
        tgt_prefix, tgt_unit = self._separate_prefix_from_unit(target_unit)
        new_value *= Decimal(10) ** Decimal(self.__units[src_unit].exponents[src_prefix])
        if src_unit != tgt_unit:
            new_value = Decimal(self.__units[src_unit].to_basic(new_value))
            new_value = Decimal(self.__units[tgt_unit].from_basic(new_value))
        new_value *= Decimal(10) ** Decimal(-self.__units[tgt_unit].exponents[tgt_prefix])
        return Decimal(str(new_value))

    def copy(self) -> Quantity:
        fac = self.factory
        the_copy: Quantity = fac.new_from_dict(
            **fac.data_constructor.quantity(
                unit=self.default_scaled_unit,
                exponents=self.default_unit.exponents,
                init_value=self.value,
                custom_condition=self.custom_condition,
                space_after_value=self.__space_after_value,
            )
        )
        for label in self.__units:
            if self.__units[label] is not self.__default_unit:
                the_copy.add_unit(
                    symbol=self.__units[label].symbol,
                    from_basic=self.__units[label].from_basic,
                    to_basic=self.__units[label].to_basic,
                    space_after_value=self.__space_after_value,
                )
        return the_copy

    def pick_scaled_unit(self, id: int) -> None:
        picked = self.__scaled_units[id]
        self.set_unit(picked[1])
        self.set_prefix(picked[0])

    def print(
        self,
        use_thousands_separator: bool = False,
        precision: int = 28,
        trailing_zeros: bool = False,
        adjust: Optional[Callable[[Decimal | float], Decimal | float]] = None,
        include_unit: bool = True,
        *args,
    ) -> str:

        str_val = super().print(
            use_thousands_separator=use_thousands_separator,
            precision=precision,
            trailing_zeros=trailing_zeros,
            adjust=self.__adjust_func,
        )
        if include_unit:
            sep = NBSP if self.__unit.space else ""
            return f"{str_val}{sep}{self.__prefix}{self.__unit.symbol}"
        else:
            return str_val

    def read(self, text: str, overwrite_dependent: bool = False) -> None:
        text = text.strip()
        if text == "":
            raise Quantity.BlankText(text)
        matchobj = re.fullmatch(
            f"(?P<value>[\S]+)[ \t({NBSP})]?"
            + f"(?P<possible_scaled_unit>{Quantity.COMPLETE_UNIT_PATTERN})",
            text,
        )
        if matchobj is None:
            raise Quantity.CannotExtractQuantity(text)

        read_data = matchobj.groupdict()
        possible_scaled_unit = read_data["possible_scaled_unit"]
        prefix, unit = Quantity._separate_prefix_from_unit(possible_scaled_unit)
        if unit not in self.__units:
            raise Quantity.UnknownUnitInText(text)

        read_data["value"] = read_data["value"].strip().replace(",", ".")
        read_data["value"] = self.remove_thousands_separators(read_data["value"])
        try:
            value = Decimal(read_data["value"])
            if self.is_valid(value):
                self.set_unit(unit)
                self.set_prefix(prefix)
                value *= Decimal(10) ** Decimal(self.__units[unit].exponents[prefix])
                value = self.__units[unit].to_basic(value)
                value *= Decimal(10) ** Decimal(-self.__unit.exponents[self.__unit.default_prefix])
                self.set(value, overwrite_dependent)
        except:
            raise self._reading_exception

    def read_only_value(self, text: str, overwrite_dependent: bool = False) -> None:
        super().read(text, overwrite_dependent)
        self._value = self.__readjust_func(self.__unit.to_basic(self._value))

    def set_prefix(self, prefix: str) -> None:
        if not prefix in self.__unit.exponents:
            raise Quantity.UndefinedUnitPrefix(prefix)
        self.__prefix = prefix

    def set_scaled_unit(self, scaled_unit: str) -> None:
        prefix, unit = self._separate_prefix_from_unit(scaled_unit)
        self.set_unit(unit)
        self.set_prefix(prefix)

    def set_unit(self, unit: str) -> None:
        self.__check_unit_is_defined(unit)
        self.__prefix = ""
        self.__unit = self.__units[unit]

    def __adjust_func(self, value: Decimal | float) -> Decimal:
        value = self.__unit.from_basic(value)
        decimal_shift = Decimal(
            self.__unit.exponents[self.__unit.default_prefix] - self.__unit.exponents[self.__prefix]
        )
        return Decimal(value) * Decimal("10") ** decimal_shift

    def __readjust_func(self, value: Decimal | float) -> Decimal:
        value = self.__unit.from_basic(value)
        decimal_shift = Decimal(self.__unit.exponents[self.__prefix])
        return Decimal(value) * Decimal("10") ** decimal_shift

    def __check_unit_is_defined(self, unit_symbol: str) -> None:
        if unit_symbol not in self.__units:
            raise Quantity.UndefinedUnit(unit_symbol)

    @staticmethod
    def _acceptable_unit_symbol(text: str) -> bool:
        return re.fullmatch(Quantity.UNIT_PATTERN, text) is not None

    @staticmethod
    def _acceptable_unit_prefix(text: str) -> bool:
        return re.fullmatch(Quantity.PREFIX_PATTERN, text) is not None

    @staticmethod
    def _check_conversion_from_and_to_basic_units(
        from_basic: Callable[[Decimal | float], Decimal],
        to_basic: Callable[[Decimal | float], Decimal],
        test_value: Decimal | float = Decimal("0"),
    ) -> None:

        orig = Decimal(str(test_value))
        converted_to_alt_and_back = from_basic((to_basic(orig)))
        if converted_to_alt_and_back != orig:
            raise Quantity.Conversion_To_Alternative_Units_And_Back_Does_Not_Give_The_Original_Value(
                f"{orig} != {converted_to_alt_and_back}"
            )

    @staticmethod
    def __check_exponent(prefix, exponent) -> None:
        if not Quantity._acceptable_unit_prefix(prefix):
            raise Quantity.UnacceptableUnitPrefix(prefix)
        if not int(exponent) == exponent:
            raise Quantity.NonIntegerExponent(exponent)

    @staticmethod
    def __create_unit(
        symbol: str,
        exponents: Optional[Dict[str, int]] = None,
        space: bool = True,
        from_basic: Callable[[Decimal | float], Decimal] = lambda x: Decimal(x),
        to_basic: Callable[[Decimal | float], Decimal] = lambda x: Decimal(x),
    ) -> Unit:

        symbol = symbol.strip()
        if not Quantity._acceptable_unit_symbol(symbol):
            raise Quantity.UnacceptableUnitSymbol(symbol)
        if exponents is not None:
            for prefix, exponent in exponents.items():
                Quantity.__check_exponent(prefix, exponent)
        else:
            exponents = Quantity.__default_exponents.copy()

        return Unit(symbol, exponents, from_basic, to_basic, space)

    WHOLE_UNITS = ["ppm", "mol", "Gy", "Torr", "hp", "ft", "min", "mph"]

    @staticmethod
    def _separate_prefix_from_unit(possible_scaled_unit: str) -> Tuple[str, str]:
        for whole_unit in Quantity.WHOLE_UNITS:
            for k in range(len(possible_scaled_unit), -1, -1):
                if whole_unit == possible_scaled_unit[k:]:
                    return possible_scaled_unit[:k], whole_unit

        unit_match, prefix_match = None, None
        k = 0
        n = len(possible_scaled_unit)
        prefix = ""
        unit = ""
        while (unit_match is None or prefix_match is None) and (-k) < n:
            k -= 1
            prefix, unit = possible_scaled_unit[:k], possible_scaled_unit[k:]
            prefix_match = re.fullmatch(Quantity.PREFIX_PATTERN, prefix)
            unit_match = re.fullmatch(Quantity.UNIT_PATTERN, unit)
        return prefix, unit

    class BlankText(Exception):
        pass

    class CannotExtractQuantity(Exception):
        pass

    class Conversion_To_Alternative_Units_And_Back_Does_Not_Give_The_Original_Value(Exception):
        pass

    class DuplicityInCustomPrefixes(Exception):
        pass

    class MissingUnit(Exception):
        pass

    class NonIntegerExponent(Exception):
        pass

    class UndefinedUnit(Exception):
        pass

    class UndefinedUnitPrefix(Exception):
        pass

    class UnacceptableUnitPrefix(Exception):
        pass

    class UnacceptableUnitSymbol(Exception):
        pass

    class UnitAlreadyDefined(Exception):
        pass

    class UnknownUnitInText(Exception):
        pass


AttributeType = Literal[
    "bool", "choice", "date", "integer", "money", "name", "quantity", "real", "text"
]


class Attribute_Data_Constructor:

    __types = {
        "text": Text_Attribute,
        "bool": Bool_Attribute,
        "integer": Integer_Attribute,
        "real": Real_Attribute_Dimensionless,
        "choice": Choice_Attribute,
        "date": Date_Attribute,
        "money": Monetary_Attribute,
        "name": Name_Attribute,
        "quantity": Quantity,
    }

    @staticmethod
    def get_type_from_text(text: AttributeType) -> Type[Attribute]:
        return Attribute_Data_Constructor.__types[text]

    @staticmethod
    def types() -> Dict[str, Type[Attribute]]:
        return Attribute_Data_Constructor.__types.copy()

    def _check(self, info: Dict[str, Any]) -> None:
        if "atype" not in info:
            raise Attribute_Data_Constructor.MissingAttributeType(info)
        elif info["atype"] not in self.__types:
            raise Attribute_Data_Constructor.UndefinedAttributeType(info["atype"])
        attr = self.__types[info["atype"]](Attribute_Factory(Controller()), **info)

    def boolean(self, init_value: int = False) -> Dict[str, Any]:
        return {"atype": "bool", "init_value": init_value}

    def date(
        self,
        init_value: datetime.date = datetime.date.today(),
        custom_condition: Callable[[datetime.date], Any] = lambda x: True,
    ) -> Dict[str, Any]:

        return {
            "atype": "date",
            "init_value": init_value,
            "custom_condition": custom_condition,
        }

    def choice(
        self,
        options: Optional[List[Any]] = None,
        init_option: Any = None,
    ) -> Dict[str, Any]:

        if options is None:
            options = []
        return {"atype": "choice", "init_value": init_option, "options": options}

    def integer(
        self,
        init_value: int = 0,
        custom_condition: Callable[[int], Any] = lambda x: True,
    ) -> Dict[str, Any]:
        return {
            "atype": "integer",
            "init_value": init_value,
            "custom_condition": custom_condition,
        }

    def money(
        self,
        init_value: Decimal | float | int = 0.0,
        enforce_sign: bool = False,
        custom_condition: Callable[[Any], bool] = lambda x: True,
    ) -> Dict[str, Any]:

        return {
            "atype": "money",
            "init_value": init_value,
            "enforce_sign": enforce_sign,
            "custom_condition": custom_condition,
        }

    def name(self, init_value: str = "name") -> Dict[str, Any]:
        return {"atype": "name", "init_value": init_value}

    def quantity(
        self,
        unit: str,
        exponents: Optional[Dict[str, int]] = None,
        init_value: Decimal | float | int = 0.0,
        space_after_value: bool = True,
        custom_condition: Callable[[int], Any] = lambda x: True,
    ) -> Dict[str, Any]:

        return {
            "atype": "quantity",
            "init_value": init_value,
            "unit": unit,
            "exponents": exponents,
            "space_after_value": space_after_value,
            "custom_condition": custom_condition,
        }

    def real(
        self,
        init_value: Decimal | float | int = 0.0,
        custom_condition: Callable[[float | Decimal], Any] = lambda x: True,
    ) -> Dict[str, Any]:

        return {
            "atype": "real",
            "init_value": init_value,
            "custom_condition": custom_condition,
        }

    def text(
        self,
        init_value: str = "",
        custom_condition: Callable[[str], Any] = lambda x: True,
    ) -> Dict[str, Any]:
        return {
            "atype": "text",
            "init_value": init_value,
            "custom_condition": custom_condition,
        }

    class MissingAttributeType(Exception):
        pass

    class UndefinedAttributeType(Exception):
        pass


from typing import Type


@dataclasses.dataclass
class Attribute_Factory:
    controller: Controller
    locale_code: Locale_Code = "en_us"
    currency_code: Currency_Code = "USD"
    data_constructor: Attribute_Data_Constructor = Attribute_Data_Constructor()

    def __post_init__(self) -> None:
        if not self.currency_code in Monetary_Attribute.Currencies:
            raise Monetary_Attribute.CurrencyNotDefined(self.currency_code)
        self.__verify_and_format_locale_code()

    @property
    def types(self) -> Dict:
        return Attribute_Data_Constructor.types()

    def newlist(
        self,
        atype: AttributeType = "text",
        init_items: List[Any] | None = None,
        name: str = "",
    ) -> Attribute_List:
        if atype not in self.types:
            raise Attribute.InvalidAttributeType(atype)
        return Attribute_List(self, atype, init_attributes=init_items, name=name)

    def newqu(
        self,
        init_value: Optional[float | Decimal | int] = None,
        name: str = "",
        unit: str = "",
        exponents: Optional[Dict[str, int]] = None,
        space_after_value: bool = True,
        custom_condition: Callable[[Decimal | float | int], bool] = lambda x: True,
    ) -> Quantity:

        return Quantity(
            self,
            atype="quantity",
            init_value=init_value,
            name=name,
            unit=unit,
            exponents=exponents,
            space_after_value=space_after_value,
            custom_condition=custom_condition,
        )

    def new(
        self,
        atype: AttributeType = "text",
        init_value: Any = None,
        name: str = "",
        custom_condition: Callable[[Any], bool] = lambda x: True,
        **kwargs,
    ) -> Attribute:

        if atype not in self.types:
            raise Attribute.InvalidAttributeType(atype)
        else:
            return self.types[atype](
                factory=self,
                atype=atype,
                init_value=init_value,
                name=name,
                custom_condition=custom_condition,
                **kwargs,
            )

    def new_from_dict(self, **dict) -> Attribute:
        if dict["atype"] not in self.types:
            raise Attribute.InvalidAttributeType(dict["atype"])
        else:
            return self.types[dict["atype"]](self, **dict)

    def choice(self, name: str = "") -> Choice_Attribute:
        return Choice_Attribute(self, atype="choice", name=name)

    def redo(self) -> None:
        self.controller.redo()

    def run(self, *cmds: Command) -> None:
        self.controller.run(*cmds)

    def undo(self) -> None:
        self.controller.undo()

    def undo_and_forget(self) -> None:
        self.controller.undo_and_forget()

    class UnknownLocaleCode(Exception):
        pass

    def __verify_and_format_locale_code(self) -> None:
        if not self.locale_code in get_args(Locale_Code):
            raise Attribute_Factory.UnknownLocaleCode(self.locale_code)


def attribute_factory(
    controller: Controller,
    locale_code: Locale_Code = "en_us",
    currency_code: Currency_Code = "USD",
) -> Attribute_Factory:

    return Attribute_Factory(controller, locale_code, currency_code)
