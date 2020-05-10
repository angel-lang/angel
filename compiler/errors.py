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
class _AngelInterfaceError(AngelError):
    subject: nodes.Name
    interface: nodes.Name
    code: Code


@dataclass
class AngelMissingInterfaceMember(_AngelInterfaceError):
    missing_member: nodes.Name
    inherited_from: t.Optional[nodes.Type] = None

    def __str__(self) -> str:
        subject = self.subject.to_code()
        if self.inherited_from:
            inheritence = f" (which inherits from '{self.inherited_from.to_code()}')"
        else:
            inheritence = ""
        return "\n".join((
            f"Interface Implementation Error: '{subject}' implements '{self.interface.to_code()}'{inheritence}",
            f"                                however, member '{self.missing_member.to_code()}' is missing",
            "",
            str(self.code),
        ))


@dataclass
class AngelInterfaceFieldError(_AngelInterfaceError):
    field: nodes.Name
    subject_field_type: nodes.Type
    interface_field_type: nodes.Type
    inherited_from: t.Optional[nodes.Type] = None

    def __str__(self) -> str:
        subject = self.subject.to_code()
        l2 = f"however, '{self.field.to_code()}' has type '{self.subject_field_type.to_code()}'"
        l3 = f"and expected type is '{self.interface_field_type.to_code()}'"
        if self.inherited_from:
            inheritence = f" (which inherits from '{self.inherited_from.to_code()}')"
        else:
            inheritence = ""
        return "\n".join((
            f"Interface Implementation Error: '{subject}' implements '{self.interface.to_code()}'{inheritence}",
            "                                " + l2,
            "                                " + l3,
            "",
            str(self.code),
        ))


@dataclass
class AngelInterfaceMethodError(_AngelInterfaceError):
    method: nodes.Name
    subject_method_args: nodes.Arguments
    subject_method_return_type: nodes.Type
    interface_method_args: nodes.Arguments
    interface_method_return_type: nodes.Type
    inherited_from: t.Optional[nodes.Type] = None

    def __str__(self) -> str:
        subject = self.subject.to_code()
        method = self.method.to_code()
        subject_args = ', '.join(arg.to_code() for arg in self.subject_method_args)
        subject_type = self.subject_method_return_type.to_code()
        interface_args = ', '.join(arg.to_code() for arg in self.interface_method_args)
        interface_type = self.interface_method_return_type.to_code()

        if self.inherited_from:
            inheritence = f" (which inherits from '{self.inherited_from.to_code()}')"
        else:
            inheritence = ""

        l2 = f"however, it implemented {method}({subject_args}) -> {subject_type}"
        l3 = f"and expected implementation is {method}({interface_args}) -> {interface_type}"
        return "\n".join((
            f"Interface Implementation Error: '{subject}' implements '{self.interface.to_code()}'{inheritence}",
            "                                " + l2,
            "                                " + l3,
            "",
            str(self.code),
        ))


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
class AngelConstructorError(AngelError):
    algebraic: nodes.Type
    constructor: str
    code: Code

    def __str__(self) -> str:
        return "\n".join((
            (f"Constructor Error: type '{self.algebraic.to_code()}' "
             f"does not have '{self.constructor}' constructor"),
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
class AngelUnsatisfiedWhereClause(AngelError):
    clause: nodes.Expression
    code: Code

    def __str__(self):
        return "\n".join((
            f"Unsatisfied Clause Error: unsatisfied {self.clause.to_code()}",
            "",
            str(self.code),
        ))


@dataclass
class AngelMultipleDispatchError(AngelError):
    func_path: nodes.Expression
    funcs: t.List[nodes.FunctionType]
    got_args: t.List[nodes.Type]
    supertype: t.Optional[nodes.Type]
    code: Code

    def __str__(self):
        args = ', '.join(arg.to_code() for arg in self.got_args)
        impls = '\n'.join(func.to_code() for func in self.funcs)
        if self.supertype:
            return_type = f" and returns {self.supertype.to_code()}"
        else:
            return_type = ""
        return "\n".join((
            f"Multiple Dispatch Error: there is no {self.func_path.to_code()} that expects ({args}){return_type}.",
            f"but there are implementations:\n{impls}",
            "",
            str(self.code),
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
