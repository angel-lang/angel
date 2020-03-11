import typing as t
import abc
import enum

from dataclasses import dataclass


class Node:
    @abc.abstractmethod
    def to_code(self) -> str:
        pass


class Type:
    @abc.abstractmethod
    def to_code(self) -> str:
        pass


class Expression:
    @abc.abstractmethod
    def to_code(self) -> str:
        pass


AST = t.List[Node]


class StdModule(enum.Enum):
    iostream = "iostream"
    cstdint = "cstdint"
    string = "string"


class Operator(enum.Enum):
    lshift = "<<"
    rshift = ">>"

    lt_eq = "<="
    gt_eq = ">="
    eq_eq = "=="
    neq = "!="

    eq = "="
    lt = "<"
    gt = ">"

    add = "+"
    sub = "-"
    mul = "*"
    div = "/"


class StdName(Type, Expression, enum.Enum):
    int_fast8_t = "int_fast8_t"
    int_fast16_t = "int_fast16_t"
    int_fast32_t = "int_fast32_t"
    int_fast64_t = "int_fast64_t"

    uint_fast8_t = "uint_fast8_t"
    uint_fast16_t = "uint_fast16_t"
    uint_fast32_t = "uint_fast32_t"
    uint_fast64_t = "uint_fast64_t"

    string = "string"

    cout = "cout"
    cin = "cin"
    endl = "endl"

    def to_code(self) -> str:
        assert isinstance(self.value, str)
        return "std::" + self.value


class PrimitiveTypes(Type, enum.Enum):
    int = "int"
    void = "void"
    bool = "bool"

    def to_code(self) -> str:
        assert isinstance(self.value, str)
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


class BoolLiteral(Expression, enum.Enum):
    true = "true"
    false = "false"

    def to_code(self) -> str:
        return self.value


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
    value: t.Optional[Expression]

    def to_code(self) -> str:
        if self.value is None:
            return f"{self.type.to_code()} {self.name};"
        return f"{self.type.to_code()} {self.name}={self.value.to_code()};"


@dataclass
class Assignment(Node):
    left: Expression
    operator: Operator
    right: Expression

    def to_code(self) -> str:
        return f"{self.left.to_code()}{self.operator.value}{self.right.to_code()};"


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


@dataclass
class While(Node):
    condition: Expression
    body: AST

    def to_code(self) -> str:
        body = "\n".join(node.to_code() for node in self.body)
        return f"while({self.condition.to_code()}){{{body}}}"


@dataclass
class If(Node):
    condition: Expression
    body: AST
    else_ifs: t.List[t.Tuple[Expression, AST]]
    else_: AST

    def to_code(self) -> str:
        body = ''.join(node.to_code() for node in self.body)
        else_ifs = []
        for else_if_condition, else_if_body in self.else_ifs:
            else_ifs.append(
                f"else if({else_if_condition.to_code()}){{{''.join(node.to_code() for node in else_if_body)}}}")
        if self.else_:
            else_ = f"else{{{''.join(node.to_code() for node in self.else_)}}}"
        else:
            else_ = ""
        return f"if({self.condition.to_code()}){{{body}}}{''.join(else_ifs)}{else_}"


@dataclass
class StructDeclaration(Node):
    name: str
    body: AST

    def to_code(self) -> str:
        body = ''.join(node.to_code() for node in self.body)
        return f"struct {self.name}{{{body}}};"
