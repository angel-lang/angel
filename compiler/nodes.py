import enum
import typing as t

from dataclasses import dataclass, field


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


class AssignmentLeft(Expression):
    """Kind of expression that can be used for assignment."""


@dataclass
class Node:
    """Base class for statements."""

    line: int

    def to_code(self, indentation_level: int = 0) -> str:
        return ""


class Type:
    """Base class for types."""

    def to_code(self, indentation_level: int = 0) -> str:
        return ""


AST = t.List[Node]


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
class RefType(Type):
    value_type: Type

    def to_code(self, indentation_level: int = 0) -> str:
        return f"ref {self.value_type.to_code()}"


@dataclass
class Name(Type, AssignmentLeft):
    member: str
    module: t.Optional[str] = None
    unmangled: str = ''

    def to_code(self, indentation_level: int = 0) -> str:
        member = self.unmangled or self.member
        if self.module:
            return f"{self.module}#{member}"
        return member


@dataclass
class Field(AssignmentLeft):
    line: int
    base: Expression
    field: Name
    base_type: t.Optional[Type] = None

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.base.to_code()}.{self.field.to_code()}"


@dataclass
class Subscript(AssignmentLeft):
    line: int
    base: Expression
    index: Expression
    base_type: t.Optional[Type] = None

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.base.to_code()}[{self.index.to_code()}]"


@dataclass
class Ref(Expression):
    value: Expression
    value_type: t.Optional[Type] = None

    def to_code(self, indentation_level: int = 0) -> str:
        return f"ref {self.value.to_code()}"


