from functools import partial

from . import estimation_nodes as enodes, nodes
from .estimation import Evaluator


def print_repl(value: enodes.Expression) -> enodes.Void:
    if isinstance(value, (enodes.String, enodes.Char)):
        print(value.value)
    else:
        print(value.to_code())
    return enodes.Void()


def read_repl(prompt: enodes.String) -> enodes.String:
    return enodes.String(input(prompt.value))


REPLEvaluator = partial(Evaluator, {
    nodes.BuiltinFunc.print.value: enodes.Function(
        [nodes.Argument("value", nodes.BuiltinType.convertible_to_string)], nodes.BuiltinType.void,
        specification=print_repl
    ),
    nodes.BuiltinFunc.read.value: enodes.Function(
        [nodes.Argument("prompt", nodes.BuiltinType.string)], nodes.BuiltinType.string, specification=read_repl
    )
})
