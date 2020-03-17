import typing as t

from . import nodes, environment_entries as entries, estimation_nodes as enodes


class Environment:

    def __init__(self):
        self.space = [{}]
        self.nesting_level = 0
        self.parents: t.List[nodes.Name] = []

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

    def add_field(self, line: int, name: nodes.Name, type_: nodes.Type) -> None:
        assert self.parents
        entry = self.space[self.nesting_level][self.parents[-1].member]
        assert isinstance(entry, entries.StructEntry)
        entry.fields[name.member] = entries.VariableEntry(line, name, type_, value=None)

    def add_struct(self, line: int, name: nodes.Name) -> None:
        self.space[self.nesting_level][name.member] = entries.StructEntry(line, name, fields={}, methods={})

    def update_function_body(self, name: nodes.Name, body: nodes.AST) -> None:
        self.space[self.nesting_level][name.member].body = body

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