@dataclass
class Parentheses(Expression):
    value: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        return f"({self.value.to_code()})"


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
    """How to add a builtin type:
    1. Add it as a member:
        type = "Type"
    2. If it is an interface, add it to the list of interfaces (classmethod) and to builtin_interfaces mapping
        in constants
    3. If it is a "Convertible" interface, add it to as_convertible_interface mapping
    3. Add supertypes of this type to get_builtin_supertypes mapping
    """
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
    self_ = "Self"

    object_ = "Object"
    convertible_to_string = "ConvertibleToString"
    convertible_to_i8 = "ConvertibleToI8"
    convertible_to_i16 = "ConvertibleToI16"
    convertible_to_i32 = "ConvertibleToI32"
    convertible_to_i64 = "ConvertibleToI64"
    convertible_to_u8 = "ConvertibleToU8"
    convertible_to_u16 = "ConvertibleToU16"
    convertible_to_u32 = "ConvertibleToU32"
    convertible_to_u64 = "ConvertibleToU64"

    addable = "Addable"
    subtractable = "Subtractable"
    multipliable = "Multipliable"
    divisible = "Divisible"
    arithmetic_object = "ArithmeticObject"

    eq = "Eq"

    iterable = "Iterable"

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

    @classmethod
    def interfaces(cls) -> t.List[str]:
        return [
            BuiltinType.addable.value, BuiltinType.subtractable.value, BuiltinType.multipliable.value,
            BuiltinType.divisible.value, BuiltinType.arithmetic_object.value, BuiltinType.object_.value,
            BuiltinType.iterable.value, BuiltinType.eq.value,
            BuiltinType.convertible_to_string.value, BuiltinType.convertible_to_i16.value
        ]

    @property
    def is_interface(self):
        return self.value in self.interfaces()

    @property
    def is_finite_int_type(self):
        return self.value in self.finite_int_types()

    @property
    def is_finite_float_type(self):
        return self.value in self.finite_float_types()

    @property
    def is_finite(self):
        return self.is_finite_int_type or self.is_finite_float_type

    @property
    def as_convertible_interface(self):
        return {
            BuiltinType.string.value: BuiltinType.convertible_to_string,
            BuiltinType.i8.value: BuiltinType.convertible_to_i8,
            BuiltinType.i16.value: BuiltinType.convertible_to_i16,
            BuiltinType.i32.value: BuiltinType.convertible_to_i32,
            BuiltinType.i64.value: BuiltinType.convertible_to_i64,
            BuiltinType.u8.value: BuiltinType.convertible_to_u8,
            BuiltinType.u16.value: BuiltinType.convertible_to_u16,
            BuiltinType.u32.value: BuiltinType.convertible_to_u32,
            BuiltinType.u64.value: BuiltinType.convertible_to_u64,
        }[self.value]

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
                BuiltinType.convertible_to_string.value, BuiltinType.convertible_to_i8.value,
                BuiltinType.convertible_to_i16.value, BuiltinType.convertible_to_i32.value,
                BuiltinType.convertible_to_i64.value,
                BuiltinType.object_.value, BuiltinType.eq.value
            ],
            BuiltinType.i16.value: [
                BuiltinType.i16.value, BuiltinType.i32.value, BuiltinType.i64.value,
                BuiltinType.convertible_to_string.value,
                BuiltinType.convertible_to_i16.value, BuiltinType.convertible_to_i32.value,
                BuiltinType.convertible_to_i64.value,
                BuiltinType.object_.value, BuiltinType.eq.value
            ],
            BuiltinType.i32.value: [
                BuiltinType.i32.value, BuiltinType.i64.value, BuiltinType.convertible_to_string.value,
                BuiltinType.convertible_to_i32.value, BuiltinType.convertible_to_i64.value,
                BuiltinType.object_.value, BuiltinType.eq.value
            ],
            BuiltinType.i64.value: [
                BuiltinType.i64.value, BuiltinType.convertible_to_string.value, BuiltinType.object_.value,
                BuiltinType.eq.value, BuiltinType.convertible_to_i64.value,
            ],

            BuiltinType.u8.value: [
                BuiltinType.u8.value, BuiltinType.u16.value, BuiltinType.u32.value, BuiltinType.u64.value,
                BuiltinType.convertible_to_string.value, BuiltinType.convertible_to_i16.value,
                BuiltinType.convertible_to_i32.value, BuiltinType.convertible_to_i64.value,
                BuiltinType.convertible_to_u8.value, BuiltinType.convertible_to_u16.value,
                BuiltinType.convertible_to_u32.value, BuiltinType.convertible_to_u64.value,
                BuiltinType.object_.value, BuiltinType.eq.value
            ],
            BuiltinType.u16.value: [
                BuiltinType.u16.value, BuiltinType.u32.value, BuiltinType.u64.value,
                BuiltinType.convertible_to_string.value, BuiltinType.object_.value, BuiltinType.eq.value,
                BuiltinType.convertible_to_i32.value, BuiltinType.convertible_to_i64.value,
                BuiltinType.convertible_to_u16.value,
                BuiltinType.convertible_to_u32.value, BuiltinType.convertible_to_u64.value,
            ],
            BuiltinType.u32.value: [
                BuiltinType.u32.value, BuiltinType.u64.value, BuiltinType.convertible_to_string.value,
                BuiltinType.object_.value, BuiltinType.eq.value,
                BuiltinType.convertible_to_i64.value, BuiltinType.convertible_to_u32.value,
                BuiltinType.convertible_to_u64.value,
            ],
            BuiltinType.u64.value: [
                BuiltinType.u64.value, BuiltinType.convertible_to_string.value, BuiltinType.object_.value,
                BuiltinType.eq.value, BuiltinType.convertible_to_u64.value
            ],

            BuiltinType.f32.value: [
                BuiltinType.f32.value, BuiltinType.f64.value, BuiltinType.convertible_to_string.value,
                BuiltinType.object_.value, BuiltinType.eq.value
            ],
            BuiltinType.f64.value: [
                BuiltinType.f64.value, BuiltinType.convertible_to_string.value, BuiltinType.object_.value,
                BuiltinType.eq.value
            ],

            BuiltinType.string.value: [
                BuiltinType.string.value, BuiltinType.convertible_to_string.value,
                BuiltinType.object_.value, BuiltinType.eq.value
            ],
            BuiltinType.bool.value: [
                BuiltinType.bool.value, BuiltinType.convertible_to_string.value, BuiltinType.object_.value,
                BuiltinType.eq.value
            ],
            BuiltinType.char.value: [
                BuiltinType.char.value, BuiltinType.convertible_to_string.value, BuiltinType.object_.value,
                BuiltinType.eq.value
            ],
            BuiltinType.void.value: [BuiltinType.void.value],
            BuiltinType.arithmetic_object.value: [
                BuiltinType.addable.value, BuiltinType.subtractable.value, BuiltinType.multipliable.value,
                BuiltinType.divisible.value, BuiltinType.object_.value
            ],
            BuiltinType.eq.value: [BuiltinType.object_.value]
        }[self.value]

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


