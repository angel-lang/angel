import typing as t
import hashlib

from . import errors, nodes
from .context import Context


def dispatch(dispatcher, key, *arguments):
    func = dispatcher.get(key)
    if func is None:
        raise errors.AngelNotImplemented(f'cannot dispatch {key}')
    return func(*arguments)


def get_hash(string: str) -> str:
    md5 = hashlib.new('md5')
    md5.update(string.encode('utf-8'))
    return md5.hexdigest()[:6]


def mangle(name: nodes.Name, context: Context) -> nodes.Name:
    if name.module:
        raise NotImplementedError
    if context.mangle_names:
        return nodes.Name("_".join(["angel", context.main_hash, name.member]), unmangled=name.member)
    return name


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


apply_mapping_expression_dispatcher = {
    nodes.Name: lambda name, mapping: mapping.get(name.member, name),
    nodes.BuiltinType: lambda name, mapping: name,
    nodes.BuiltinFunc: lambda name, mapping: name,
    nodes.BinaryExpression: lambda expr, mapping: nodes.BinaryExpression(
        apply_mapping_expression(expr.left, mapping), expr.operator, apply_mapping_expression(expr.right, mapping)
    ),
}


apply_mapping_dispatcher = {
    nodes.Name: lambda name, mapping: mapping.get(name.member, name),
    nodes.FunctionType: lambda func, mapping: nodes.FunctionType(
        func.parameters, [nodes.Argument(arg.name, apply_mapping(arg.type, mapping), arg.value) for arg in func.arguments],
        apply_mapping(func.return_type, mapping), func.where_clauses, func.saved_environment, func.is_algebraic_method
    ),
    nodes.BuiltinType: lambda builtin, mapping: builtin,
    nodes.TemplateType: lambda template, mapping: template,
    nodes.StructType: lambda struct, mapping: nodes.StructType(
        struct.name, [apply_mapping(param, mapping) for param in struct.parameters]
    ),
    nodes.AlgebraicType: lambda algebraic, mapping: nodes.AlgebraicType(
        algebraic.base, [apply_mapping(param, mapping) for param in algebraic.parameters], algebraic.constructor,
        algebraic.constructor_types
    ),
    nodes.GenericType: lambda generic, mapping: nodes.GenericType(
        generic.name, [apply_mapping(param, mapping) for param in generic.parameters]
    ),
    nodes.DictType: lambda dict_type, mapping: nodes.DictType(
        apply_mapping(dict_type.key_type, mapping), apply_mapping(dict_type.value_type, mapping)
    ),
    nodes.VectorType: lambda vector_type, mapping: nodes.VectorType(apply_mapping(vector_type.subtype, mapping)),
    nodes.OptionalType: lambda optional_type, mapping: nodes.OptionalType(
        apply_mapping(optional_type.inner_type, mapping)
    ),
    nodes.RefType: lambda ref_type, mapping: nodes.RefType(apply_mapping(ref_type.value_type, mapping)),
}


def apply_mapping(raw: nodes.Type, mapping: t.Dict[str, nodes.Type]) -> nodes.Type:
    return dispatch(apply_mapping_dispatcher, type(raw), raw, mapping)


def apply_mapping_expression(raw: nodes.Expression, mapping: t.Dict[str, nodes.Type]) -> nodes.Expression:
    return dispatch(apply_mapping_expression_dispatcher, type(raw), raw, mapping)


def is_user_defined_type(typ: nodes.Type) -> bool:
    return isinstance(typ, nodes.Name) or (
        isinstance(typ, nodes.GenericType) and isinstance(typ.name, nodes.Name)
    )
