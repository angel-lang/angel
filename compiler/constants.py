from . import nodes, estimation_nodes as enodes


builtin_funcs = {
    nodes.BuiltinFunc.print.value: enodes.Function(
        [nodes.Argument("value", nodes.BuiltinType.convertible_to_string)], nodes.BuiltinType.void,
        specification=lambda value: enodes.Void()
    ),
    nodes.BuiltinFunc.read.value: enodes.Function(
        [nodes.Argument("prompt", nodes.BuiltinType.string)], nodes.BuiltinType.string,
        specification=lambda prompt: enodes.DynamicValue(nodes.BuiltinType.string)
    )
}


def string_split(s: enodes.Expression, by: enodes.Expression) -> enodes.Expression:
    if isinstance(s, enodes.String) and isinstance(by, enodes.Char):
        return enodes.Vector([enodes.String(string) for string in s.value.split(by.value)], nodes.BuiltinType.string)
    else:
        assert 0, f"Cannot estimate String.split for self='{s}' and by='{by}'"


def string_length(s: enodes.Expression) -> enodes.Expression:
    if isinstance(s, enodes.String):
        return enodes.Int(len(s.value), nodes.BuiltinType.u64)
    else:
        assert 0, f"Cannot estimate String.length for self='{s}'"


def vector_length(v: enodes.Expression) -> enodes.Expression:
    if isinstance(v, enodes.Vector):
        return enodes.Int(len(v.elements), nodes.BuiltinType.u64)
    else:
        assert 0, f"Cannot estimate Vector.length for self='{v}'"


def dict_length(d: enodes.Expression) -> enodes.Expression:
    if isinstance(d, enodes.Dict):
        return enodes.Int(len(d.keys), nodes.BuiltinType.u64)
    else:
        assert 0, f"Cannot estimate Dict.length for self='{d}'"


string_fields = {
    nodes.StringFields.split.value: enodes.Function(
        [nodes.Argument("by", nodes.BuiltinType.char)], nodes.VectorType(nodes.BuiltinType.string),
        specification=string_split
    ),
    nodes.StringFields.length.value: string_length,
}

vector_fields = {
    nodes.VectorFields.length.value: vector_length,
}

dict_fields = {
    nodes.DictFields.length.value: dict_length,
}