class BuiltinFunc(Expression, enum.Enum):
    print = "print"
    read = "read"

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


class PrivateBuiltinFunc(Expression, enum.Enum):
    vector_to_string = "__vector_to_string"

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


class SpecialName(Expression, enum.Enum):
    self = "self"

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


class Operator(enum.Enum):
    not_ = "not"
    and_ = "and"
    or_ = "or"
    is_ = "is"

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
    def higher_order_boolean_operators(cls):
        return [Operator.and_, Operator.or_, Operator.is_]

    @classmethod
    def comparison_operators(cls):
        return [Operator.lt_eq, Operator.gt_eq, Operator.eq_eq, Operator.neq, Operator.lt, Operator.gt]

    @classmethod
    def comparison_operators_names(cls):
        return [op.value for op in cls.comparison_operators()]

    @classmethod
    def assignment_operators(cls):
        return [Operator.add_eq, Operator.sub_eq, Operator.mul_eq, Operator.div_eq, Operator.eq]

    def to_arithmetic_operator(self):
        return Operator(self.value[0])


class SpecialMethods(enum.Enum):
    as_ = "as"

    eq = "__eq__"
    lt = "__lt__"
    gt = "__gt__"

    add = "__add__"
    sub = "__sub__"
    mul = "__mul__"
    div = "__div__"

    @classmethod
    def from_operator(cls, operator: Operator):
        return {
            Operator.eq_eq.value: SpecialMethods.eq,
            Operator.lt.value: SpecialMethods.lt,
            Operator.gt.value: SpecialMethods.gt,
            Operator.add.value: SpecialMethods.add,
            Operator.sub.value: SpecialMethods.sub,
            Operator.mul.value: SpecialMethods.mul,
            Operator.div.value: SpecialMethods.div,
        }[operator.value]


@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: Operator
    right: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.left.to_code()} {self.operator.value} {self.right.to_code()}"


@dataclass
class Cast(Expression):
    value: Expression
    to_type: Type
    is_builtin: bool = True

    def to_code(self, indentation_level: int = 0) -> str:
        return f"({self.to_type.to_code()})({self.value.to_code()})"


@dataclass
class BoolLiteral(Expression, enum.Enum):
    true = "True"
    false = "False"

    def to_code(self, indentation_level: int = 0) -> str:
        return self.value


@dataclass
class IntegerLiteral(Expression):
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
    typ: t.Optional[Type] = None

    def to_code(self, indentation_level: int = 0) -> str:
        return "[" + ', '.join(element.to_code() for element in self.elements) + "]"


class DictLiteral(Expression):
    keys: t.List[Expression]
    values: t.List[Expression]
    annotation: t.Optional[Type] = None

    def __init__(self, keys, values, annotation=None):
        self.keys = keys
        self.values = values
        self.annotation = annotation

    def to_code(self, indentation_level: int = 0) -> str:
        inner = []
        for key, value in zip(self.keys, self.values):
            inner.append(f"{key.to_code()}: {value.to_code()}")
        return "[" + ', '.join(element for element in inner) + "]"


@dataclass
class FunctionCall(Node, Expression):
    function_path: Expression
    args: t.List[Expression]
    instance_call_params: t.Optional[t.List[Type]] = None

    def to_code(self, indentation_level: int = 0) -> str:
        code = f"{self.function_path.to_code()}({', '.join(arg.to_code() for arg in self.args)})"
        return INDENTATION * indentation_level + code


