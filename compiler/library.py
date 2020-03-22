import typing as t
from enum import Enum

from . import cpp_nodes, nodes


class StringFields(Enum):
    split_char = "__string_split_char"


class Builtins(Enum):
    read = "__read"
    print = "__print"

    @classmethod
    def from_builtin_func(cls, func: nodes.BuiltinFunc):
        dispatcher: t.Dict[str, Builtins] = {
            nodes.BuiltinFunc.print.value: Builtins.print,
            nodes.BuiltinFunc.read.value: Builtins.read,
        }
        return dispatcher[func.value]


class Modules(Enum):
    string = "angel_string"
    builtins = "angel_builtins"

    @property
    def header(self) -> str:
        return self.value + ".h"

    @property
    def includes(self) -> t.List[cpp_nodes.StdModule]:
        return {
            Modules.string.value: [
                cpp_nodes.StdModule.string,
                cpp_nodes.StdModule.vector,
            ],
            Modules.builtins.value: [
                cpp_nodes.StdModule.string,
                cpp_nodes.StdModule.iostream
            ],
        }[self.value]
