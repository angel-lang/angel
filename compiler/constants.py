from . import nodes, estimation_nodes as enodes, environment_entries as entries


SELF_NAME = nodes.Name(nodes.SpecialName.self.value)

# Used for AST nodes created by compiler
SPEC_LINE = -1


builtin_funcs = {
    nodes.BuiltinFunc.print.value: enodes.Function(
        nodes.BuiltinFunc.print.value, [], [nodes.Argument('value', nodes.BuiltinType.convertible_to_string)],
        nodes.BuiltinType.void, [], specification=lambda value: enodes.Void()
    ),
    nodes.BuiltinFunc.read.value: enodes.Function(
        nodes.BuiltinFunc.read.value, [], [nodes.Argument('prompt', nodes.BuiltinType.string)],
        nodes.BuiltinType.string, [], specification=lambda prompt: enodes.DynamicValue(nodes.BuiltinType.string)
    )
}


private_builtin_funcs = {
    # TODO: replace specification for vector_to_string function: make return result much more specific
    nodes.PrivateBuiltinFunc.vector_to_string.value: enodes.Function(
        nodes.PrivateBuiltinFunc.vector_to_string.value, [],
        [nodes.Argument('value', nodes.VectorType(nodes.BuiltinType.convertible_to_string))],
        nodes.BuiltinType.string, [], specification=lambda value: enodes.DynamicValue(nodes.BuiltinType.string)
    )
}


builtin_interfaces = {
    nodes.BuiltinType.eq.value: entries.InterfaceEntry(
        line=0, name=nodes.Name(nodes.BuiltinType.eq.value),
        parameters=[], implemented_interfaces=[], fields={}, methods={
            nodes.SpecialMethods.eq.value: entries.FunctionEntry(
                line=0, name=nodes.Name(nodes.SpecialMethods.eq.value),
                parameters=[], arguments=[nodes.Argument('other', nodes.BuiltinType.self_)],
                return_type=nodes.BuiltinType.bool, body=[]
            )
        }, inherited_fields={}, inherited_methods={}
    ),

    nodes.BuiltinType.convertible_to_string.value: entries.InterfaceEntry(
        line=0, name=nodes.Name(nodes.BuiltinType.convertible_to_string.value),
        parameters=[], implemented_interfaces=[], fields={}, methods={
            nodes.SpecialMethods.as_.value: entries.FunctionEntry(
                line=0, name=nodes.Name(nodes.SpecialMethods.as_.value),
                parameters=[], arguments=[], return_type=nodes.BuiltinType.string, body=[]
            )
        }, inherited_fields={}, inherited_methods={}
    ),

    nodes.BuiltinType.object_.value: entries.InterfaceEntry(
        line=0, name=nodes.Name(nodes.BuiltinType.object_.value),
        parameters=[], implemented_interfaces=[], fields={}, methods={}, inherited_fields={}, inherited_methods={}
    ),

    nodes.BuiltinType.arithmetic_object.value: entries.InterfaceEntry(
        line=0, name=nodes.Name(nodes.BuiltinType.arithmetic_object.value),
        parameters=[], implemented_interfaces=[
            nodes.BuiltinType.addable, nodes.BuiltinType.subtractable, nodes.BuiltinType.multipliable,
            nodes.BuiltinType.divisible
        ], fields={}, methods={}, inherited_fields={}, inherited_methods={}
    ),

    nodes.BuiltinType.addable.value: entries.InterfaceEntry(
        line=0, name=nodes.Name(nodes.BuiltinType.addable.value),
        parameters=[], implemented_interfaces=[],
        fields={}, methods={
            nodes.SpecialMethods.add.value: entries.FunctionEntry(
                line=0, name=nodes.Name(nodes.SpecialMethods.add.value),
                parameters=[], arguments=[nodes.Argument('other', nodes.BuiltinType.self_)],
                return_type=nodes.BuiltinType.self_, body=[]
            )
        },
        inherited_fields={}, inherited_methods={}
    ),

    nodes.BuiltinType.subtractable.value: entries.InterfaceEntry(
        line=0, name=nodes.Name(nodes.BuiltinType.subtractable.value),
        parameters=[], implemented_interfaces=[],
        fields={}, methods={
            nodes.SpecialMethods.sub.value: entries.FunctionEntry(
                line=0, name=nodes.Name(nodes.SpecialMethods.sub.value),
                parameters=[], arguments=[nodes.Argument('other', nodes.BuiltinType.self_)],
                return_type=nodes.BuiltinType.self_, body=[]
            )
        },
        inherited_fields={}, inherited_methods={}
    ),

    nodes.BuiltinType.multipliable.value: entries.InterfaceEntry(
        line=0, name=nodes.Name(nodes.BuiltinType.multipliable.value),
        parameters=[], implemented_interfaces=[],
        fields={}, methods={
            nodes.SpecialMethods.mul.value: entries.FunctionEntry(
                line=0, name=nodes.Name(nodes.SpecialMethods.mul.value),
                parameters=[], arguments=[nodes.Argument('other', nodes.BuiltinType.self_)],
                return_type=nodes.BuiltinType.self_, body=[]
            )
        },
        inherited_fields={}, inherited_methods={}
    ),

    nodes.BuiltinType.divisible.value: entries.InterfaceEntry(
        line=0, name=nodes.Name(nodes.BuiltinType.divisible.value),
        parameters=[], implemented_interfaces=[],
        fields={}, methods={
            nodes.SpecialMethods.div.value: entries.FunctionEntry(
                line=0, name=nodes.Name(nodes.SpecialMethods.div.value),
                parameters=[], arguments=[nodes.Argument('other', nodes.BuiltinType.self_)],
                return_type=nodes.BuiltinType.self_, body=[]
            )
        },
        inherited_fields={}, inherited_methods={}
    )
}