@dataclass
class MethodCall(Node, Expression):
    instance_path: Expression
    method: Name
    args: t.List[Expression]
    instance_type: t.Optional[Type] = None
    is_algebraic_method: bool = False

    def __init__(
        self, line: int, instance_path: Expression, method: Name, args: t.List[Expression],
        instance_type: t.Optional[Type] = None, is_algebraic_method: bool = False
    ):
        self.line = line
        self.instance_path = instance_path
        self.method = method
        self.args = args
        self.instance_type = instance_type

    def to_code(self, indentation_level: int = 0) -> str:
        method = self.method.to_code()
        return f"{self.instance_path.to_code()}.{method}({', '.join(arg.to_code() for arg in self.args)})"


@dataclass
class Assignment(Node):
    left: AssignmentLeft
    operator: Operator
    right: Expression

    def to_code(self, indentation_level: int = 0) -> str:
        code = f"{self.left.to_code()} {self.operator.value} {self.right.to_code()}"
        return INDENTATION * indentation_level + code


@dataclass
class ConstantDeclaration(Node, Expression):
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
class For(Node):
    element: Name
    container: Expression
    body: AST
    container_type: t.Optional[Type] = None

    def to_code(self, indentation_level: int = 0) -> str:
        body = '\n'.join(node.to_code(indentation_level + 1) for node in self.body)
        code = f"for {self.element.to_code()} in {self.container.to_code()}:\n{body}"
        return INDENTATION * indentation_level + code


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
    condition: Expression
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


class Argument:
    name: Name
    type: Type
    value: t.Optional[Expression]

    def __init__(self, name: t.Union[str, Name], type_: Type, value: t.Optional[Expression] = None):
        if isinstance(name, str):
            self.name = Name(name)
        else:
            self.name = name
        self.type = type_
        self.value = value

    def to_code(self) -> str:
        if self.value:
            return f"{self.name.to_code()}: {self.type.to_code()} = {self.value.to_code()}"
        return f"{self.name.to_code()}: {self.type.to_code()}"


@dataclass
class GenericType(Type):
    name: t.Union[Name, BuiltinType]
    params: t.List[Type]

    def to_code(self, indentation_level: int = 0) -> str:
        return f"{self.name.to_code()}({', '.join(param.to_code() for param in self.params)})"


Arguments = t.List[Argument]
Parameters = t.List[Name]
Interface = t.Union[Name, BuiltinType, GenericType]
Interfaces = t.List[Interface]


@dataclass
class FunctionType(Type):
    params: Parameters
    args: Arguments
    return_type: Type
    is_algebraic_method: bool = False

    def to_code(self, indentation_level: int = 0) -> str:
        return f"({', '.join(arg.to_code() for arg in self.args)}) -> {self.return_type.to_code()}"


@dataclass
class MultipleDispatch(Type):
    funcs: t.List[FunctionType]

    def to_code(self, indentation_level: int = 0) -> str:
        return f"MultiD[{', '.join(func.to_code() for func in self.funcs)}]"


@dataclass
class StructType(Type):
    name: Name
    params: t.List[Type]

    def to_code(self, indentation_level: int = 0) -> str:
        return f"StructType({self.name.to_code()}, params={[param.to_code() for param in self.params]})"


@dataclass
class AlgebraicType(Type):
    base: Name
    params: t.List[Type]
    constructor: t.Optional[Name] = None
    constructor_types: t.Dict[str, Name] = field(default_factory=dict)

    def to_code(self, indentation_level: int = 0) -> str:
        if self.constructor:
            return f"{self.base.to_code()}.{self.constructor.to_code()}"
        if self.params:
            params = f"({', '.join(param.to_code() for param in self.params)})"
        else:
            params = ""
        return f"{self.base.to_code()}{params}"


