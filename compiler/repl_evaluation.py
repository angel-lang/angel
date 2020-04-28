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


def vector_to_string_repl(vector: enodes.Vector) -> enodes.String:
    elements = []
    for element in vector.elements:
        if isinstance(element, enodes.String):
            value = '"' + element.value + '"'
        elif isinstance(element, enodes.Int):
            value = str(element.value)
        elif isinstance(element, enodes.Vector):
            value = vector_to_string_repl(element).value
        else:
            raise NotImplementedError
        elements.append(value)
    return enodes.String(f"[{', '.join(elements)}]")


builtin_funcs = {
    nodes.BuiltinFunc.print.value: enodes.Function(
        [nodes.Argument("value", nodes.BuiltinType.convertible_to_string)], nodes.BuiltinType.void,
        specification=print_repl, name=nodes.BuiltinFunc.print.value
    ),
    nodes.BuiltinFunc.read.value: enodes.Function(
        [nodes.Argument("prompt", nodes.BuiltinType.string)], nodes.BuiltinType.string, specification=read_repl
    )
}


private_builtin_funcs = {
    nodes.PrivateBuiltinFunc.vector_to_string.value: enodes.Function(
        [nodes.Argument("value", nodes.VectorType(nodes.BuiltinType.object_))], nodes.BuiltinType.string,
        specification=vector_to_string_repl,
        name=nodes.PrivateBuiltinFunc.vector_to_string.value
    )
}


# String
def string_split(s: enodes.String, by: enodes.Char) -> enodes.Vector:
    return enodes.Vector([enodes.String(string) for string in s.value.split(by.value)], nodes.BuiltinType.string)


def string_length(s: enodes.String) -> enodes.Int:
    return enodes.Int(len(s.value), nodes.BuiltinType.u64)


# Vector
def vector_length(v: enodes.Vector) -> enodes.Int:
    return enodes.Int(len(v.elements), nodes.BuiltinType.u64)


def vector_append(v: enodes.Vector) -> enodes.Function:
    def func(s: enodes.Vector, element: enodes.Expression) -> enodes.Void:
        s.elements.append(element)
        return enodes.Void()

    return enodes.Function(
        args=[nodes.Argument("element", type_=v.element_type)], return_type=nodes.BuiltinType.void, specification=func
    )


# Dict
def dict_length(d: enodes.Dict) -> enodes.Int:
    return enodes.Int(len(d.keys), nodes.BuiltinType.u64)


string_fields = {
    nodes.StringFields.split.value: enodes.Function(
        [nodes.Argument("by", nodes.BuiltinType.char)], nodes.VectorType(nodes.BuiltinType.string),
        specification=string_split
    ),
    nodes.StringFields.length.value: string_length
}

vector_fields = {
    nodes.VectorFields.length.value: vector_length,
    nodes.VectorFields.append.value: vector_append,
}

dict_fields = {
    nodes.DictFields.length.value: dict_length
}

REPLEvaluator = partial(
    Evaluator,
    EstimatedObjects(
        builtin_funcs=builtin_funcs, private_builtin_funcs=private_builtin_funcs, string_fields=string_fields, vector_fields=vector_fields, dict_fields=dict_fields
    )
)
