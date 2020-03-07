import enum
import typing as t

from dataclasses import dataclass


@dataclass
class Position:
    column: int = 1
    line: int = 1

    def next_line(self):
        self.line += 1
        self.column = 1

    def next_column(self):
        self.column += 1

    def __str__(self):
        return f"(line: {self.line}, column: {self.column})"

    __repr__ = __str__


class Node:
    """Base class for all AST nodes."""


class Expression(Node):
    """Base class for expressions.

    Every expression is a statement.
    """


class Type(Expression):
    """Base class for types.

    Every type is an expression.
    """


AST = t.List[Node]


class BuiltinType(Type, enum.Enum):
    i8 = "I8"
    i16 = "I16"
    i32 = "I32"
    i64 = "I64"

    @classmethod
    def finite_int_types(cls) -> t.List[str]:
        return [type_.value for type_ in [BuiltinType.i8, BuiltinType.i16, BuiltinType.i32, BuiltinType.i64]]


class BuiltinFunc(Expression, enum.Enum):
    print = "print"


@dataclass
class Name(Type):
    member: str
    module: t.Optional[str] = None


@dataclass
class IntegerLiteral(Type):
    value: str


@dataclass
class StringLiteral(Expression):
    value: str


@dataclass
class FunctionCall(Expression):
    function_path: Expression
    args: t.List[Expression]


@dataclass
class ConstantDeclaration(Expression):
    name: Name
    type: Type
    value: Expression