class I8Fields(enum.Enum):
    add = SpecialMethods.add.value
    sub = SpecialMethods.sub.value
    mul = SpecialMethods.mul.value
    div = SpecialMethods.div.value

    lt = SpecialMethods.lt.value
    gt = SpecialMethods.gt.value
    eq = SpecialMethods.eq.value

    @property
    def as_type(self) -> Type:
        return {
            I8Fields.add.value: MultipleDispatch([
                FunctionType([], [Argument("other", BuiltinType.f32)], BuiltinType.f64),

                FunctionType([], [Argument("other", BuiltinType.i8)], BuiltinType.i16),
                FunctionType([], [Argument("other", BuiltinType.i16)], BuiltinType.i32),
                FunctionType([], [Argument("other", BuiltinType.i32)], BuiltinType.i64),

                FunctionType([], [Argument("other", BuiltinType.u8)], BuiltinType.i16),
                FunctionType([], [Argument("other", BuiltinType.u16)], BuiltinType.i32),
                FunctionType([], [Argument("other", BuiltinType.u32)], BuiltinType.i64),
            ]),

            I8Fields.sub.value: MultipleDispatch([
                FunctionType([], [Argument("other", BuiltinType.f32)], BuiltinType.f64),

                FunctionType([], [Argument("other", BuiltinType.i8)], BuiltinType.i16),
                FunctionType([], [Argument("other", BuiltinType.i16)], BuiltinType.i32),
                FunctionType([], [Argument("other", BuiltinType.i32)], BuiltinType.i64),

                FunctionType([], [Argument("other", BuiltinType.u8)], BuiltinType.i16),
                FunctionType([], [Argument("other", BuiltinType.u16)], BuiltinType.i32),
                FunctionType([], [Argument("other", BuiltinType.u32)], BuiltinType.i64),
            ]),

            I8Fields.mul.value: MultipleDispatch([
                FunctionType([], [Argument("other", BuiltinType.f32)], BuiltinType.f64),

                FunctionType([], [Argument("other", BuiltinType.i8)], BuiltinType.i16),
                FunctionType([], [Argument("other", BuiltinType.i16)], BuiltinType.i32),
                FunctionType([], [Argument("other", BuiltinType.i32)], BuiltinType.i64),

                FunctionType([], [Argument("other", BuiltinType.u8)], BuiltinType.i16),
                FunctionType([], [Argument("other", BuiltinType.u16)], BuiltinType.i32),
                FunctionType([], [Argument("other", BuiltinType.u32)], BuiltinType.i64),
            ]),

            I8Fields.div.value: MultipleDispatch([
                FunctionType([], [Argument("other", BuiltinType.i8)], BuiltinType.i64),
                FunctionType([], [Argument("other", BuiltinType.i16)], BuiltinType.i64),
                FunctionType([], [Argument("other", BuiltinType.i32)], BuiltinType.i64),

                FunctionType([], [Argument("other", BuiltinType.u8)], BuiltinType.i64),
                FunctionType([], [Argument("other", BuiltinType.u16)], BuiltinType.i64),
                FunctionType([], [Argument("other", BuiltinType.u32)], BuiltinType.i64),
            ]),

            I8Fields.lt.value: MultipleDispatch([
                FunctionType([], [Argument("other", BuiltinType.i8)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i16)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i32)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i64)], BuiltinType.bool),

                FunctionType([], [Argument("other", BuiltinType.u8)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u16)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u32)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u64)], BuiltinType.bool),
            ]),

            I8Fields.gt.value: MultipleDispatch([
                FunctionType([], [Argument("other", BuiltinType.i8)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i16)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i32)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i64)], BuiltinType.bool),

                FunctionType([], [Argument("other", BuiltinType.u8)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u16)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u32)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u64)], BuiltinType.bool),
            ]),

            I8Fields.eq.value: MultipleDispatch([
                FunctionType([], [Argument("other", BuiltinType.i8)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i16)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i32)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.i64)], BuiltinType.bool),

                FunctionType([], [Argument("other", BuiltinType.u8)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u16)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u32)], BuiltinType.bool),
                FunctionType([], [Argument("other", BuiltinType.u64)], BuiltinType.bool),
            ])
        }[self.value]


class StringFields(enum.Enum):
    split = "split"
    length = "length"

    add = SpecialMethods.add.value
    eq = SpecialMethods.eq.value

    @property
    def as_type(self) -> Type:
        return {
            StringFields.split.value: FunctionType(
                [], [Argument("by", BuiltinType.char)], return_type=VectorType(BuiltinType.string)
            ),
            StringFields.length.value: BuiltinType.u64,
            StringFields.add.value: FunctionType(
                [], [Argument("other", BuiltinType.string)], return_type=BuiltinType.string
            ),
            StringFields.eq.value: FunctionType(
                [], [Argument("other", BuiltinType.string)], return_type=BuiltinType.bool
            )
        }[self.value]


