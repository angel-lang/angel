import typing as t
import abc
import enum

from dataclasses import dataclass, field


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
    functional = "functional"
    variant = "variant"


class Operator(enum.Enum):
    and_ = "&&"
    or_ = "||"

    increment = "++"
    decrement = "--"

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
    variant = "variant"

    get = "get"
    to_string = "to_string"

    ostream = "ostream"
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
class MemberName(Type):
    namespace: Type
    member: str

    def to_code(self) -> str:
        return f"{self.namespace.to_code()}::{self.member}"


@dataclass
class VoidPtr(Type):
    def to_code(self) -> str:
        return "void*"


@dataclass
class Subscript(Expression):
    base: Expression
    index: Expression

    def to_code(self) -> str:
        base = self.base.to_code()
        if isinstance(self.base, Deref):
            base = f"({base})"
        return f"{base}[{self.index.to_code()}]"


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
class NamedArgument(Expression):
    name: Id
    value: Expression

    def to_code(self) -> str:
        return f'{self.name.to_code()}={self.value.to_code()}'


@dataclass
class Parentheses(Expression):
    value: Expression

    def to_code(self) -> str:
        return '(' + self.value.to_code() + ')'


@dataclass
class GenericType(Type):
    parent: Type
    parameters: t.List[Type]

    def to_code(self) -> str:
        parameters = ','.join(param.to_code() for param in self.parameters)
        return f"{self.parent.to_code()}<{parameters}>"


@dataclass
class FunctionType(Type):
    result_type: Type
    arguments: t.List[Type]

    def to_code(self) -> str:
        return f"std::function<{self.result_type.to_code()}({','.join(arg.to_code() for arg in self.arguments)})>"


@dataclass
class Auto(Type):
    def to_code(self) -> str:
        return "auto"


@dataclass
class Addr(Type):
    value: Type

    def to_code(self) -> str:
        return f"{self.value.to_code()}&"


@dataclass
class AddrExpression(Expression):
    value: Expression

    def to_code(self) -> str:
        return f"&{self.value.to_code()}"


@dataclass
class Pointer(Type):
    value: Type

    def to_code(self) -> str:
        return f"{self.value.to_code()}*"


@dataclass
class Deref(Expression):
    value: Expression

    def to_code(self) -> str:
        return f"*{self.value.to_code()}"


@dataclass
class UnaryExpression(Expression):
    operator: Operator
    subexpression: Expression

    def to_code(self) -> str:
        return f"{self.operator.value}{self.subexpression.to_code()}"


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
    arguments: t.List[Expression]
    parameters: t.List[Type] = field(default_factory=list)

    def to_code(self) -> str:
        arguments = ",".join(arg.to_code() for arg in self.arguments)
        if self.parameters:
            parameters = ",".join(param.to_code() for param in self.parameters)
            return f"{self.function_path.to_code()}<{parameters}>({arguments})"
        return f"{self.function_path.to_code()}({arguments})"


@dataclass
class MethodCall(Node, Expression):
    base: Expression
    method: str
    arguments: t.List[Expression]

    def to_code(self) -> str:
        base = self.base.to_code()
        if isinstance(self.base, Cast):
            base = f'({base})'
        arguments = ','.join(arg.to_code() for arg in self.arguments)
        return f"{base}.{self.method}({arguments})"


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
    arguments: Arguments
    body: AST

    def to_code(self) -> str:
        arguments = ",".join(arg.to_code() for arg in self.arguments)
        body = "\n".join(node.to_code() for node in self.body)
        return f"{self.return_type.to_code()} {self.name}({arguments}){{{body}}}"


@dataclass
class Break(Node):

    def to_code(self) -> str:
        return "break;"


@dataclass
class For(Node):
    start_condition: SubDeclaration
    continue_condition: Expression
    end_condition: Expression
    body: AST

    def to_code(self) -> str:
        start = self.start_condition.to_code()
        continue_ = self.continue_condition.to_code()
        end = self.end_condition.to_code()
        body = "\n".join(node.to_code() for node in self.body)
        return f"for({start};{continue_};{end}){{{body}}}"


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
    arguments: Arguments
    delegation_arguments: t.Optional[t.List[Expression]]
    body: AST

    def to_code(self) -> str:
        arguments = ','.join(arg.to_code() for arg in self.arguments)
        if self.delegation_arguments is not None:
            delegation_arguments = ','.join(arg.to_code() for arg in self.delegation_arguments)
            return f"{self.name}({arguments}):{self.name}({delegation_arguments}){{}}"
        body = ''.join(node.to_code() for node in self.body)
        return f"{self.name}({arguments}){{{body}}}"


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


@dataclass
class Template(Node):
    types: t.List[Type]
    node: Node

    def to_code(self) -> str:
        types = ','.join('typename ' + type_.to_code() for type_ in self.types)
        return f"template<{types}>{self.node.to_code()}"
