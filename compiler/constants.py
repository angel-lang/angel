from . import nodes, estimation_nodes as enodes


builtin_funcs={
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


string_fields={
    nodes.StringFields.split.value: enodes.Function(
        [nodes.Argument("by", nodes.BuiltinType.char)], nodes.VectorType(nodes.BuiltinType.string),
        specification=string_split
    ),
    nodes.StringFields.length.value: string_length,
}
