import enum
import typing as t

from dataclasses import dataclass


INDENTATION = " " * 4


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

    def to_code(self, indentation_level: int = 0) -> str:
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


@dataclass
class DynValue:
    type: Type


@dataclass
class VectorType(Type):
    subtype: Type

    def to_code(self, indentation_level: int = 0) -> str:
        return f"[{self.subtype.to_code()}]"


@dataclass
class DictType(Type):
    key_type: Type
    value_type: Type

    def to_code(self, indentation_level: int = 0) -> str:
        return f"[{self.key_type.to_code()}: {self.value_type.to_code()}]"


@dataclass
class OptionalType(Type):
    inner_type: Type

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.inner_type.to_code()}?"


@dataclass
class TemplateType(Type):
    id: int

    def to_code(self, indentation_level: int = 0) -> str:
        return f"T<{self.id}>"


@dataclass
class Field(Expression):
    line: int
    base: Expression
    field: str

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.base.to_code()}.{self.field}"


@dataclass
class OptionalSomeValue(Expression):
    value: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.value.to_code()}!"


@dataclass
class OptionalSomeCall(Expression):
    value: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        return f"Optional.Some({self.value.to_code()})"


class OptionalTypeConstructor(Expression, enum.Enum):
    none = "None"
    some = "Some"

    def to_code(self, indentation_level: int = 0) -> str:
        return f"Optional.{self.value}"


class BuiltinType(Type, enum.Enum):
    i8 = "I8"
    i16 = "I16"
    i32 = "I32"
    i64 = "I64"

    u8 = "U8"
    u16 = "U16"
    u32 = "U32"
    u64 = "U64"

    f32 = "F32"
    f64 = "F64"

    string = "String"
    char = "Char"
    bool = "Bool"
    void = "Void"

    convertible_to_string = "ConvertibleToString"

    # These types are mentioned only in expressions.
    optional = "Optional"

    @classmethod
    def finite_signed_int_types(cls) -> t.List[str]:
        return [type_.value for type_ in (BuiltinType.i8, BuiltinType.i16, BuiltinType.i32, BuiltinType.i64)]

    @classmethod
    def finite_unsigned_int_types(cls) -> t.List[str]:
        return [type_.value for type_ in (BuiltinType.u8, BuiltinType.u16, BuiltinType.u32, BuiltinType.u64)]

    @classmethod
    def finite_int_types(cls) -> t.List[str]:
        return BuiltinType.finite_signed_int_types() + BuiltinType.finite_unsigned_int_types()

    @classmethod
    def finite_float_types(cls) -> t.List[str]:
        return [BuiltinType.f32.value, BuiltinType.f64.value]

    @property
    def is_finite_int_type(self):
        return self.value in self.finite_int_types()

    @property
    def is_finite_float_type(self):
        return self.value in self.finite_float_types()

    @property
    def is_finite(self):
        return self.is_finite_int_type or self.is_finite_float_type

    def get_range(self) -> str:
        assert self.is_finite
        return {
            BuiltinType.i8.value: "[-128; 127]",
            BuiltinType.i16.value: "[-32768; 32767]",
            BuiltinType.i32.value: "[-2147483648; 2147483647]",
            BuiltinType.i64.value: "[-9223372036854775808; 9223372036854775807]",

            BuiltinType.u8.value: "[0; 255]",
            BuiltinType.u16.value: "[0; 65535]",
            BuiltinType.u32.value: "[0; 4294967295]",
            BuiltinType.u64.value: "[0; 18446744073709551615]",

            BuiltinType.f32.value: (
                "[-3.402823700000000000000000000E+38; -1.17549400000000000000000000E-38] U "
                "{0} U [1.17549400000000000000000000E-38; 3.402823700000000000000000000E+38]"
            ),
            BuiltinType.f64.value: (
                "[-1.79769313486231570000000000E+308; -2.22507385850720140000000000E-308] U "
                "{0} U [2.22507385850720140000000000E-308; 1.79769313486231570000000000E+308]"
            ),
        }[self.value]

    def get_builtin_supertypes(self) -> t.List[str]:
        return {
            BuiltinType.i8.value: [
                BuiltinType.i8.value, BuiltinType.i16.value, BuiltinType.i32.value, BuiltinType.i64.value,
                BuiltinType.convertible_to_string.value
            ],
            BuiltinType.i16.value: [
                BuiltinType.i16.value, BuiltinType.i32.value, BuiltinType.i64.value,
                BuiltinType.convertible_to_string.value
            ],
            BuiltinType.i32.value: [
                BuiltinType.i32.value, BuiltinType.i64.value, BuiltinType.convertible_to_string.value
            ],
            BuiltinType.i64.value: [BuiltinType.i64.value, BuiltinType.convertible_to_string.value],

            BuiltinType.u8.value: [
                BuiltinType.u8.value, BuiltinType.u16.value, BuiltinType.u32.value, BuiltinType.u64.value,
                BuiltinType.convertible_to_string.value
            ],
            BuiltinType.u16.value: [
                BuiltinType.u16.value, BuiltinType.u32.value, BuiltinType.u64.value,
                BuiltinType.convertible_to_string.value
            ],
            BuiltinType.u32.value: [
                BuiltinType.u32.value, BuiltinType.u64.value, BuiltinType.convertible_to_string.value
            ],
            BuiltinType.u64.value: [BuiltinType.u64.value, BuiltinType.convertible_to_string.value],

            BuiltinType.f32.value: [
                BuiltinType.f32.value, BuiltinType.f64.value, BuiltinType.convertible_to_string.value,
            ],
            BuiltinType.f64.value: [
                BuiltinType.f64.value, BuiltinType.convertible_to_string.value,
            ],

            BuiltinType.string.value: [BuiltinType.string.value, BuiltinType.convertible_to_string.value],
            BuiltinType.bool.value: [BuiltinType.bool.value, BuiltinType.convertible_to_string.value],
            BuiltinType.char.value: [BuiltinType.char.value, BuiltinType.convertible_to_string.value],
            BuiltinType.void.value: [BuiltinType.void.value],
        }[self.value]

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