# String
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


# Vector
def vector_length(v: enodes.Expression) -> enodes.Expression:
    if isinstance(v, enodes.Vector):
        return enodes.Int(len(v.elements), nodes.BuiltinType.u64)
    else:
        assert 0, f"Cannot estimate Vector.length for self='{v}'"


def vector_append(v: enodes.Expression) -> enodes.Function:
    assert isinstance(v, enodes.Vector)

    def func(s: enodes.Vector, element: enodes.Expression) -> enodes.Void:
        s.elements.append(element)
        return enodes.Void()

    # We don't need to pass an environment because `self` will be added when calling the method
    return enodes.Function(
        nodes.VectorFields.append.value, [], [nodes.Argument('element', v.element_type)], nodes.BuiltinType.void,
        [], specification=func
    )


def vector_pop(v: enodes.Expression) -> enodes.Function:
    assert isinstance(v, enodes.Vector)

    def func(s: enodes.Vector) -> enodes.Expression:
        return s.elements.pop()

    # We don't need to pass an environment because `self` will be added when calling the method
    return enodes.Function(
        nodes.VectorFields.pop.value, [], [], v.element_type, [], specification=func
    )


# Dict
def dict_length(d: enodes.Expression) -> enodes.Expression:
    if isinstance(d, enodes.Dict):
        return enodes.Int(len(d.keys), nodes.BuiltinType.u64)
    else:
        assert 0, f"Cannot estimate Dict.length for self='{d}'"


string_fields = {
    nodes.StringFields.split.value: enodes.Function(
        nodes.StringFields.split.value, [], [nodes.Argument('delimiter', nodes.BuiltinType.char)],
        nodes.VectorType(nodes.BuiltinType.string), [], specification=string_split
    ),
    nodes.StringFields.length.value: string_length,
}

vector_fields = {
    nodes.VectorFields.length.value: vector_length,
    nodes.VectorFields.pop.value: vector_pop,
    # TODO: consider returning Function object instead of a function
    nodes.VectorFields.append.value: vector_append,
}

dict_fields = {
    nodes.DictFields.length.value: dict_length,
}
