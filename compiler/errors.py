import typing as t

from dataclasses import dataclass

from . import nodes


@dataclass
class Code:
    string: str = ""
    line: int = 0
    column: t.Optional[int] = None

    def __str__(self) -> str:
        if self.column is not None:
            spaces = " " * (len(f"{self.line}: ") + self.column - 1)
            return f"{self.line}: {self.string}\n{spaces}^"
        return f"{self.line}: {self.string}"


class AngelError(Exception):
    pass


class AngelNotImplemented(AngelError):
    def __init__(self, msg: t.Optional[str] = None):
        self.msg = msg

    def __str__(self):
        if self.msg:
            return self.msg
        return "Not implemented"


class AngelDivByZero(AngelError):
    def __str__(self):
        return "Division by zero is not allowed"


@dataclass
class AngelPrivateFieldsNotInitializedAndNoInit(AngelError):
    field: nodes.Name
    code: Code

    def __str__(self) -> str:
        return "\n".join((
            "Initialization Error: all private fields must be initialized to generate default init",
            f"                      however, field '{self.field.to_code()}' does not have default value",
            "",
            str(self.code),
        ))


@dataclass
class AngelFieldError(AngelError):
    instance: nodes.Expression
    instance_type: nodes.Type
    field_name: str
    code: Code

    def __str__(self) -> str:
        return "\n".join((
            (f"Field Error: '{self.instance.to_code()}' of type '{self.instance_type.to_code()}' "
             f"does not have '{self.field_name}' field"),
            "",
            str(self.code),
        ))


@dataclass
class AngelSubscriptError(AngelError):
    instance: nodes.Expression
    instance_type: nodes.Type
    index: nodes.Expression
    code: Code

    def __str__(self) -> str:
        return "\n".join((
            (f"Subscript Error: '{self.instance.to_code()}' of type '{self.instance_type.to_code()}' "
             f"cannot be subscripted by '{self.index.to_code()}'"),
            "",
            str(self.code),
        ))


@dataclass
class AngelTypeError(AngelError):
    message: str
    code: Code
    possible_types: t.List[nodes.Type]

    def __str__(self) -> str:
        possible_types = ', '.join(type_.to_code() for type_ in self.possible_types)
        return "\n".join((
            f"Type Error: {self.message}",
            "",
            str(self.code),
            "",
            f"possible types: {possible_types}"
        ))


@dataclass
class AngelWrongArguments(AngelError):
    expected: str
    code: Code
    got_args: t.List[nodes.Expression]

    def __str__(self):
        args = "(" + ", ".join(arg.to_code() for arg in self.got_args) + ")"
        return "\n".join((
            f"Arguments Error: got '{args}', expected '{self.expected}' in",
            "",
            str(self.code),
        ))


@dataclass
class AngelNoncallableCall(AngelError):
    noncallable: nodes.Expression
    code: Code

    def __str__(self):
        return "\n".join((
            f"Noncallable Call Error: noncallable '{self.noncallable.to_code()}' was called in",
            "",
            str(self.code),
        ))


@dataclass
class AngelSyntaxError(AngelError):
    message: str
    code: Code

    def __str__(self) -> str:
        return "\n".join((
            f"Syntax Error: {self.message}",
            "",
            str(self.code)
        ))


@dataclass
class AngelNameError(AngelError):
    name: nodes.Name
    code: Code

    def __str__(self) -> str:
        return "\n".join((
            f"Name Error: '{self.name.to_code()}' is not defined but used in",
            "",
            str(self.code),
        ))


@dataclass
class AngelConstantReassignment(AngelError):
    cannot_reassign: nodes.Expression
    reassignment_code: Code
    definition_code: Code

    def __str__(self) -> str:
        return "\n".join((
            f"Immutability Error: cannot reassign value of '{self.cannot_reassign.to_code()}' in",
            "",
            str(self.reassignment_code),
            "",
            "It was defined immutable in",
            "",
            str(self.definition_code),
        ))