class BuiltinFunc(Expression, enum.Enum):
    print = "print"
    read = "read"

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


class Operator(enum.Enum):
    not_ = "not"
    and_ = "and"
    or_ = "or"

    lt_eq = "<="
    gt_eq = ">="
    eq_eq = "=="
    neq = "!="

    lt = "<"
    gt = ">"

    eq = "="
    add_eq = "+="
    sub_eq = "-="
    mul_eq = "*="
    div_eq = "/="

    add = "+"
    sub = "-"
    mul = "*"
    div = "/"

    @classmethod
    def comparison_operators(cls):
        return [Operator.lt_eq, Operator.gt_eq, Operator.eq_eq, Operator.neq, Operator.lt, Operator.gt]

    @classmethod
    def assignment_operators(cls):
        return [Operator.add_eq, Operator.sub_eq, Operator.mul_eq, Operator.div_eq, Operator.eq]

    def to_arithmetic_operator(self):
        return Operator(self.value[0])


class SpecialMethods(enum.Enum):
    eq = "__eq__"
    lt = "__lt__"
    gt = "__gt__"

    add = "__add__"
    sub = "__sub__"
    mul = "__mul__"
    div = "__div__"


@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: Operator
    right: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.left.to_code()} {self.operator.value} {self.right.to_code()}"


@dataclass
class UnaryExpression(Expression):
    operator: Operator
    value: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.operator.value} {self.value.to_code()}"


@dataclass
class Name(Type):
    member: str
    module: t.Optional[str] = None

    def to_code(self, indentation_level: int = 0) -> str:
        if self.module:
            return f"{self.module}#{self.member}"
        return self.member


@dataclass
class Cast(Expression):
    value: Expression
    to_type: Type

    def to_code(self, indentation_level: int = 0) -> str:
        return f"({self.to_type.to_code()})({self.value.to_code()})"


@dataclass
class BoolLiteral(Expression, enum.Enum):
    true = "true"
    false = "false"

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


@dataclass
class IntegerLiteral(Type):
    value: str

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


@dataclass
class DecimalLiteral(Expression):
    value: str

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


@dataclass
class StringLiteral(Expression):
    value: str

    def to_code(self, indentation_level: int = 0) -> str:
        return '"' + self.value + '"'


@dataclass
class CharLiteral(Expression):
    value: str

    def to_code(self, indentation_level: int = 0) -> str:
        return "'" + self.value + "'"


@dataclass
class VectorLiteral(Expression):
    elements: t.List[Expression]

    def to_code(self, indentation_level: int = 0) -> str:
        return "[" + ', '.join(element.to_code() for element in self.elements) + "]"


@dataclass
class DictLiteral(Expression):
    keys: t.List[Expression]
    values: t.List[Expression]
    annotation: t.Optional[Type] = None

    def to_code(self, indentation_level: int = 0) -> str:
        inner = []
        for key, value in zip(self.keys, self.values):
            inner.append(f"{key.to_code()}: {value.to_code()}")
        return "[" + ', '.join(element for element in inner) + "]"


