import typing as t

from . import nodes, environment_entries as entries, estimation_nodes as enodes, errors


class Environment:

    def __init__(self):
        self.space = [{}]
        self.nesting_level = 0
        self.parents: t.List[nodes.Name] = []
        self.code = errors.Code()

    def __getitem__(self, key) -> t.Optional[entries.Entry]:
        """Get entry. Return None if not found."""
        nesting_level = self.nesting_level
        while nesting_level >= 0:
            entry = self.space[nesting_level].get(key)
            if entry is not None:
                return entry
            nesting_level -= 1
        return None

    def get(self, key: nodes.Name) -> entries.Entry:
        """Get entry of name. Raise NameError if name is not found."""
        assert not key.module
        entry = self[key.member]
        if entry is None:
            raise errors.AngelNameError(key, self.code)
        return entry

    def get_algebraic(self, algebraic: nodes.AlgebraicType) -> t.Union[entries.AlgebraicEntry, entries.StructEntry]:
        """Get entry of algebraic data type or its constructor if algebraic.constructor."""
        algebraic_entry = self.get(algebraic.base)
        assert isinstance(algebraic_entry, entries.AlgebraicEntry)
        if not algebraic.constructor:
            return algebraic_entry
        return algebraic_entry.constructors[algebraic.constructor.member]

    def add_constant(
            self, line: int, name: nodes.Name, type_: nodes.Type, value: t.Optional[nodes.Expression],
            estimated_value: t.Optional[enodes.Expression] = None
    ) -> None:
        self.space[self.nesting_level][name.member] = entries.ConstantEntry(
            line, name, type_, has_value=value is not None, estimated_value=estimated_value
        )

    def add_variable(
            self, line: int, name: nodes.Name, type_: nodes.Type, value: t.Optional[nodes.Expression],
            estimated_value: t.Optional[enodes.Expression] = None
    ) -> None:
        self.space[self.nesting_level][name.member] = entries.VariableEntry(
            line, name, type_, value, estimated_value=estimated_value
        )

    def add_arguments(self, line: int, args: t.List[nodes.Argument]) -> None:
        for arg in args:
            value = enodes.DynamicValue(arg.type)
            self.space[self.nesting_level][arg.name.member] = entries.ConstantEntry(
                line, arg.name, arg.type, has_value=True, estimated_value=value
            )

    def add_function(
            self, line: int, name: nodes.Name, args: t.List[nodes.Argument], return_type: nodes.Type
    ) -> None:
        self.space[self.nesting_level][name.member] = entries.FunctionEntry(
            line, name, args, return_type, body=[]
        )

    def add_method(
            self, line: int, name: nodes.Name, args: t.List[nodes.Argument], return_type: nodes.Type
    ) -> None:
        entry = self._get_parent_struct_entry()
        entry.methods[name.member] = entries.FunctionEntry(line, name, args, return_type, body=[])

    def add_field(self, line: int, name: nodes.Name, type_: nodes.Type) -> None:
        entry = self._get_parent_struct_entry()
        entry.fields[name.member] = entries.VariableEntry(line, name, type_, value=None)

    def add_self(self, line: int, is_variable: bool = False) -> None:
        type_ = self._build_parent_struct_type()
        if is_variable:
            func = self.add_variable
        else:
            func = self.add_constant
        func(line, nodes.Name(nodes.SpecialName.self.value), type_, value=None)

    def add_init_declaration(self, line: int, args: nodes.Arguments) -> None:
        entry = self._get_parent_struct_entry()
        entry.init_declarations[','.join(arg.to_code() for arg in args)] = entries.InitEntry(line, args, body=[])

    def _get_parent_struct_entry(self) -> entries.StructEntry:
        assert self.parents
        entry = self[self.parents[0].member]
        for parent in self.parents[1:]:
            if isinstance(entry, entries.AlgebraicEntry):
                entry = entry.constructors[parent.member]
            else:
                assert 0, "Non-supported struct nesting"
        assert isinstance(entry, entries.StructEntry)
        return entry

    def _build_parent_struct_type(self) -> nodes.Type:
        assert self.parents
        type_: nodes.Type = self.parents[-1]
        for parent in reversed(self.parents[:-1]):
            # TODO: add proper params and constructor_types
            assert isinstance(type_, nodes.Name)
            type_ = nodes.AlgebraicType(parent, [], type_)
        return type_

    def add_struct(self, line: int, name: nodes.Name, params: nodes.Parameters) -> None:
        if self.parents:
            self.add_algebraic_constructor(line, name, params)
        else:
            self.space[self.nesting_level][name.member] = entries.StructEntry(
                line, name, params, fields={}, init_declarations={}, methods={}
            )

    def add_algebraic_constructor(self, line: int, name: nodes.Name, params: nodes.Parameters) -> None:
        assert self.parents
        entry = self[self.parents[-1].member]
        assert isinstance(entry, entries.AlgebraicEntry)
        entry.constructors[name.member] = entries.StructEntry(
            line, name, params, fields={}, init_declarations={}, methods={}
        )

    def add_algebraic(self, line: int, name: nodes.Name, params: nodes.Parameters) -> None:
        self.space[self.nesting_level][name.member] = entries.AlgebraicEntry(
            line, name, params, constructors={}, methods={}
        )

    def add_parameters(self, line: int, parameters: nodes.Parameters) -> None:
        for parameter in parameters:
            self.space[self.nesting_level][parameter.member] = entries.ParameterEntry(line, parameter)

    def update_function_body(self, name: nodes.Name, body: nodes.AST) -> None:
        self.space[self.nesting_level][name.member].body = body

    def update_method_body(self, name: nodes.Name, body: nodes.AST) -> None:
        entry = self._get_parent_struct_entry()
        entry.methods[name.member].body = body

    def update_init_declaration_body(self, args: nodes.Arguments, body: nodes.AST) -> None:
        entry = self._get_parent_struct_entry()
        entry.init_declarations[','.join(arg.to_code() for arg in args)].body = body

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
