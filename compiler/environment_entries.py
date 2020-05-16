import typing as t

from dataclasses import dataclass, field
from enum import Enum

from . import nodes
from .enums import DeclType
from .estimation_nodes import Expression, Function


@dataclass
class Entry:
    line: int


@dataclass
class FunctionEntry(Entry):
    name: nodes.Name
    params: nodes.Parameters
    args: t.List[nodes.Argument]
    return_type: nodes.Type
    body: nodes.AST
    where_clauses: t.List[nodes.Expression] = field(default_factory=list)

    # TODO: add an environment argument
    def to_estimated_function(self) -> Function:
        return Function(
            self.name, self.params, self.args, self.return_type, self.where_clauses, specification=self.body
        )


@dataclass
class InitEntry(Entry):
    args: t.List[nodes.Argument]
    body: nodes.AST


@dataclass
class StructEntry(Entry):
    name: nodes.Name
    params: nodes.Parameters
    implemented_interfaces: nodes.Interfaces
    fields: t.Dict[str, Entry]
    init_declarations: t.Dict[str, InitEntry]
    methods: t.Dict[str, FunctionEntry]


@dataclass
class AlgebraicEntry(Entry):
    name: nodes.Name
    params: nodes.Parameters
    constructors: t.Dict[str, StructEntry]
    methods: t.Dict[str, FunctionEntry]


@dataclass
class InterfaceEntry(Entry):
    name: nodes.Name
    params: nodes.Parameters
    parent_interfaces: nodes.Interfaces
    fields: t.Dict[str, Entry]
    methods: t.Dict[str, FunctionEntry]
    inherited_fields: t.Dict[str, t.Tuple[nodes.Interface, Entry]]
    inherited_methods: t.Dict[str, t.Tuple[nodes.Interface, FunctionEntry]]


@dataclass
class ParameterEntry(Entry):
    name: nodes.Name
    parent_interfaces: nodes.Interfaces
    fields: t.Dict[str, Entry]
    methods: t.Dict[str, FunctionEntry]


@dataclass
class DeclEntry(Entry):
    decl_type: DeclType
    name: nodes.Name
    type: nodes.Type
    value: t.Optional[nodes.Expression]
    estimated_value: Expression

    def __post_init__(self):
        self.has_value = self.value is not None

    @property
    def is_constant(self) -> bool:
        return self.decl_type.value == DeclType.constant.value

    @property
    def is_variable(self) -> bool:
        return self.decl_type.value == DeclType.variable.value