@dataclass
class FunctionCall(Node):
    function_path: Expression
    args: t.List[Expression]

    def to_code(self, indentation_level: int = 0) -> str:
        code = f"{self.function_path.to_code()}({', '.join(arg.to_code() for arg in self.args)})"
        return INDENTATION * indentation_level + code


@dataclass
class Assignment(Node):
    left: Expression
    operator: Operator
    right: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        code = f"{self.left.to_code()} {self.operator.value} {self.right.to_code()}"
        return INDENTATION * indentation_level + code


@dataclass
class ConstantDeclaration(Node):
    name: Name
    type: t.Optional[Type]
    value: t.Optional[Expression]

    def __post_init__(self):
        assert self.type is not None or self.value is not None

    def to_code(self, indentation_level: int = 0) -> str:
        if self.type is not None and self.value is not None:
            code = f"let {self.name.to_code()}: {self.type.to_code()} = {self.value.to_code()}"
            return INDENTATION * indentation_level + code
        if self.value is not None:
            code = f"let {self.name.to_code()} = {self.value.to_code()}"
            return INDENTATION * indentation_level + code
        assert self.type is not None
        code = f"let {self.name.to_code()}: {self.type.to_code()}"
        return INDENTATION * indentation_level + code


@dataclass
class VariableDeclaration(Node):
    name: Name
    type: t.Optional[Type]
    value: t.Optional[Expression]

    def __post_init__(self):
        assert self.type is not None or self.value is not None

    def to_code(self, indentation_level: int = 0) -> str:
        if self.type is not None and self.value is not None:
            code = f"var {self.name.to_code()}: {self.type.to_code()} = {self.value.to_code()}"
            return INDENTATION * indentation_level + code
        if self.value is not None:
            code = f"var {self.name.to_code()} = {self.value.to_code()}"
            return INDENTATION * indentation_level + code
        assert self.type is not None
        code = f"var {self.name.to_code()}: {self.type.to_code()}"
        return INDENTATION * indentation_level + code


@dataclass
class Break(Node):
    def to_code(self, indentation_level: int = 0) -> str:
        return INDENTATION * indentation_level + "break"


@dataclass
class While(Node):
    condition: Expression
    body: AST

    def to_code(self, indentation_level: int = 0) -> str:
        body = '\n'.join(node.to_code(indentation_level + 1) for node in self.body)
        code = f"while {self.condition.to_code()}:\n{body}"
        return INDENTATION * indentation_level + code


@dataclass
class If(Node):
    condition: t.Union[ConstantDeclaration, Expression]
    body: AST
    elifs: t.List[t.Tuple[Expression, AST]]
    else_: AST

    def to_code(self, indentation_level: int = 0) -> str:
        body = '\n'.join(node.to_code(indentation_level + 1) for node in self.body)
        if self.elifs:
            elifs_ = []
            for elif_condition, elif_body in self.elifs:
                elif_body_code = '\n'.join(node.to_code(indentation_level + 1) for node in elif_body)
                elif_code = f"elif {elif_condition.to_code()}:\n{elif_body_code}"
                elifs_.append(INDENTATION * indentation_level + elif_code)
            elifs = "\n".join(elifs_)
        else:
            elifs = ""
        if self.else_:
            else_body = '\n'.join(node.to_code(indentation_level + 1) for node in self.else_)
            else_ = INDENTATION * indentation_level + f"else:\n{else_body}"
        else:
            else_ = ""
        code = f"if {self.condition.to_code()}:\n{body}{elifs}{else_}"
        return INDENTATION * indentation_level + code


@dataclass
class Return(Node):
    value: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        return f"return {self.value.to_code()}"


@dataclass
class Argument:
    name: Name
    type: Type

    def to_code(self) -> str:
        return f"{self.name.to_code()}: {self.type.to_code()}"


@dataclass
class FunctionDeclaration(Node):
    name: Name
    args: t.List[Argument]
    return_type: Type
    body: AST

    def to_code(self, indentation_level: int = 0) -> str:
        body = '\n'.join(node.to_code(indentation_level + 1) for node in self.body)
        args = ', '.join(arg.to_code() for arg in self.args)
        code = f"fun {self.name.to_code()}({args}) -> {self.return_type.to_code()}:\n{body}"
        return INDENTATION * indentation_level + code


@dataclass
class FieldDeclaration(Node):
    name: Name
    type: Type

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.name.to_code()}: {self.type.to_code()}"


@dataclass
class StructDeclaration(Node):
    name: Name
    body: AST

    def to_code(self, indentation_level: int = 0) -> str:
        body = '\n'.join(node.to_code(indentation_level + 1) for node in self.body)
        code = f"struct {self.name.to_code()}:\n{body}"
        return INDENTATION * indentation_level + code
