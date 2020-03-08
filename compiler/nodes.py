import enum
import typing as t

from dataclasses import dataclass


@dataclass
class Position:
    column: int = 1
    line: int = 1

    def next_line(self) -> None:
        self.line += 1
        self.column = 1

    def next_column(self) -> None:
        self.column += 1

    def __str__(self) -> str:
        return f"(line: {self.line}, column: {self.column})"

    __repr__ = __str__


class Expression:
    """Base class for expressions."""

    def to_code(self) -> str:
        return ""


@dataclass
class Node(Expression):
    """Base class for statements.

    Every statement is an expression.
    """
    line: int


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

    u8 = "U8"
    u16 = "U16"
    u32 = "U32"
    u64 = "U64"

    string = "String"

    @classmethod
    def finite_signed_int_types(cls) -> t.List[str]:
        return [type_.value for type_ in (BuiltinType.i8, BuiltinType.i16, BuiltinType.i32, BuiltinType.i64)]

    @classmethod
    def finite_unsigned_int_types(cls) -> t.List[str]:
        return [type_.value for type_ in (BuiltinType.u8, BuiltinType.u16, BuiltinType.u32, BuiltinType.u64)]

    @classmethod
    def finite_int_types(cls) -> t.List[str]:
        return BuiltinType.finite_signed_int_types() + BuiltinType.finite_unsigned_int_types()

    @property
    def is_finite_int_type(self) -> bool:
        return self.value in self.finite_int_types()

    def get_range(self) -> str:
        assert self.is_finite_int_type
        return {
            BuiltinType.i8.value: "[-128; 127]",
            BuiltinType.i16.value: "[-32768; 32767]",
            BuiltinType.i32.value: "[-2147483648; 2147483647]",
            BuiltinType.i64.value: "[-9223372036854775808; 9223372036854775807]",

            BuiltinType.u8.value: "[0; 255]",
            BuiltinType.u16.value: "[0; 65535]",
            BuiltinType.u32.value: "[0; 4294967295]",
            BuiltinType.u64.value: "[0; 18446744073709551615]",
        }[self.value]

    def to_code(self) -> str:
        return self.value


class BuiltinFunc(Expression, enum.Enum):
    print = "print"

    def to_code(self) -> str:
        return self.value


class Operator(enum.Enum):
    eq = "="


@dataclass
class Name(Type):
    member: str
    module: t.Optional[str] = None

    def to_code(self) -> str:
        if self.module:
            return f"{self.module}#{self.member}"
        return self.member


@dataclass
class IntegerLiteral(Type):
    value: str

    def to_code(self) -> str:
        return self.value


@dataclass
class StringLiteral(Expression):
    value: str

    def to_code(self) -> str:
        return '"' + self.value + '"'


@dataclass
class FunctionCall(Node):
    function_path: Expression
    args: t.List[Expression]

    def to_code(self) -> str:
        return f"{self.function_path.to_code()}({', '.join(arg.to_code() for arg in self.args)})"


@dataclass
class Assignment(Node):
    left: Expression
    operator: Operator
    right: Expression

    def to_code(self) -> str:
        return f"{self.left.to_code()} {self.operator.value} {self.right.to_code()}"


@dataclass
class ConstantDeclaration(Node):
    name: Name
    type: t.Optional[Type]
    value: t.Optional[Expression]

    def __post_init__(self):
        assert self.type is not None or self.value is not None

    def to_code(self) -> str:
        if self.type is not None and self.value is not None:
            return f"let {self.name.to_code()}: {self.type.to_code()} = {self.value.to_code()}"
        if self.value is not None:
            return f"let {self.name.to_code()} = {self.value.to_code()}"
        assert self.type is not None
        return f"let {self.name.to_code()}: {self.type.to_code()}"


@dataclass
class VariableDeclaration(Node):
    name: Name
    type: t.Optional[Type]
    value: t.Optional[Expression]

    def __post_init__(self):
        assert self.type is not None or self.value is not None

    def to_code(self) -> str:
        if self.type is not None and self.value is not None:
            return f"var {self.name.to_code()}: {self.type.to_code()} = {self.value.to_code()}"
        if self.value is not None:
            return f"var {self.name.to_code()} = {self.value.to_code()}"
        assert self.type is not None
        return f"var {self.name.to_code()}: {self.type.to_code()}"
