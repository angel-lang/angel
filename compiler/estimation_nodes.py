"""Nodes that represent evaluated expressions at compile-time."""
import enum
import typing as t
from decimal import Decimal
from dataclasses import dataclass, field

from . import nodes


class Expression:
    def to_code(self) -> str:
        return ""


@dataclass
class Void(Expression):
    def to_code(self) -> str:
        return "Void"


@dataclass
class String(Expression):
    value: str

    def to_code(self) -> str:
        return '"' + self.value + '"'


@dataclass
class Char(Expression):
    value: str

    def to_code(self) -> str:
        return "'" + self.value + "'"


@dataclass
class Int(Expression):
    value: int
    type: nodes.BuiltinType

    def to_code(self) -> str:
        return str(self.value)


@dataclass
class Float(Expression):
    value: Decimal
    type: nodes.BuiltinType

    def to_code(self) -> str:
        return str(self.value)


@dataclass
class Vector(Expression):
    elements: t.List[Expression]
    element_type: nodes.Type

    def to_code(self) -> str:
        return f"[{', '.join(element.to_code() for element in self.elements)}]"


@dataclass
class Dict(Expression):
    keys: t.List[Expression]
    values: t.List[Expression]
    key_type: nodes.Type
    value_type: nodes.Type

    def to_code(self) -> str:
        keys = (key.to_code() for key in self.keys)
        values = (value.to_code() for value in self.values)
        result = []
        for key, value in zip(keys, values):
            result.append(f"{key}: {value}")
        return f"[{', '.join(result)}]"


@dataclass
class Bool(Expression):
    value: bool

    def to_code(self) -> str:
        return str(self.value)


class OptionalConstructor(Expression, enum.Enum):
    some = "Some"
    none = "None"

    def to_code(self) -> str:
        return f"Optional.{self.value}"


@dataclass
class OptionalSomeCall(Expression):
    inner_value: Expression

    def to_code(self) -> str:
        return f"Optional.Some({self.inner_value.to_code()})"


@dataclass
class DynamicValue(Expression):
    type: nodes.Type

    def to_code(self) -> str:
        return f"DynamicValue({self.type.to_code()})"


@dataclass
class Function(Expression):
    args: nodes.Arguments
    return_type: nodes.Type
    specification: t.Union[t.Callable[..., Expression], nodes.AST]

    def to_code(self) -> str:
        return f"Function(({', '.join(arg.to_code() for arg in self.args)}) -> {self.return_type.to_code()})"


@dataclass
class Struct(Expression):
    name: nodes.Name

    def to_code(self) -> str:
        return f"Struct({self.name.to_code()})"


@dataclass
class Instance(Expression):
    type: nodes.Name
    fields: t.Dict[str, Expression] = field(default_factory=dict)

    def to_code(self) -> str:
        return f"{self.type.to_code()}({','.join(f'{name}: {value.to_code()}' for name, value in self.fields.items())})"


@dataclass
class Break(Expression):

    def to_code(self) -> str:
        return "Break"
