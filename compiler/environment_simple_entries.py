import typing as t
from dataclasses import dataclass

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


@dataclass
class InitEntry(Entry):
    args: t.List[nodes.Argument]
    body: nodes.AST


@dataclass
class StructEntry(Entry):
    name: nodes.Name
    params: nodes.Parameters
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
    fields: t.Dict[str, Entry]
    methods: t.Dict[str, FunctionEntry]


@dataclass
class ParameterEntry(Entry):
    name: nodes.Name
