from functools import partial

from . import estimation_nodes as enodes, nodes
from .estimation import Evaluator, EstimatedObjects


def print_repl(value: enodes.Expression) -> enodes.Void:
    if isinstance(value, (enodes.String, enodes.Char)):
        print(value.value)
    else:
        print(value.to_code())
    return enodes.Void()


def read_repl(prompt: enodes.String) -> enodes.String:
    return enodes.String(input(prompt.value))


builtin_funcs = {
    nodes.BuiltinFunc.print.value: enodes.Function(
        [nodes.Argument("value", nodes.BuiltinType.convertible_to_string)], nodes.BuiltinType.void,
        specification=print_repl
    ),
    nodes.BuiltinFunc.read.value: enodes.Function(
        [nodes.Argument("prompt", nodes.BuiltinType.string)], nodes.BuiltinType.string, specification=read_repl
    )
}


def string_split(s: enodes.String, by: enodes.Char) -> enodes.Vector:
    return enodes.Vector([enodes.String(string) for string in s.value.split(by.value)], nodes.BuiltinType.string)


string_fields = {
    nodes.StringFields.split.value: enodes.Function(
        [nodes.Argument("by", nodes.BuiltinType.char)], nodes.VectorType(nodes.BuiltinType.string),
        specification=string_split
    )
}

REPLEvaluator = partial(Evaluator, EstimatedObjects(builtin_funcs=builtin_funcs, string_fields=string_fields))
