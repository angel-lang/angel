import typing as t

from . import nodes, environment_entries as entries, estimation_nodes as enodes, errors
from .enums import DeclType
from .constants import SELF_NAME
from .utils import dispatch


def copy_environment(to_copy):
    result = Environment()
    result.where_clauses = list(to_copy.where_clauses)
    result.space = []
    result.nesting_level = -1
    for scope in to_copy.space:
        # Entries are the same
        result_scope = dict(scope)
        result.space.append(result_scope)
        result.nesting_level += 1
    return result


class Environment:

    def __init__(self, space: t.Optional[t.List[t.Dict[str, entries.Entry]]] = None, load_builtins: bool = False):
        self._load_node_dispatcher: t.Dict[type, t.Callable[[nodes.Node], None]] = {
            nodes.InterfaceDeclaration: self._load_interface,
            nodes.FunctionDeclaration: self._load_function,
        }

        self.space = space or [{}]
        if space:
            self.nesting_level = len(space) - 1
        else:
            self.nesting_level = 0

        self.parents: t.List[nodes.Name] = []
        self.where_clauses: t.List[nodes.Expression] = []
        self.code = errors.Code()

        if load_builtins:
            self.load_builtins()

    def __getitem__(self, key) -> t.Optional[entries.Entry]:
        """Get entry. Return None if not found."""
        nesting_level = self.nesting_level
        while nesting_level >= 0:
            entry = self.space[nesting_level].get(key)
            if entry is not None:
                return entry
            nesting_level -= 1
        return None

    def get(self, key: t.Union[nodes.Name, nodes.BuiltinType]) -> entries.Entry:
        """Get entry of name. Raise NameError if name is not found."""
        if isinstance(key, nodes.BuiltinType):
            id_ = key.value
        else:
            assert not key.module
            id_ = key.member

        entry = self[id_]
        if entry is None:
            raise errors.AngelNameError(key, self.code)
        return entry

    def get_type(self, key: t.Union[nodes.BuiltinType, nodes.GenericType, nodes.Name]) -> entries.Entry:
        if isinstance(key, nodes.GenericType):
            return self.get_type(key.name)
        elif isinstance(key, (nodes.Name, nodes.BuiltinType)):
            return self.get(key)

    def get_algebraic(self, algebraic: nodes.AlgebraicType) -> t.Union[entries.AlgebraicEntry, entries.StructEntry]:
        """Get entry of algebraic data type or its constructor if algebraic.constructor."""
        algebraic_entry = self.get(algebraic.base)
        assert isinstance(algebraic_entry, entries.AlgebraicEntry)
        if not algebraic.constructor:
            return algebraic_entry
        return algebraic_entry.constructors[algebraic.constructor.member]

    def add_declaration(
        self, node: nodes.Decl, estimated_value: t.Optional[enodes.Expression] = None, **kwarguments
    ) -> None:
        if not estimated_value:
            estimated_value = enodes.DynamicValue(kwarguments.get("type", node.type))
        parameters = {
            "decl_type": node.decl_type,
            "line": node.line,
            "name": node.name,
            "type": node.type,
            "value": node.value,
            "estimated_value": estimated_value
        }
        parameters.update(kwarguments)
        self.space[self.nesting_level][parameters["name"].member] = entries.DeclEntry(**parameters)      # type: ignore

    def add_arguments(self, line: int, arguments: t.List[nodes.Argument]) -> None:
        for arg in arguments:
            value = enodes.DynamicValue(arg.type)
            self.space[self.nesting_level][arg.name.member] = entries.DeclEntry(
                line, DeclType.constant, arg.name, arg.type, value=None, estimated_value=value
            )

    def add_function(
        self, line: int, name: t.Union[nodes.Name, nodes.BuiltinFunc], parameters: nodes.Parameters, arguments: t.List[nodes.Argument],
        return_type: nodes.Type, where_clause: t.Optional[nodes.Expression]
    ) -> None:
        space_copy = copy_environment(self).space
        clauses = list(self.where_clauses)
        if where_clause:
            clauses.append(where_clause)
        name_string = name.member if isinstance(name, nodes.Name) else name.value
        # TODO: BuiltinFunc name should be BuiltinFunc in object
        self.space[self.nesting_level][name_string] = entries.FunctionEntry(
            line, nodes.Name(name_string), parameters, arguments, return_type, body=[], where_clauses=clauses, saved_environment=space_copy
        )

    # TODO: add parameters to method declarations
    def add_method(
        self, line: int, name: t.Union[nodes.SpecialMethods, nodes.Name],
        arguments: t.List[nodes.Argument], return_type: nodes.Type
    ) -> None:
        entry = self._get_parent_type_entry()
        space_copy = copy_environment(self).space
        if isinstance(name, nodes.SpecialMethods):
            key = name.value
            name = nodes.Name(key)
        else:
            key = name.member
        entry.methods[key] = entries.FunctionEntry(
            line, name, [], arguments, return_type, body=[], where_clauses=list(self.where_clauses),
            saved_environment=space_copy
        )

    def add_field(self, line: int, name: nodes.Name, type_: nodes.Type) -> None:
        entry = self._get_parent_type_entry()
        assert isinstance(entry, (entries.StructEntry, entries.InterfaceEntry))
        entry.fields[name.member] = entries.DeclEntry(
            line, DeclType.variable, name, type_, value=None, estimated_value=enodes.DynamicValue(type_)
        )

    def add_self(self, line: int, is_variable: bool = False) -> None:
        type_ = self._build_parent_struct_type()
        self.add_declaration(nodes.Decl(line, DeclType.variable, SELF_NAME, type_))

    def add_init_declaration(self, line: int, arguments: nodes.Arguments) -> None:
        entry = self._get_parent_type_entry()
        assert isinstance(entry, entries.StructEntry)
        entry.init_declarations[','.join(arg.to_code() for arg in arguments)] = entries.InitEntry(line, arguments, body=[])

    def _get_parent_type_entry(self) -> t.Union[entries.StructEntry, entries.AlgebraicEntry, entries.InterfaceEntry]:
        assert self.parents
        entry = self[self.parents[0].member]
        for parent in self.parents[1:]:
            if isinstance(entry, entries.AlgebraicEntry):
                entry = entry.constructors[parent.member]
            else:
                assert 0, "Non-supported struct nesting"
        assert isinstance(entry, (entries.AlgebraicEntry, entries.StructEntry, entries.InterfaceEntry))
        return entry

    def _build_parent_struct_type(self) -> nodes.Type:
        assert self.parents
        type_: nodes.Type = self.parents[-1]
        for parent in reversed(self.parents[:-1]):
            # TODO: add proper parameters and constructor_types
            assert isinstance(type_, nodes.Name)
            type_ = nodes.AlgebraicType(parent, [], type_)
        return type_

    def add_struct(self, line: int, name: nodes.Name, parameters: nodes.Parameters, interfaces: nodes.Interfaces) -> None:
        if self.parents:
            self.add_algebraic_constructor(line, name, parameters)
        else:
            self.space[self.nesting_level][name.member] = entries.StructEntry(
                line, name, parameters, interfaces, fields={}, init_declarations={}, methods={}
            )

    def add_algebraic_constructor(self, line: int, name: nodes.Name, parameters: nodes.Parameters) -> None:
        assert self.parents
        entry = self[self.parents[-1].member]
        assert isinstance(entry, entries.AlgebraicEntry)
        entry.constructors[name.member] = entries.StructEntry(
            line, name, parameters, implemented_interfaces=[], fields={}, init_declarations={}, methods={}
        )

    def add_algebraic(self, line: int, name: nodes.Name, parameters: nodes.Parameters) -> None:
        self.space[self.nesting_level][name.member] = entries.AlgebraicEntry(
            line, name, parameters, constructors={}, methods={}
        )

    def add_interface(
        self, line: int, name: t.Union[nodes.BuiltinType, nodes.Name], parameters: nodes.Parameters,
        implemented_interfaces: nodes.Interfaces
    ) -> None:
        inherited_fields: t.Dict[str, t.Tuple[nodes.Interface, entries.Entry]] = {}
        inherited_methods: t.Dict[str, t.Tuple[nodes.Interface, entries.FunctionEntry]] = {}
        for interface in implemented_interfaces:
            if isinstance(interface, nodes.Name):
                interface_entry = self.get(interface)
            elif isinstance(interface, nodes.BuiltinType):
                interface_entry = self.get(nodes.Name(interface.value))
            else:
                # TODO: support inheritance from builtin interfaces
                assert isinstance(interface.name, nodes.Name)
                interface_entry = self.get(interface.name)
            assert isinstance(interface_entry, entries.InterfaceEntry)

            for field_name, field_entry in interface_entry.fields.items():
                inherited_fields[field_name] = (interface, field_entry)
            inherited_fields.update(interface_entry.inherited_fields)

            for method_name, method_entry in interface_entry.methods.items():
                inherited_methods[method_name] = (interface, method_entry)
            inherited_methods.update(interface_entry.inherited_methods)

        name_string = name.member if isinstance(name, nodes.Name) else name.value
        self.space[self.nesting_level][name_string] = entries.InterfaceEntry(
            line, name, parameters, implemented_interfaces=implemented_interfaces, fields={}, methods={},
            inherited_fields=inherited_fields, inherited_methods=inherited_methods
        )

    def add_parameters(self, line: int, parameters: nodes.Parameters) -> None:
        for parameter in parameters:
            interfaces, fields, methods = self.get_required_data_from_where_clauses(parameter)
            self.space[self.nesting_level][parameter.member] = entries.ParameterEntry(
                line, parameter, interfaces, fields, methods
            )

    def update_function_body(self, name: nodes.Name, body: nodes.AST) -> None:
        entry = self.space[self.nesting_level][name.member]
        assert isinstance(entry, entries.FunctionEntry)
        entry.body = body

    def update_method_body(self, name: t.Union[nodes.SpecialMethods, nodes.Name], body: nodes.AST) -> None:
        entry = self._get_parent_type_entry()
        if isinstance(name, nodes.SpecialMethods):
            key = name.value
        else:
            key = name.member
        entry.methods[key].body = body

    def update_init_declaration_body(self, arguments: nodes.Arguments, body: nodes.AST) -> None:
        entry = self._get_parent_type_entry()
        assert isinstance(entry, entries.StructEntry)
        entry.init_declarations[','.join(arg.to_code() for arg in arguments)].body = body

    def update_code(self, code: errors.Code) -> None:
        self.code = code

    def inc_nesting(self, parent: t.Optional[nodes.Name] = None) -> None:
        self.nesting_level += 1
        self.space.append({})
        if parent:
            self.parents.append(parent)

    def dec_nesting(self, parent: t.Optional[nodes.Name] = None) -> None:
        del self.space[self.nesting_level]
        self.nesting_level -= 1
        if parent:
            self.parents.pop()

    def add_where_clause(self, where_clause: nodes.Expression) -> None:
        self.where_clauses.append(where_clause)

    def remove_where_clause(self) -> None:
        self.where_clauses.pop()

    def _get_required_data_from_clause(self, name: nodes.Name, condition: nodes.Expression):
        interfaces, fields, methods = [], {}, {}
        if isinstance(condition, nodes.BinaryExpression):
            if condition.operator == nodes.Operator.is_:
                if condition.left == name:
                    interfaces.append(condition.right)
                    assert isinstance(condition.right, (nodes.Name, nodes.BuiltinType, nodes.GenericType))
                    interface_entry = self.get_type(condition.right)
                    assert isinstance(interface_entry, entries.InterfaceEntry)
                    fields.update(interface_entry.fields)
                    fields.update({
                        k: field_entry for k, (interface, field_entry) in interface_entry.inherited_fields.items()
                    })
                    methods.update(interface_entry.methods)
                    methods.update({
                        k: method_entry for k, (interface, method_entry) in interface_entry.inherited_methods.items()
                    })
            elif condition.operator == nodes.Operator.and_:
                sub_interfaces1, sub_fields1, sub_methods1 = self._get_required_data_from_clause(name, condition.left)
                sub_interfaces2, sub_fields2, sub_methods2 = self._get_required_data_from_clause(
                    name, condition.right
                )
                interfaces.extend(sub_interfaces1)
                interfaces.extend(sub_interfaces2)
                fields.update(sub_fields1)
                fields.update(sub_fields2)
                methods.update(sub_methods1)
                methods.update(sub_methods2)
            else:
                assert 0, f"Cannot get required data from binary expression {condition}"
        else:
            assert 0, f"Cannot get required data from where clause {condition}"
        return interfaces, fields, methods

    def get_required_data_from_where_clauses(
        self, name: nodes.Name
    ) -> t.Tuple[nodes.Interfaces, t.Dict[str, entries.Entry], t.Dict[str, entries.FunctionEntry]]:
        interfaces: nodes.Interfaces = []
        fields: t.Dict[str, entries.Entry] = {}
        methods: t.Dict[str, entries.FunctionEntry] = {}
        for clause in self.where_clauses:
            sub_interfaces, sub_fields, sub_methods = self._get_required_data_from_clause(name, clause)
            interfaces.extend(sub_interfaces)
            fields.update(sub_fields)
            methods.update(sub_methods)
        return interfaces, fields, methods

    def _load_interface(self, node: nodes.Node):
        assert isinstance(node, nodes.InterfaceDeclaration)
        self.add_interface(
            line=node.line, name=node.name, parameters=node.parameters,
            implemented_interfaces=node.implemented_interfaces
        )
        if isinstance(node.name, nodes.BuiltinType):
            self.parents.append(nodes.Name(node.name.value))
        else:
            self.parents.append(node.name)
        for method_declaration in node.methods:
            self.add_method(
                line=method_declaration.line, name=method_declaration.name,
                arguments=method_declaration.arguments, return_type=method_declaration.return_type
            )
        self.parents.pop()
        # TODO: add fields

    def _load_function(self, node: nodes.Node):
        assert isinstance(node, nodes.FunctionDeclaration)
        self.add_function(
            line=node.line, name=node.name, parameters=node.parameters, arguments=node.arguments,
            return_type=node.return_type, where_clause=node.where_clause
        )

    def load_builtins(self):
        from . import parsers, clarification, context
        with open("stdlib/builtins/main.angel", "r") as file:
            contents = file.read()
        parser = parsers.Parser()
        clarifier = clarification.Clarifier(context.Context(contents.splitlines(), main_hash="", mangle_names=False))
        for node in clarifier.clarify_ast(parser.parse(contents)):
            dispatch(self._load_node_dispatcher, type(node), node)
