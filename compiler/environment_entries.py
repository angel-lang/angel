import typing as t

from dataclasses import dataclass

from . import nodes
from .environment_simple_entries import (
    Entry, FunctionEntry, AlgebraicEntry, InitEntry, StructEntry, ParameterEntry, InterfaceEntry
)
from .estimation_nodes import Expression


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
