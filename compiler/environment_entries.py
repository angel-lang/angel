import typing as t

from dataclasses import dataclass

from . import nodes
from .estimation_nodes import Expression


@dataclass
class Entry:
    line: int


@dataclass
class ConstantEntry(Entry):
    name: nodes.Name
    type: nodes.Type
    has_value: bool
    estimated_value: t.Optional[Expression] = None


@dataclass
class VariableEntry(Entry):
    name: nodes.Name
    type: nodes.Type
    value: t.Optional[nodes.Expression]
    estimated_value: t.Optional[Expression] = None


@dataclass
class FunctionEntry(Entry):
    name: nodes.Name
    args: t.List[nodes.Argument]
    return_type: nodes.Type
    body: nodes.AST


@dataclass
class StructEntry(Entry):
    name: nodes.Name
    fields: t.Dict[str, Entry]
    methods: t.Dict[str, FunctionEntry]
