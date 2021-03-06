import typing as t
from dataclasses import dataclass, field

from . import nodes
from .enums import DeclType
from .estimation_nodes import Expression, Function


@dataclass
class Entry:
    line: int


@dataclass
class FunctionEntry(Entry):
    name: nodes.Name
    parameters: nodes.Parameters
    arguments: t.List[nodes.Argument]
    return_type: nodes.Type
    body: nodes.AST
    where_clauses: t.List[nodes.Expression] = field(default_factory=list)
    saved_environment: t.List[t.Dict[str, Entry]] = field(default_factory=list)

    def to_estimated_function(self) -> Function:
        return Function(
            self.name, self.parameters, self.arguments, self.return_type, self.where_clauses, specification=self.body,
            saved_environment=self.saved_environment
        )

    def to_function_type(self) -> nodes.FunctionType:
        return nodes.FunctionType(
            self.parameters, self.arguments, self.return_type, self.where_clauses, self.saved_environment
        )


@dataclass
class InitEntry(Entry):
    arguments: t.List[nodes.Argument]
    body: nodes.AST


@dataclass
class StructEntry(Entry):
    name: nodes.Name
    parameters: nodes.Parameters
    implemented_interfaces: nodes.Interfaces
    fields: t.Dict[str, Entry]
    init_declarations: t.Dict[str, InitEntry]
    methods: t.Dict[str, FunctionEntry]

    def implements_interface(self, interface: nodes.Interface) -> bool:
        return interface in self.implemented_interfaces


@dataclass
class AlgebraicEntry(Entry):
    name: nodes.Name
    parameters: nodes.Parameters
    constructors: t.Dict[str, StructEntry]
    methods: t.Dict[str, FunctionEntry]


@dataclass
class InterfaceEntry(Entry):
    name: t.Union[nodes.BuiltinType, nodes.Name]
    parameters: nodes.Parameters
    implemented_interfaces: nodes.Interfaces
    fields: t.Dict[str, Entry]
    methods: t.Dict[str, FunctionEntry]
    inherited_fields: t.Dict[str, t.Tuple[nodes.Interface, Entry]]
    inherited_methods: t.Dict[str, t.Tuple[nodes.Interface, FunctionEntry]]


@dataclass
class ParameterEntry(Entry):
    name: nodes.Name
    implemented_interfaces: nodes.Interfaces
    fields: t.Dict[str, Entry]
    methods: t.Dict[str, FunctionEntry]

    def implements_interface(self, interface: nodes.Interface) -> bool:
        return interface in self.implemented_interfaces


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
