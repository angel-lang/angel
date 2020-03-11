import typing as t

from . import nodes, environment_entries as entries


class Environment:

    def __init__(self):
        self.space = [{}]
        self.nesting_level = 0

    def __getitem__(self, key) -> t.Optional[entries.Entry]:
        nesting_level = self.nesting_level
        while nesting_level >= 0:
            entry = self.space[nesting_level].get(key)
            if entry is not None:
                return entry
            nesting_level -= 1
        return None

    def add_constant(
            self, line: int, name: nodes.Name, type_: nodes.Type, value: t.Optional[nodes.Expression],
            computed_value: t.Any = None
    ) -> None:
        self.space[self.nesting_level][name.member] = entries.ConstantEntry(
            line, name, type_, has_value=value is not None, computed_value=computed_value
        )

    def add_variable(
            self, line: int, name: nodes.Name, type_: nodes.Type, computed_value: t.Any = None
    ) -> None:
        self.space[self.nesting_level][name.member] = entries.VariableEntry(
            line, name, type_, computed_value=computed_value
        )

    def add_arguments(self, line: int, args: t.List[nodes.Argument]) -> None:
        for arg in args:
            self.space[self.nesting_level][arg.name.member] = entries.ConstantEntry(
                line, arg.name, arg.type, has_value=True, computed_value=nodes.DynValue(arg.type)
            )

    def add_function(
            self, line: int, name: nodes.Name, args: t.List[nodes.Argument], return_type: nodes.Type
    ) -> None:
        self.space[self.nesting_level][name.member] = entries.FunctionEntry(
            line, name, args, return_type, body=[]
        )

    def add_method(
            self, parent: nodes.Name, line: int, name: nodes.Name, args: t.List[nodes.Argument], return_type: nodes.Type
    ) -> None:
        entry = self.space[self.nesting_level][parent.member]
        assert isinstance(entry, entries.StructEntry)
        entry.methods[name.member] = entries.FunctionEntry(line, name, args, return_type, body=[])

    def add_field(self, parent: nodes.Name, line: int, name: nodes.Name, type_: nodes.Type) -> None:
        entry = self.space[self.nesting_level][parent.member]
        assert isinstance(entry, entries.StructEntry)
        entry.fields[name.member] = entries.VariableEntry(line, name, type_)

    def add_struct(self, line: int, name: nodes.Name) -> None:
        self.space[self.nesting_level][name.member] = entries.StructEntry(line, name, fields={}, methods={})

    def update_method_body(self, parent: nodes.Name, name: nodes.Name, body: nodes.AST) -> None:
        entry = self.space[self.nesting_level][parent.member]
        assert isinstance(entry, entries.StructEntry)
        entry.methods[name.member].body = body

    def update_function_body(self, name: nodes.Name, body: nodes.AST) -> None:
        self.space[self.nesting_level][name.member].body = body

    def inc_nesting(self) -> None:
        self.nesting_level += 1
        self.space.append({})

    def dec_nesting(self) -> None:
        del self.space[self.nesting_level]
        self.nesting_level -= 1
