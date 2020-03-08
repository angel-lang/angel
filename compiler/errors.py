import typing as t

from dataclasses import dataclass

from . import nodes


@dataclass
class Code:
    string: str
    line: int
    column: t.Optional[int] = None

    def __str__(self) -> str:
        if self.column is not None:
            spaces = " " * (len(f"{self.line}: ") + self.column - 1)
            return f"{self.line}: {self.string}\n{spaces}^"
        return f"{self.line}: {self.string}"


class AngelError(Exception):
    pass


class AngelNotImplemented(AngelError):
    pass


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
