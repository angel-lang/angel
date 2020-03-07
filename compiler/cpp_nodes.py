import typing as t
import abc
import enum

from dataclasses import dataclass


class Node(abc.ABC):
    @abc.abstractmethod
    def to_code(self) -> str:
        pass


class Type(abc.ABC):
    @abc.abstractmethod
    def to_code(self) -> str:
        pass


class Expression(abc.ABC):
    @abc.abstractmethod
    def to_code(self) -> str:
        pass


AST = t.List[Node]


class StdModule(enum.Enum):
    iostream = "iostream"
    cstdint = "cstdint"


class Operator(enum.Enum):
    lshift = "<<"


class ABCEnumMeta(abc.ABCMeta, enum.EnumMeta):
    pass


class StdName(Type, Expression, enum.Enum, metaclass=ABCEnumMeta):
    int_fast8_t = "int_fast8_t"
    int_fast16_t = "int_fast16_t"
    int_fast32_t = "int_fast32_t"
    int_fast64_t = "int_fast64_t"

    cout = "cout"
    endl = "endl"

    def to_code(self) -> str:
        return "std::" + self.value


class PrimitiveTypes(Type, enum.Enum, metaclass=ABCEnumMeta):
    int = "int"
    void = "void"

    def to_code(self) -> str:
        return self.value


@dataclass
class IntegerLiteral(Expression):
    value: str

    def to_code(self) -> str:
        return self.value


@dataclass
class StringLiteral(Expression):
    value: str

    def to_code(self) -> str:
        return '"' + self.value + '"'


@dataclass
class Id(Type, Expression):
    value: str

    def to_code(self) -> str:
        return self.value


@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: Operator
    right: Expression

    def to_code(self) -> str:
        return f"{self.left.to_code()}{self.operator.value}{self.right.to_code()}"


@dataclass
class Semicolon(Node):
    expression: Expression

    def to_code(self) -> str:
        return self.expression.to_code() + ";"


@dataclass
class FunctionCall(Node, Expression):
    function_path: Expression
    args: t.List[Expression]

    def to_code(self) -> str:
        args = ",".join(arg.to_code() for arg in self.args)
        return f"{self.function_path.to_code()}({args})"


@dataclass
class Argument:
    type: Type
    name: str

    def to_code(self) -> str:
        return f"{self.type.to_code()} {self.name}"


@dataclass
class Include(Node):
    module: StdModule

    def to_code(self) -> str:
        return f"#include <{self.module.value}>"


@dataclass
class Declaration(Node):
    type: Type
    name: str
    value: Expression

    def to_code(self) -> str:
        return f"{self.type.to_code()} {self.name}={self.value.to_code()};"


@dataclass
class Return(Node):
    value: Expression

    def to_code(self) -> str:
        return f"return {self.value.to_code()};"


@dataclass
class FunctionDeclaration(Node):
    return_type: Type
    name: str
    args: t.List[Argument]
    body: AST

    def to_code(self) -> str:
        args = ",".join(arg.to_code() for arg in self.args)
        body = "\n".join(node.to_code() for node in self.body)
        return f"{self.return_type.to_code()} {self.name}({args}){{{body}}}"