class VectorFields(enum.Enum):
    append = "append"
    length = "length"

    add = SpecialMethods.add.value
    eq = SpecialMethods.eq.value

    def as_type(self, element_type: Type) -> Type:
        from .utils import apply_mapping
        return apply_mapping({
            VectorFields.append.value: FunctionType(
                [], [Argument('element', Name('A'))], return_type=Name('A')
            ),
            VectorFields.add.value: FunctionType(
                [], [Argument("other", VectorType(Name('A')))], return_type=VectorType(Name('A'))
            ),
            VectorFields.eq.value: FunctionType(
                [], [Argument("other", VectorType(Name('A')))], return_type=BuiltinType.bool
            ),
            VectorFields.length.value: BuiltinType.u64,
        }[self.value], mapping={'A': element_type})


class DictFields(enum.Enum):
    length = "length"

    def as_type(self, _: Type, __: Type) -> Type:
        return {
            DictFields.length.value: BuiltinType.u64,
        }[self.value]


@dataclass
class FunctionDeclaration(Node):
    name: Name
    params: Parameters
    args: Arguments
    return_type: Type
    body: AST

    def to_code(self, indentation_level: int = 0) -> str:
        body = '\n'.join(node.to_code(indentation_level + 1) for node in self.body)
        if self.params:
            params = f"<{', '.join(param.to_code() for param in self.params)}>"
        else:
            params = ""
        args = ', '.join(arg.to_code() for arg in self.args)
        code = f"fun {self.name.to_code()}{params}({args}) -> {self.return_type.to_code()}:\n{body}"
        return INDENTATION * indentation_level + code


@dataclass
class MethodDeclaration(Node):
    name: Name
    args: Arguments
    return_type: Type
    body: AST

    def to_code(self, indentation_level: int = 0) -> str:
        body = '\n'.join(node.to_code(indentation_level + 1) for node in self.body)
        if self.args:
            args = "(" + ', '.join(arg.to_code() for arg in self.args) + ")"
        else:
            args = ''
        if self.return_type:
            return_type = " -> " + self.return_type.to_code()
        else:
            return_type = ""
        code = f"fun {self.name.to_code()}{args}{return_type}:\n{body}"
        return INDENTATION * indentation_level + code


@dataclass
class FieldDeclaration(Node):
    name: Name
    type: Type
    value: t.Optional[Expression]

    def to_code(self, indentation_level: int = 0) -> str:
        if self.value:
            return f"{self.name.to_code()}: {self.type.to_code()} = {self.value.to_code()}"
        return f"{self.name.to_code()}: {self.type.to_code()}"


@dataclass
class InitDeclaration(Node):
    args: Arguments
    body: AST

    def to_code(self, indentation_level: int = 0) -> str:
        body = '\n'.join(node.to_code(indentation_level + 1) for node in self.body)
        return INDENTATION * indentation_level + f"init({', '.join(arg.to_code() for arg in self.args)}):\n{body}"


@dataclass
class StructDeclaration(Node):
    name: Name
    parameters: Parameters
    interfaces: Interfaces
    private_fields: t.List[FieldDeclaration]
    public_fields: t.List[FieldDeclaration]
    init_declarations: t.List[InitDeclaration]
    private_methods: t.List[MethodDeclaration]
    public_methods: t.List[MethodDeclaration]
    special_methods: t.List[MethodDeclaration]

    def to_code(self, indentation_level: int = 0) -> str:
        if self.interfaces:
            interfaces = ' is ' + ', '.join(interface.to_code() for interface in self.interfaces)
        else:
            interfaces = ''

        if self.parameters:
            parameters = '(' + ', '.join(parameter.to_code() for parameter in self.parameters) + ')'
        else:
            parameters = ''

        private_fields = '\n'.join(node.to_code(indentation_level + 1) for node in self.private_fields)
        public_fields = '\n'.join(node.to_code(indentation_level + 1) for node in self.public_fields)
        init_declarations = '\n'.join(node.to_code(indentation_level + 1) for node in self.init_declarations)
        private_methods = '\n'.join(node.to_code(indentation_level + 1) for node in self.private_methods)
        public_methods = '\n'.join(node.to_code(indentation_level + 1) for node in self.public_methods)
        fields = private_fields + public_fields

        if not fields and not init_declarations and not private_methods and not public_methods:
            return INDENTATION * indentation_level + f"struct {self.name.to_code()}{parameters}{interfaces}"

        body = (
            fields + "\n" + init_declarations + "\n" + private_methods + "\n" + public_methods
        )
        return INDENTATION * indentation_level + f"struct {self.name.to_code()}{parameters}{interfaces}:\n{body}"


