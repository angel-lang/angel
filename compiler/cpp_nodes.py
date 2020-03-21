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
    vector = "vector"
    map = "map"
    optional = "optional"


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
    vector = "vector"
    map = "map"
    optional = "optional"
    nullopt = "nullopt"

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
    char = "char"
    float = "float"
    double = "double"

    def to_code(self) -> str:
        assert isinstance(self.value, str)
        return self.value


class SpecialName(Expression, enum.Enum):
    this = "this"

    def to_code(self) -> str:
        return self.value


@dataclass
class VoidPtr(Type):
    def to_code(self) -> str:
        return "void*"


@dataclass
class Subscript(Expression):
    base: Expression
    index: Expression

    def to_code(self) -> str:
        return f"{self.base.to_code()}[{self.index.to_code()}]"


@dataclass
class IntegerLiteral(Expression):
    value: str

    def to_code(self) -> str:
        return self.value


@dataclass
class DecimalLiteral(Expression):
    value: str

    def to_code(self) -> str:
        return self.value


@dataclass
class StringLiteral(Expression):
    value: str

    def to_code(self) -> str:
        return '"' + self.value + '"'


@dataclass
class CharLiteral(Expression):
    value: str

    def to_code(self) -> str:
        return "'" + self.value + "'"


@dataclass
class ArrayLiteral(Expression):
    elements: t.List[Expression]

    def to_code(self) -> str:
        return "{" + ','.join(element.to_code() for element in self.elements) + "}"


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
class GenericType(Type):
    parent: Type
    parameters: t.List[Type]

    def to_code(self) -> str:
        parameters = ','.join(param.to_code() for param in self.parameters)
        return f"{self.parent.to_code()}<{parameters}>"


@dataclass
class Auto(Type):
    def to_code(self) -> str:
        return "auto"


@dataclass
class Deref(Expression):
    value: Expression

    def to_code(self) -> str:
        return f"*{self.value.to_code()}"


@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: Operator
    right: Expression

    def to_code(self) -> str:
        return f"{self.left.to_code()}{self.operator.value}{self.right.to_code()}"


@dataclass
class Cast(Expression):
    value: Expression
    to_type: Type

    def to_code(self) -> str:
        return f"({self.to_type.to_code()})({self.value.to_code()})"


@dataclass
class ArrowField(Expression):
    base: Expression
    field: str

    def to_code(self) -> str:
        return f"{self.base.to_code()}->{self.field}"


@dataclass
class DotField(Expression):
    base: Expression
    field: str

    def to_code(self) -> str:
        return f"{self.base.to_code()}.{self.field}"


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
class MethodCall(Node, Expression):
    base: Expression
    method: str
    args: t.List[Expression]

    def to_code(self) -> str:
        args = ','.join(arg.to_code() for arg in self.args)
        return f"{self.base.to_code()}.{self.method}({args})"


@dataclass
class Argument:
    type: Type
    name: str
    value: t.Optional[Expression] = None

    def to_code(self) -> str:
        if self.value:
            return f"{self.type.to_code()} {self.name}={self.value.to_code()}"
        return f"{self.type.to_code()} {self.name}"


Arguments = t.List[Argument]


@dataclass
class Include(Node):
    module: str
    standard: bool = True

    def to_code(self) -> str:
        if self.standard:
            return f"#include <{self.module}>"
        return f'#include "{self.module}"'


@dataclass
class SubDeclaration(Node):
    type: Type
    name: str
    value: Expression

    def to_code(self) -> str:
        return f"{self.type.to_code()} {self.name}={self.value.to_code()}"


@dataclass
class Declaration(Node):
    type: Type
    name: str
    value: t.Optional[Expression]

    def to_code(self) -> str:
        if self.value is None:
            return f"{self.type.to_code()} {self.name};"
        return f"{self.type.to_code()} {self.name}={self.value.to_code()};"

    def to_sub_declaration(self) -> SubDeclaration:
        assert self.value is not None
        return SubDeclaration(self.type, self.name, self.value)


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
    args: Arguments
    body: AST

    def to_code(self) -> str:
        args = ",".join(arg.to_code() for arg in self.args)
        body = "\n".join(node.to_code() for node in self.body)
        return f"{self.return_type.to_code()} {self.name}({args}){{{body}}}"


@dataclass
class Break(Node):

    def to_code(self) -> str:
        return "break;"


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


class AccessModifier(enum.Enum):
    public = "public"
    private = "private"
    protected = "protected"


@dataclass
class InitDeclaration(Node):
    name: str
    args: Arguments
    body: AST

    def to_code(self) -> str:
        args = ','.join(arg.to_code() for arg in self.args)
        body = ''.join(node.to_code() for node in self.body)
        return f"{self.name}({args}){{{body}}}"


@dataclass
class ClassDeclaration(Node):
    name: str
    base_classes: t.List[t.Tuple[AccessModifier, Type]]
    private: AST
    public: AST

    def to_code(self) -> str:
        inheritance = ""
        if self.base_classes:
            inheritance = ":" + ",".join(
                f"{modifier.value} {base_class.to_code()}" for modifier, base_class in self.base_classes
            )
        private = ""
        if self.private:
            private = "private:" + ''.join(node.to_code() for node in self.private)
        public = ""
        if self.public:
            public = "public:" + ''.join(node.to_code() for node in self.public)
        return f"class {self.name}{inheritance}{{{private}{public}}};"
