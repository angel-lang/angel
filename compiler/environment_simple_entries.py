import typing as t
from dataclasses import dataclass, field

from . import nodes


@dataclass
class Entry:
    line: int


@dataclass
class FunctionEntry(Entry):
    name: nodes.Name
    args: t.List[nodes.Argument]
    return_type: nodes.Type
    body: nodes.AST
    where_clauses: t.List[nodes.WhereClause] = field(default_factory=list)


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
