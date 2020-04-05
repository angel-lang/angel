import typing as t

from . import errors, nodes


def dispatch(dispatcher, key, *args):
    func = dispatcher.get(key)
    if func is None:
        raise errors.AngelNotImplemented(f'cannot dispatch {key}')
    return func(*args)


def get_all_subclasses(cls):
    result = set()
    for subclass in cls.__subclasses__():
        subclass_subclasses = get_all_subclasses(subclass)
        if subclass_subclasses:
            # Don't add subclass that has subclasses.
            result = result.union(subclass_subclasses)
        else:
            result.add(subclass.__name__)
    return result


NODES = get_all_subclasses(nodes.Node)
EXPRS = get_all_subclasses(nodes.Expression)
TYPES = get_all_subclasses(nodes.Type)
ASSIGNMENTS = get_all_subclasses(nodes.AssignmentLeft)


apply_mapping_dispatcher = {
    nodes.Name: lambda name, mapping: mapping.get(name.member, name),
    nodes.FunctionType: lambda func, mapping: nodes.FunctionType(
        [nodes.Argument(arg.name, apply_mapping(arg.type, mapping), arg.value) for arg in func.args],
        apply_mapping(func.return_type, mapping)
    ),
    nodes.BuiltinType: lambda builtin, mapping: builtin,
    nodes.TemplateType: lambda template, mapping: template,
    nodes.StructType: lambda struct, mapping: nodes.StructType(
        struct.name, [apply_mapping(param, mapping) for param in struct.params]
    ),
    nodes.AlgebraicType: lambda algebraic, mapping: nodes.AlgebraicType(
        algebraic.name, [apply_mapping(param, mapping) for param in algebraic.params], algebraic.constructor_types
    ),
    nodes.GenericType: lambda generic, mapping: nodes.GenericType(
        generic.name, [apply_mapping(param, mapping) for param in generic.params]
    ),
    nodes.AlgebraicConstructor: lambda algebraic, mapping: nodes.AlgebraicConstructor(
        t.cast(nodes.Name, apply_mapping(algebraic.algebraic, mapping)), apply_mapping(algebraic.constructor, mapping)
    ),
    nodes.DictType: lambda dict_type, mapping: nodes.DictType(
        apply_mapping(dict_type.key_type, mapping), apply_mapping(dict_type.value_type, mapping)
    ),
    nodes.VectorType: lambda vector_type, mapping: nodes.VectorType(apply_mapping(vector_type.subtype, mapping)),
    nodes.OptionalType: lambda optional_type, mapping: nodes.OptionalType(
        apply_mapping(optional_type.inner_type, mapping)
    ),
}


def apply_mapping(raw: nodes.Type, mapping: t.Dict[str, nodes.Type]) -> nodes.Type:
    return dispatch(apply_mapping_dispatcher, type(raw), raw, mapping)
