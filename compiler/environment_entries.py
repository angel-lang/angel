import typing as t

from dataclasses import dataclass

from . import nodes


@dataclass
class Entry:
    line: int


@dataclass
class ConstantEntry(Entry):
    name: nodes.Name
    type: nodes.Type
    has_value: bool
    computed_value: t.Any = None


@dataclass
class VariableEntry(Entry):
    name: nodes.Name
    type: nodes.Type
    computed_value: t.Any = None


@dataclass
class FunctionEntry(Entry):
    name: nodes.Name
    args: t.List[nodes.Argument]
    return_type: nodes.Type
    body: nodes.AST