@dataclass
class WhereClause:
    condition: t.Optional[Expression]

    def to_code(self) -> str:
        if self.condition is None:
            return ''
        return f'where {self.condition.to_code()}'


@dataclass
class ExtensionDeclaration(Node):
    name: Name
    parameters: Parameters
    interfaces: Interfaces
    where_clause: WhereClause
    private_methods: t.List[MethodDeclaration]
    public_methods: t.List[MethodDeclaration]
    special_methods: t.List[MethodDeclaration]

    def to_code(self, indentation_level: int = 0) -> str:
        if self.interfaces:
            interfaces = ' is ' + ', '.join(interface.to_code() for interface in self.interfaces)
        else:
            interfaces = ''

        if self.parameters:
            parameters = '(' + ', '.join(parameter.to_code() for parameter in self.parameters) + ')'
        else:
            parameters = ''

        where = self.where_clause.to_code()
        private_methods = '\n'.join(node.to_code(indentation_level + 1) for node in self.private_methods)
        public_methods = '\n'.join(node.to_code(indentation_level + 1) for node in self.public_methods)

        if not private_methods and not public_methods:
            return INDENTATION * indentation_level + f"extension {self.name.to_code()}{parameters}{interfaces}{where}"

        body = private_methods + "\n" + public_methods
        return (
            INDENTATION * indentation_level + f"extension {self.name.to_code()}{parameters}{interfaces}{where}:\n{body}"
        )


@dataclass
class AlgebraicDeclaration(Node):
    name: Name
    parameters: Parameters
    constructors: t.List[StructDeclaration]
    public_methods: t.List[MethodDeclaration]
    private_methods: t.List[MethodDeclaration]

    def to_code(self, indentation_level: int = 0) -> str:
        if self.parameters:
            parameters = '(' + ', '.join(parameter.to_code() for parameter in self.parameters) + ')'
        else:
            parameters = ''
        constructors = '\n'.join(node.to_code(indentation_level + 1) for node in self.constructors)
        private_methods = '\n'.join(node.to_code(indentation_level + 1) for node in self.private_methods)
        public_methods = '\n'.join(node.to_code(indentation_level + 1) for node in self.public_methods)
        body = constructors + "\n" + private_methods + "\n" + public_methods
        return INDENTATION * indentation_level + f"algebraic {self.name.to_code()}{parameters}:\n{body}"


@dataclass
class InterfaceDeclaration(Node):
    name: Name
    parameters: Parameters
    parent_interfaces: Interfaces
    fields: t.List[FieldDeclaration]
    methods: t.List[MethodDeclaration]

    def to_code(self, indentation_level: int = 0) -> str:
        if self.parent_interfaces:
            interfaces = ' is ' + ', '.join(interface.to_code() for interface in self.parent_interfaces)
        else:
            interfaces = ''

        if self.parameters:
            parameters = '(' + ', '.join(parameter.to_code() for parameter in self.parameters) + ')'
        else:
            parameters = ''

        methods = '\n'.join(node.to_code(indentation_level + 1) for node in self.methods)
        fields = '\n'.join(node.to_code(indentation_level + 1) for node in self.fields)
        body = fields + "\n" + methods
        return INDENTATION * indentation_level + f"interface {self.name.to_code()}{parameters}{interfaces}:\n{body}"
