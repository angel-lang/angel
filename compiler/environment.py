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

    def inc_nesting(self) -> None:
        self.nesting_level += 1
        self.space.append({})

    def dec_nesting(self) -> None:
        del self.space[self.nesting_level]
        self.nesting_level -= 1
