import typing as t
import unittest
from copy import copy
from collections import namedtuple
from decimal import Decimal
from itertools import zip_longest

from . import nodes, errors, environment, environment_entries as entries, estimation_nodes as enodes
from .enums import DeclType
from .context import Context
from .constants import builtin_interfaces, SPEC_LINE
from .utils import submangle, dispatch, TYPES, EXPRS, apply_mapping, apply_mapping_expression, is_user_defined_type


Mapping = t.Dict[str, nodes.Type]
InferenceResult = namedtuple('InferenceResult', ['type', 'mapping'])
UnificationResult = namedtuple('UnificationResult', ['type', 'mapping'])


def to_inference_result(unification_result: UnificationResult) -> InferenceResult:
    return InferenceResult(unification_result.type, unification_result.mapping)


def build_instance_type(struct_type: nodes.StructType) -> nodes.Type:
    if struct_type.parameters:
        return nodes.GenericType(struct_type.name, struct_type.parameters)
    return struct_type.name


def get_possible_unsigned_int_types_based_on_value(value: int) -> t.List[nodes.Type]:
    if value < 0:
        return []
    elif value <= 255:
        return [nodes.BuiltinType.u8, nodes.BuiltinType.u16, nodes.BuiltinType.u32, nodes.BuiltinType.u64]
    elif value <= 65535:
        return [nodes.BuiltinType.u16, nodes.BuiltinType.u32, nodes.BuiltinType.u64]
    elif value <= 4294967295:
        return [nodes.BuiltinType.u32, nodes.BuiltinType.u64]
    elif value <= 18446744073709551615:
        return [nodes.BuiltinType.u64]
    return []


def get_possible_signed_int_types_based_on_value(value: int) -> t.List[nodes.Type]:
    if -128 <= value <= 127:
        return [nodes.BuiltinType.i8, nodes.BuiltinType.i16, nodes.BuiltinType.i32, nodes.BuiltinType.i64]
    elif -32768 <= value <= 32767:
        return [nodes.BuiltinType.i16, nodes.BuiltinType.i32, nodes.BuiltinType.i64]
    elif -2147483648 <= value <= 2147483647:
        return [nodes.BuiltinType.i32, nodes.BuiltinType.i64]
    elif -9223372036854775808 <= value <= 9223372036854775807:
        return [nodes.BuiltinType.i64]
    return []


def get_possible_int_types_based_on_value(value: int) -> t.List[nodes.Type]:
    base: t.List[nodes.Type] = [nodes.BuiltinType.int_]
    return (
        base
        + get_possible_signed_int_types_based_on_value(value)
        + get_possible_unsigned_int_types_based_on_value(value)
    )


MAX_FLOAT32 = Decimal('3.402823700000000000000000000E+38')
MIN_FLOAT32 = Decimal('1.17549400000000000000000000E-38')
MAX_FLOAT64 = Decimal('1.79769313486231570000000000E308')
MIN_FLOAT64 = Decimal('2.22507385850720140000000000E-308')


def get_possible_float_types_base_on_value(value: str) -> t.List[nodes.Type]:
    decimal = Decimal(value)
    if MIN_FLOAT32 <= decimal <= MAX_FLOAT32 or -MAX_FLOAT32 <= decimal <= -MIN_FLOAT32 or decimal == 0:
        return [nodes.BuiltinType.f32, nodes.BuiltinType.f64]
    elif MIN_FLOAT64 <= decimal <= MAX_FLOAT64 or -MAX_FLOAT64 <= decimal <= -MIN_FLOAT64:
        return [nodes.BuiltinType.f64]
    return []


class TypeChecker(unittest.TestCase):

    def __init__(self, context: Context):
        super().__init__()
        self.env: environment.Environment = environment.Environment()
        self.code: errors.Code = errors.Code("", 0)
        self.estimator: t.Optional[t.Any] = None
        self.context = context

        self.template_types: t.List[t.Optional[nodes.Type]] = []
        self.template_type_id = -1

        self.infer_type_from_field_of_builtin_type_dispatcher = {
            nodes.BuiltinType.string.value: lambda field, mapping, supertype: to_inference_result(
                self.unify_types(
                    nodes.StringFields(field.field.unmangled or field.field.member).as_type, supertype, mapping
                )
            )
        }

        self.infer_type_from_subscript_of_builtin_type_dispatcher = {
            nodes.BuiltinType.string.value: self.infer_type_from_string_builtin_type_subscript
        }

        self.infer_type_from_field_dispatcher = {
            nodes.BuiltinType: lambda base_type, field, mapping, supertype: dispatch(
                self.infer_type_from_field_of_builtin_type_dispatcher, base_type.value, field, mapping, supertype
            ),
            nodes.FunctionType: self.infer_field_of_function_type,
            nodes.Name: self.infer_field_of_name_type,
            nodes.TemplateType: self.infer_field_of_template_type,
            nodes.DictType: self.infer_field_of_dict_type,
            nodes.VectorType: self.infer_field_of_vector_type,
            nodes.OptionalType: self.infer_field_of_optional_type,
            nodes.StructType: self.infer_field_of_struct_type,
            nodes.GenericType: self.infer_field_of_generic_type,
            nodes.AlgebraicType: self.infer_field_of_algebraic_type,
            nodes.RefType: self.infer_field_of_ref_type,
        }

        self.infer_type_from_subscript_dispatcher = {
            nodes.BuiltinType: lambda base_type, subscript, mapping, supertype: dispatch(
                self.infer_type_from_subscript_of_builtin_type_dispatcher, base_type.value, subscript,
                mapping, supertype
            ),
            nodes.FunctionType: self.infer_subscript_of_function_type,
            nodes.Name: self.infer_subscript_of_name_type,
            nodes.TemplateType: self.infer_subscript_of_template_type,
            nodes.DictType: self.infer_subscript_of_dict_type,
            nodes.VectorType: self.infer_subscript_of_vector_type,
            nodes.OptionalType: self.infer_subscript_of_optional_type,
            nodes.StructType: self.infer_subscript_of_struct_type,
            nodes.GenericType: self.infer_subscript_of_generic_type,
            nodes.AlgebraicType: self.infer_subscript_of_algebraic_type,
            nodes.RefType: self.infer_subscript_of_ref_type,
        }

        self.type_inference_dispatcher = {
            nodes.Name: self.infer_type_from_name,
            nodes.SpecialName: self.infer_type_from_special_name,
            nodes.BuiltinFunc: self.infer_type_from_builtin_func,
            nodes.PrivateBuiltinFunc: self.infer_type_from_private_builtin_func,
            nodes.BinaryExpression: self.infer_type_from_binary_expression,
            nodes.FunctionCall: self.infer_type_from_function_call,
            nodes.MethodCall: self.infer_type_from_method_call,
            nodes.Field: self.infer_type_from_field,
            nodes.Subscript: self.infer_type_from_subscript,
            nodes.Cast: self.infer_type_from_cast,
            nodes.Decl: lambda value, supertype, mapping: self.infer_type(
                value.value, supertype, mapping
            ),
            nodes.Ref: self.infer_type_from_ref,
            nodes.Parentheses: lambda value, supertype, mapping: self.infer_type(
                value.value, supertype, mapping
            ),
            nodes.NamedArgument: lambda value, supertype, mapping: self.infer_type(
                value.value, supertype, mapping
            ),

            nodes.IntegerLiteral: self.infer_type_from_integer_literal,
            nodes.DecimalLiteral: self.infer_type_from_decimal_literal,
            nodes.StringLiteral: lambda _, supertype, mapping: to_inference_result(
                self.unify_types(nodes.BuiltinType.string, supertype, mapping)
            ),
            nodes.VectorLiteral: self.infer_type_from_vector_literal,
            nodes.DictLiteral: self.infer_type_from_dict_literal,
            nodes.CharLiteral: lambda _, supertype, mapping: to_inference_result(
                self.unify_types(nodes.BuiltinType.char, supertype, mapping)
            ),
            nodes.BoolLiteral: lambda _, supertype, mapping: to_inference_result(
                self.unify_types(nodes.BuiltinType.bool, supertype, mapping)
            ),

            nodes.OptionalTypeConstructor: self.infer_type_from_optional_type_constructor,
            nodes.OptionalSomeCall: self.infer_type_from_optional_some_call,
            nodes.OptionalSomeValue: self.infer_type_from_optional_some_value,
        }

        self.unification_dispatcher = {
            (nodes.BuiltinType, nodes.BuiltinType): self.unify_builtin_types,
            (nodes.VectorType, nodes.VectorType): self.unify_vector_types,
            (nodes.DictType, nodes.DictType): self.unify_dict_types,
            (nodes.TemplateType, nodes.TemplateType): self.unify_template_types,
            (nodes.OptionalType, nodes.OptionalType): self.unify_optional_types,
            (nodes.FunctionType, nodes.FunctionType): self.unify_function_types,
            (nodes.Name, nodes.Name): self.unify_name_types,
            (nodes.StructType, nodes.StructType): self.unify_struct_types,
            (nodes.GenericType, nodes.GenericType): self.unify_generic_types,
            (nodes.AlgebraicType, nodes.AlgebraicType): self.unify_algebraic_types,
            (nodes.RefType, nodes.RefType): self.unify_ref_types,

            (nodes.BuiltinType, nodes.VectorType): self.unification_failed,
            (nodes.BuiltinType, nodes.DictType): self.unification_failed,
            (nodes.BuiltinType, nodes.OptionalType): self.unification_failed,
            (nodes.BuiltinType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.BuiltinType, nodes.FunctionType): self.unification_failed,
            (nodes.BuiltinType, nodes.Name): self.unify_type_with_name,
            (nodes.BuiltinType, nodes.StructType): self.unification_failed,
            (nodes.BuiltinType, nodes.GenericType): self.unify_builtin_type_with_generic_type,
            (nodes.BuiltinType, nodes.AlgebraicType): self.unification_failed,
            (nodes.BuiltinType, nodes.RefType): self.unification_failed,

            (nodes.VectorType, nodes.BuiltinType): lambda subtype, supertype, mapping: (
                UnificationResult(supertype, mapping)
                if supertype.value == nodes.BuiltinType.convertible_to_string.value
                else self.unification_failed(subtype, supertype, mapping)
            ),
            (nodes.VectorType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.VectorType, nodes.DictType): self.unification_failed,
            (nodes.VectorType, nodes.OptionalType): self.unification_failed,
            (nodes.VectorType, nodes.FunctionType): self.unification_failed,
            (nodes.VectorType, nodes.Name): self.unify_type_with_name,
            (nodes.VectorType, nodes.StructType): self.unification_failed,
            (nodes.VectorType, nodes.GenericType): self.unify_vector_with_generic_type,
            (nodes.VectorType, nodes.AlgebraicType): self.unification_failed,
            (nodes.VectorType, nodes.RefType): self.unification_failed,

            (nodes.TemplateType, nodes.BuiltinType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.VectorType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.DictType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.OptionalType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.FunctionType): self.unification_template_subtype_success,
            # Maybe, we need to add Name: TemplateType to the mapping?
            (nodes.TemplateType, nodes.Name): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.StructType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.GenericType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.AlgebraicType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.RefType): self.unification_template_subtype_success,

            (nodes.DictType, nodes.BuiltinType): lambda subtype, supertype, mapping: (
                UnificationResult(supertype, mapping)
                if supertype.value == nodes.BuiltinType.convertible_to_string.value
                else self.unification_failed(subtype, supertype, mapping)
            ),
            (nodes.DictType, nodes.VectorType): self.unification_failed,
            (nodes.DictType, nodes.OptionalType): self.unification_failed,
            (nodes.DictType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.DictType, nodes.FunctionType): self.unification_failed,
            (nodes.DictType, nodes.Name): self.unify_type_with_name,
            (nodes.DictType, nodes.StructType): self.unification_failed,
            (nodes.DictType, nodes.GenericType): self.unification_failed,
            (nodes.DictType, nodes.AlgebraicType): self.unification_failed,
            (nodes.DictType, nodes.RefType): self.unification_failed,

            (nodes.OptionalType, nodes.BuiltinType): lambda subtype, supertype, mapping: (
                UnificationResult(supertype, mapping)
                if supertype.value == nodes.BuiltinType.convertible_to_string.value
                else self.unification_failed(subtype, supertype, mapping)
            ),
            (nodes.OptionalType, nodes.VectorType): self.unification_failed,
            (nodes.OptionalType, nodes.DictType): self.unification_failed,
            (nodes.OptionalType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.OptionalType, nodes.FunctionType): self.unification_failed,
            (nodes.OptionalType, nodes.Name): self.unify_type_with_name,
            (nodes.OptionalType, nodes.StructType): self.unification_failed,
            (nodes.OptionalType, nodes.GenericType): self.unification_failed,
            (nodes.OptionalType, nodes.AlgebraicType): self.unification_failed,
            (nodes.OptionalType, nodes.RefType): self.unification_failed,

            (nodes.FunctionType, nodes.BuiltinType): self.unification_failed,
            (nodes.FunctionType, nodes.VectorType): self.unification_failed,
            (nodes.FunctionType, nodes.DictType): self.unification_failed,
            (nodes.FunctionType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.FunctionType, nodes.OptionalType): self.unification_failed,
            (nodes.FunctionType, nodes.Name): self.unify_type_with_name,
            (nodes.FunctionType, nodes.StructType): self.unification_failed,
            (nodes.FunctionType, nodes.GenericType): self.unification_failed,
            (nodes.FunctionType, nodes.AlgebraicType): self.unification_failed,
            (nodes.FunctionType, nodes.RefType): self.unification_failed,

            (nodes.Name, nodes.BuiltinType): self.unify_name_with_builtin_type,
            (nodes.Name, nodes.VectorType): self.unification_failed,
            (nodes.Name, nodes.DictType): self.unification_failed,
            (nodes.Name, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.Name, nodes.OptionalType): self.unification_failed,
            (nodes.Name, nodes.FunctionType): self.unification_failed,
            (nodes.Name, nodes.StructType): self.unification_failed,
            (nodes.Name, nodes.GenericType): self.unification_failed,
            (nodes.Name, nodes.AlgebraicType): self.unification_failed,
            (nodes.Name, nodes.RefType): self.unification_failed,

            (nodes.StructType, nodes.BuiltinType): self.unification_failed,
            (nodes.StructType, nodes.VectorType): self.unification_failed,
            (nodes.StructType, nodes.DictType): self.unification_failed,
            (nodes.StructType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.StructType, nodes.OptionalType): self.unification_failed,
            (nodes.StructType, nodes.FunctionType): self.unification_failed,
            (nodes.StructType, nodes.GenericType): self.unification_failed,
            (nodes.StructType, nodes.Name): self.unify_type_with_name,
            (nodes.StructType, nodes.AlgebraicType): self.unification_failed,
            (nodes.StructType, nodes.RefType): self.unification_failed,

            (nodes.GenericType, nodes.BuiltinType): self.unify_generic_type_with_builtin_type,
            (nodes.GenericType, nodes.VectorType): self.unification_failed,
            (nodes.GenericType, nodes.DictType): self.unification_failed,
            (nodes.GenericType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.GenericType, nodes.OptionalType): self.unification_failed,
            (nodes.GenericType, nodes.FunctionType): self.unification_failed,
            (nodes.GenericType, nodes.StructType): self.unification_failed,
            (nodes.GenericType, nodes.Name): self.unify_type_with_name,
            (nodes.GenericType, nodes.AlgebraicType): self.unification_failed,
            (nodes.GenericType, nodes.RefType): self.unification_failed,

            (nodes.AlgebraicType, nodes.BuiltinType): self.unification_failed,
            (nodes.AlgebraicType, nodes.VectorType): self.unification_failed,
            (nodes.AlgebraicType, nodes.DictType): self.unification_failed,
            (nodes.AlgebraicType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.AlgebraicType, nodes.OptionalType): self.unification_failed,
            (nodes.AlgebraicType, nodes.FunctionType): self.unification_failed,
            (nodes.AlgebraicType, nodes.StructType): self.unification_failed,
            (nodes.AlgebraicType, nodes.Name): self.unify_algebraic_type_with_name,
            (nodes.AlgebraicType, nodes.GenericType): self.unification_failed,
            (nodes.AlgebraicType, nodes.RefType): self.unification_failed,

            (nodes.RefType, nodes.BuiltinType): lambda sub, sup, mapping: (
                UnificationResult(sup, mapping) if sup == nodes.BuiltinType.object_
                else self.unification_failed
            ),
            (nodes.RefType, nodes.VectorType): self.unification_failed,
            (nodes.RefType, nodes.DictType): self.unification_failed,
            (nodes.RefType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.RefType, nodes.OptionalType): self.unification_failed,
            (nodes.RefType, nodes.FunctionType): self.unification_failed,
            (nodes.RefType, nodes.StructType): self.unification_failed,
            (nodes.RefType, nodes.Name): self.unify_type_with_name,
            (nodes.RefType, nodes.GenericType): self.unification_failed,
            (nodes.RefType, nodes.AlgebraicType): self.unification_failed,
        }

        self.replace_template_types_dispatcher = {
            nodes.TemplateType: self.replace_template_types_template_type,
            nodes.Name: lambda name_type: name_type,
            nodes.BuiltinType: lambda builtin_type: builtin_type,
            nodes.FunctionType: lambda func_type: nodes.FunctionType(
                func_type.parameters,
                [nodes.Argument(arg.name, self.replace_template_types(arg.type), arg.value) for arg in func_type.arguments],
                self.replace_template_types(func_type.return_type),
                func_type.where_clauses, func_type.saved_environment, func_type.is_algebraic_method
            ),
            nodes.DictType: lambda dict_type: nodes.DictType(self.replace_template_types(dict_type.key_type),
                                                             self.replace_template_types(dict_type.value_type)),
            nodes.VectorType: lambda vector_type: nodes.VectorType(self.replace_template_types(vector_type.subtype)),
            nodes.OptionalType: lambda optional_type: nodes.OptionalType(
                self.replace_template_types(optional_type.inner_type)
            ),
            nodes.StructType: lambda struct_type: nodes.StructType(
                struct_type.name, [self.replace_template_types(param) for param in struct_type.parameters]
            ),
            nodes.AlgebraicType: lambda typ: nodes.AlgebraicType(
                typ.base, [self.replace_template_types(param) for param in typ.parameters],
                typ.constructor, typ.constructor_types
            ),
            nodes.GenericType: lambda generic_type: nodes.GenericType(
                generic_type.name, [self.replace_template_types(param) for param in generic_type.parameters]
            ),
            nodes.RefType: lambda ref_type: nodes.RefType(self.replace_template_types(ref_type.value_type))
        }

    def infer_type(
        self, value: nodes.Expression, supertype: t.Optional[nodes.Type] = None, mapping: t.Optional[Mapping] = None
    ) -> InferenceResult:
        self.context.template_types = self.template_types
        return dispatch(self.type_inference_dispatcher, type(value), value, supertype, mapping or {})

    def infer_type_from_name(
        self, name: nodes.Name, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        entry = self.env.get(name)
        if isinstance(entry, entries.DeclEntry):
            result = to_inference_result(self.unify_types(entry.type, supertype, mapping))
            name.type_annotation = result.type
            return result
        elif isinstance(entry, entries.FunctionEntry):
            return to_inference_result(self.unify_types(entry.to_function_type(), supertype, mapping))
        elif isinstance(entry, entries.StructEntry):
            parameters: t.List[nodes.Type] = [self.create_template_type() for _ in entry.parameters]
            return to_inference_result(self.unify_types(nodes.StructType(entry.name, parameters), supertype, mapping))
        elif isinstance(entry, entries.AlgebraicEntry):
            parameters = [self.create_template_type() for _ in entry.parameters]
            constructor_types = self.build_algebraic_constructor_types_dict(entry)
            return to_inference_result(
                self.unify_types(
                    nodes.AlgebraicType(entry.name, parameters, constructor=None, constructor_types=constructor_types),
                    supertype, mapping
                )
            )
        else:
            assert 0, f"Type inference from name can't handle {type(entry)}"

    def infer_type_from_special_name(
        self, special_name: nodes.SpecialName, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        return self.infer_type_from_name(nodes.Name(special_name.value), supertype, mapping)

    def infer_type_from_builtin_func(
        self, builtin_func: nodes.BuiltinFunc, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        return to_inference_result(self.unify_types({
            nodes.BuiltinFunc.print.value: nodes.FunctionType(
                [], arguments=[nodes.Argument('value', nodes.BuiltinType.convertible_to_string)],
                return_type=nodes.BuiltinType.void
            ),
            nodes.BuiltinFunc.read.value: nodes.FunctionType(
                [], arguments=[nodes.Argument('prompt', nodes.BuiltinType.string)],
                return_type=nodes.BuiltinType.string
            ),
        }[builtin_func.value], supertype, mapping))

    def infer_type_from_private_builtin_func(
        self, builtin_func: nodes.PrivateBuiltinFunc, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        return to_inference_result(self.unify_types({
            nodes.PrivateBuiltinFunc.vector_to_string.value: nodes.FunctionType(
                [], arguments=[nodes.Argument('value', nodes.VectorType(nodes.BuiltinType.object_))],
                return_type=nodes.BuiltinType.string
            )
        }[builtin_func.value], supertype, mapping))

    def infer_type_from_function_call(
        self, call: nodes.FunctionCall, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        function_result = self.infer_type(call.function_path)
        function_type = function_result.type
        if isinstance(function_type, nodes.StructType):
            if function_type.name.module:
                assert 0, "Module system is not supported"
            struct_entry = self.env[function_type.name.member]
            if struct_entry is None:
                raise errors.AngelNameError(function_type.name, self.code)
            assert isinstance(struct_entry, entries.StructEntry)
            result = self.match_init_declaration(
                function_type, list(struct_entry.init_declarations.values()), call.arguments, supertype, mapping
            )
            if isinstance(result.type, nodes.GenericType):
                call.instance_call_parameters = result.type.parameters
            return result
        elif isinstance(function_type, nodes.FunctionType):
            return self.match_with_function_type(function_type, call.arguments, supertype, mapping)
        raise errors.AngelNoncallableCall(call.function_path, self.code)

    def match_init_declaration(
        self, struct_type: nodes.StructType, init_declarations: t.List[entries.InitEntry],
        arguments: t.List[nodes.Expression], supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        matched = True
        expected_major = []
        struct_mapping = self.basic_struct_mapping(struct_type)
        for init_entry in init_declarations:
            for arg, value in zip_longest(init_entry.arguments, arguments):
                if arg is None:
                    matched = False
                    break
                arg_type = apply_mapping(arg.type, struct_mapping)
                if value is None:
                    value = arg.value
                    if value is None:
                        matched = False
                        break
                try:
                    result = self.infer_type(value, arg_type, mapping)
                    mapping = result.mapping
                except errors.AngelTypeError:
                    matched = False
                    break
            if not matched:
                matched = True
                expected_major.append([arg.type for arg in init_entry.arguments])
                continue
            return to_inference_result(
                self.unify_types(apply_mapping(build_instance_type(struct_type), mapping), supertype, mapping)
            )
        expected = " or ".join(
            ("(" + ", ".join(type_.to_code() for type_ in type_list) + ")" for type_list in expected_major)
        )
        raise errors.AngelWrongArguments(expected, self.code, arguments)

    def match_with_function_type(
        self, function_type: nodes.FunctionType, arguments: t.List[nodes.Expression],
        supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        """
        1. Create template types from parameters. In checks it will be replaced by regular types.
        2. Passed argument's type is subtype of declared argument's type (e.g. I8 is ConvertibleToString).
        3. Check satisfaction of `where` clauses.
        """
        for param in function_type.parameters:
            mapping[param.member] = self.create_template_type()
        for arg, value in zip_longest(function_type.arguments, arguments):
            if arg is None or value is None:
                raise errors.AngelWrongArguments(
                    f'({", ".join(arg.to_code() for arg in function_type.arguments)})', self.code, arguments
                )
            self.infer_type(value, arg.type, mapping)

        # TODO: add `self` to the environment
        estimated_arguments = [self.estimate_expression(argument) for argument in arguments]
        environment_backup = copy(self.env)
        self.env = environment.Environment(function_type.saved_environment)
        self.env.add_parameters(SPEC_LINE, function_type.parameters)

        for argument, expression, estimated in zip_longest(function_type.arguments, arguments, estimated_arguments):
            self.env.add_declaration(
                nodes.Decl(SPEC_LINE, DeclType.constant, argument.name, argument.type, expression),
                estimated_value=estimated
            )

        # TODO: Maybe we need to apply mapping only to the last where clause
        new_mapping = {}
        for k, v in mapping.items():
            new_mapping[k] = self.replace_template_types(v)
        mapping = new_mapping
        for clause in [apply_mapping_expression(clause, mapping) for clause in function_type.where_clauses]:
            estimated_clause = self.estimate_expression(clause)
            if not isinstance(estimated_clause, enodes.Bool) or not estimated_clause.value:
                raise errors.AngelUnsatisfiedWhereClause(clause, self.code)

        self.env = environment_backup
        return to_inference_result(self.unify_types(function_type.return_type, supertype, mapping))

    def basic_struct_mapping(self, struct_type: t.Union[nodes.GenericType, nodes.StructType]) -> Mapping:
        """Map struct parameter names to passed parameters.

        Example:
        struct A(B, C)

        let a: A(I8, I64)

        result will be {'B': I8, 'C': I64}
        """
        if not struct_type.parameters:
            return {}
        if isinstance(struct_type.name, nodes.BuiltinType):
            return {}
        entry = self.env.get(struct_type.name)
        assert isinstance(entry, entries.StructEntry)
        mapping = {}
        for param, type_ in zip(entry.parameters, struct_type.parameters):
            mapping[param.member] = type_
        return mapping

    def infer_type_from_method_call(
        self, call: nodes.MethodCall, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        method_result = self.infer_type_from_field(
            nodes.Field(call.line, call.instance_path, call.method), supertype=None, mapping=mapping
        )
        if isinstance(method_result.type, nodes.FunctionType):
            instance_result = self.infer_type(call.instance_path, mapping=mapping)
            call.instance_type = instance_result.type
            call.is_algebraic_method = method_result.type.is_algebraic_method
            return self.match_with_function_type(method_result.type, call.arguments, supertype, mapping)
        elif isinstance(method_result.type, nodes.AlgebraicType) and method_result.type.constructor:
            instance_result = self.infer_type(call.instance_path, mapping=mapping)
            call.instance_type = instance_result.type
            return to_inference_result(self.unify_types(method_result.type, supertype, mapping))
        else:
            assert 0, f"Cannot infer type from method call with type {method_result.type}"

    def infer_type_from_field(
        self, field: nodes.Field, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        base_result = self.infer_type(field.base)
        field.base_type = base_result.type
        return dispatch(
            self.infer_type_from_field_dispatcher, type(field.base_type), field.base_type, field, mapping, supertype
        )

    def infer_type_from_cast(
        self, cast: nodes.Cast, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        value_result = self.infer_type(cast.value)
        if isinstance(cast.to_type, nodes.BuiltinType):
            self.unify_types(value_result.type, cast.to_type.as_convertible_interface, mapping)
            cast.is_builtin = isinstance(value_result.type, nodes.BuiltinType)
            return to_inference_result(self.unify_types(cast.to_type, supertype, mapping))
        elif isinstance(cast.to_type, nodes.Name) and isinstance(value_result.type, nodes.Name):
            # TODO: it supports only a cast to itself
            self.unify_types(value_result.type, cast.to_type, mapping)
            cast.is_builtin = False
            return to_inference_result(self.unify_types(cast.to_type, supertype, mapping))
        raise NotImplementedError

    def infer_type_from_ref(
        self, ref: nodes.Ref, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        value_result = self.infer_type(ref.value, mapping=mapping)
        ref.value_type = value_result.type
        return to_inference_result(
            self.unify_types(nodes.RefType(value_result.type), supertype, value_result.mapping)
        )

    def infer_type_from_subscript(
        self, subscript: nodes.Subscript, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        base_result = self.infer_type(subscript.base)
        subscript.base_type = base_result.type
        return dispatch(
            self.infer_type_from_subscript_dispatcher, type(subscript.base_type), subscript.base_type, subscript,
            mapping, supertype
        )

    def infer_field_of_function_type(
        self, base_type: nodes.FunctionType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelFieldError(field.base, base_type, field.field.member, self.code)

    def infer_field_of_struct_type(
        self, base_type: nodes.StructType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        # Only instance fields are supported.
        raise errors.AngelFieldError(field.base, base_type, field.field.member, self.code)

    def infer_field_of_generic_type(
        self, base_type: nodes.GenericType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        struct_mapping = self.basic_struct_mapping(base_type)
        struct_mapping.update(mapping)
        if isinstance(base_type.name, nodes.Name):
            return self.infer_field_of_name_type(base_type.name, field, struct_mapping, supertype)
        raise NotImplementedError

    def infer_field_of_ref_type(
        self, base_type: nodes.RefType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        assert field.field.to_code() == 'value'
        return to_inference_result(
            self.unify_types(base_type.value_type, supertype, mapping)
        )

    def infer_field_of_name_type(
        self, base_type: nodes.Name, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        if base_type.module:
            assert 0, f"Module system is not supported"
        entry = self.env[base_type.member]
        if entry is None:
            raise errors.AngelNameError(base_type, self.code)
        if isinstance(entry, entries.StructEntry):
            field_entry = entry.fields.get(field.field.member)
            if field_entry is None:
                method_entry = entry.methods.get(field.field.member)
                if method_entry is None:
                    raise errors.AngelFieldError(field.base, base_type, field.field.member, self.code)
                return to_inference_result(self.unify_types(method_entry.to_function_type(), supertype, mapping))
            elif isinstance(field_entry, entries.DeclEntry):
                return to_inference_result(self.unify_types(field_entry.type, supertype, mapping))
            else:
                assert 0, f"Cannot infer type from field with entry {field_entry}"
        else:
            raise errors.AngelFieldError(field.base, base_type, field.field.member, self.code)

    def infer_field_of_algebraic_type(
        self, base_type: nodes.AlgebraicType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        entry = self.env.get_algebraic(base_type)
        if isinstance(entry, entries.AlgebraicEntry):
            if field.field.member not in entry.constructors:
                raise errors.AngelConstructorError(base_type, field.field.member, self.code)

            return to_inference_result(
                self.unify_types(
                    nodes.AlgebraicType(
                        base_type.base, base_type.parameters, field.field, base_type.constructor_types
                    ), supertype, mapping
                )
            )

        field_entry = entry.fields.get(field.field.member)
        if field_entry is None:
            is_algebraic_method = False
            method_entry = entry.methods.get(field.field.member)
            if method_entry is None:
                algebraic_entry = self.env.get(base_type.base)
                assert isinstance(algebraic_entry, entries.AlgebraicEntry)
                method_entry = algebraic_entry.methods.get(field.field.member)
                if method_entry is None:
                    raise errors.AngelFieldError(field.base, base_type, field.field.member, self.code)
                is_algebraic_method = True
            func_type = method_entry.to_function_type()
            func_type.is_algebraic_method = is_algebraic_method
            return to_inference_result(self.unify_types(func_type, supertype, mapping))
        elif isinstance(field_entry, entries.DeclEntry):
            return to_inference_result(self.unify_types(field_entry.type, supertype, mapping))
        else:
            assert 0, f"Cannot infer type from field with entry {field_entry}"

    def infer_field_of_template_type(
        self, base_type: nodes.TemplateType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelFieldError(field.base, base_type, field.field.member, self.code)

    def infer_field_of_dict_type(
        self, base_type: nodes.DictType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        return to_inference_result(
            self.unify_types(
                nodes.DictFields(field.field.unmangled or field.field.member).as_type(
                    base_type.key_type, base_type.value_type
                ), supertype, mapping
            )
        )

    def infer_field_of_vector_type(
        self, base_type: nodes.VectorType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        return to_inference_result(
            self.unify_types(
                nodes.VectorFields(field.field.unmangled or field.field.member).as_type(base_type.subtype),
                supertype, mapping
            )
        )

    def infer_field_of_optional_type(
        self, base_type: nodes.OptionalType, field: nodes.Field, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelFieldError(field.base, base_type, field.field.member, self.code)

    def infer_subscript_of_algebraic_type(
        self, base_type: nodes.AlgebraicType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelSubscriptError(subscript.base, base_type, subscript.index, self.code)

    def infer_subscript_of_ref_type(
        self, base_type: nodes.RefType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelSubscriptError(subscript.base, base_type, subscript.index, self.code)

    def infer_subscript_of_function_type(
        self, base_type: nodes.FunctionType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelSubscriptError(subscript.base, base_type, subscript.index, self.code)

    def infer_subscript_of_struct_type(
        self, base_type: nodes.StructType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelSubscriptError(subscript.base, base_type, subscript.index, self.code)

    def infer_subscript_of_optional_type(
        self, base_type: nodes.OptionalType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelSubscriptError(subscript.base, base_type, subscript.index, self.code)

    def infer_subscript_of_vector_type(
        self, base_type: nodes.VectorType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        self.infer_type(subscript.index, nodes.BuiltinType.u64)
        return to_inference_result(self.unify_types(base_type.subtype, supertype, mapping))

    def infer_subscript_of_dict_type(
        self, base_type: nodes.DictType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        self.infer_type(subscript.index, base_type.key_type)
        return to_inference_result(self.unify_types(base_type.value_type, supertype, mapping))

    def infer_subscript_of_template_type(
        self, base_type: nodes.TemplateType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelSubscriptError(subscript.base, base_type, subscript.index, self.code)

    def infer_subscript_of_generic_type(
        self, base_type: nodes.GenericType, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelSubscriptError(subscript.base, base_type, subscript.index, self.code)

    def infer_type_from_string_builtin_type_subscript(
        self, subscript: nodes.Subscript, mapping: Mapping, supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        self.infer_type(subscript.index, nodes.BuiltinType.u64)
        return to_inference_result(self.unify_types(nodes.BuiltinType.char, supertype, mapping))

    def infer_subscript_of_name_type(
        self, base_type: nodes.Name, subscript: nodes.Subscript, mapping: Mapping,
        supertype: t.Optional[nodes.Type]
    ) -> InferenceResult:
        raise errors.AngelSubscriptError(subscript.base, base_type, subscript.index, self.code)

    def infer_type_from_integer_literal(
        self, value: nodes.IntegerLiteral, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        possible_types = get_possible_int_types_based_on_value(int(value.value))
        try:
            result = self.unify_list_types(possible_types, supertype, mapping)
        except errors.AngelTypeError:
            if supertype is None:
                if int(value.value) > 0:
                    message = f"{value.value} is too big"
                else:
                    message = f"{value.value} is too small"
            elif isinstance(supertype, nodes.BuiltinType) and supertype.is_finite_int_type:
                message = f"{value.value} is not in range {supertype.get_range()}"
            else:
                message = f"'{supertype.to_code()}' is not a possible type for {value.value}"
            raise errors.AngelTypeError(message, self.code, possible_types)
        else:
            value.type_annotation = result.type
            return to_inference_result(result)

    def infer_type_from_decimal_literal(
        self, value: nodes.DecimalLiteral, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        possible_types = get_possible_float_types_base_on_value(value.value)
        try:
            result = self.unify_list_types(possible_types, supertype, mapping)
        except errors.AngelTypeError:
            if supertype is None:
                if int(value.value) > 0:
                    message = f"{value.value} is too big"
                else:
                    message = f"{value.value} is too small"
            elif isinstance(supertype, nodes.BuiltinType) and supertype.is_finite_float_type:
                message = f"{value.value} is not in range {supertype.get_range()}"
            else:
                message = f"'{supertype.to_code()}' is not a possible type for {value.value}"
            raise errors.AngelTypeError(message, self.code, possible_types)
        else:
            return to_inference_result(result)

    def infer_type_from_vector_literal(
        self, value: nodes.VectorLiteral, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        element_result: UnificationResult = UnificationResult(self.create_template_type(), {})
        for element in value.elements:
            current_element_result = self.infer_type(element, mapping=mapping)
            try:
                element_result = self.unify_types(element_result.type, current_element_result.type, mapping)
            except errors.AngelTypeError:
                element_result = self.unify_types(current_element_result.type, element_result.type, mapping)

        subtype = nodes.VectorType(element_result.type)
        value.typ = subtype
        return to_inference_result(self.unify_types(subtype, supertype, mapping))

    def infer_type_from_dict_literal(
        self, value: nodes.DictLiteral, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        key_result: UnificationResult = UnificationResult(self.create_template_type(), {})
        value_result: UnificationResult = UnificationResult(self.create_template_type(), {})
        for key, val in zip(value.keys, value.values):
            current_key_result = self.infer_type(key, mapping=mapping)
            try:
                key_result = self.unify_types(key_result.type, current_key_result.type, mapping=mapping)
            except errors.AngelTypeError:
                key_result = self.unify_types(current_key_result.type, key_result.type, mapping=mapping)

            current_value_result = self.infer_type(val, mapping=mapping)
            try:
                value_result = self.unify_types(value_result.type, current_value_result.type, mapping=mapping)
            except errors.AngelTypeError:
                value_result = self.unify_types(current_value_result.type, value_result.type, mapping=mapping)
        value.annotation = nodes.DictType(key_result.type, value_result.type)
        return to_inference_result(
            self.unify_types(nodes.DictType(key_result.type, value_result.type), supertype, mapping)
        )

    def infer_type_from_binary_expression(
        self, value: nodes.BinaryExpression, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        if value.operator.value == nodes.Operator.is_.value:
            result = to_inference_result(self.unify_types(nodes.BuiltinType.bool, supertype, mapping))
            value.type_annotation = result.type
            return result
        left_result = self.infer_type(value.left, mapping=mapping)
        if value.operator.value in nodes.Operator.comparison_operators_names():
            if is_user_defined_type(left_result.type):
                left_type_entry = self.env.get_type(left_result.type)
                assert isinstance(left_type_entry, (entries.StructEntry, entries.ParameterEntry))
                method_name = submangle(
                    nodes.Name(nodes.SpecialMethods.from_operator(value.operator).value), self.context
                ).member
                method_entry = left_type_entry.methods.get(
                    method_name, left_type_entry.methods.get(
                        nodes.SpecialMethods.from_operator(value.operator).value
                    )
                )
                if method_entry is None:
                    raise errors.AngelFieldError(value.left, left_result.type, method_name, self.code)
                if isinstance(left_result.type, nodes.GenericType):
                    mapping = self.basic_struct_mapping(left_result.type)
                self.satisfy_where_clauses(method_entry.where_clauses, mapping)
                # TODO: design sandbox for type checking: Self can map to different types (nested)
                self.infer_type(value.right, supertype=None, mapping=left_result.mapping)
                result = to_inference_result(self.unify_types(nodes.BuiltinType.bool, supertype, mapping))
                value.type_annotation = result.type
                return result
            self.infer_type(value.right, left_result.type, mapping=mapping)
            result = to_inference_result(self.unify_types(nodes.BuiltinType.bool, supertype, mapping))
            value.type_annotation = result.type
            return result
        result = to_inference_result(
            self.unify_types(self.infer_type(value.right, left_result.type, mapping=mapping).type, supertype, mapping)
        )
        value.type_annotation = result.type
        return result

    def infer_type_from_read_function_call(
        self, _: t.List[nodes.Expression], supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        return to_inference_result(self.unify_types(nodes.BuiltinType.string, supertype, mapping))

    def infer_type_from_optional_type_constructor(
        self, _: nodes.OptionalTypeConstructor, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        inner_type = self.create_template_type()
        return to_inference_result(self.unify_types(nodes.OptionalType(inner_type), supertype, mapping))

    def infer_type_from_optional_some_call(
        self, value: nodes.OptionalSomeCall, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        inner_result = self.infer_type(value.value)
        return to_inference_result(self.unify_types(nodes.OptionalType(inner_result.type), supertype, mapping))

    def infer_type_from_optional_some_value(
        self, value: nodes.OptionalSomeValue, _: t.Optional[nodes.Type], mapping: Mapping
    ) -> InferenceResult:
        optional_result = self.infer_type(value.value, mapping=mapping)
        assert isinstance(optional_result.type, nodes.OptionalType)
        # OptionalSomeValue is generated by compiler, so we assume that it is correct.
        return InferenceResult(optional_result.type.inner_type, mapping)

    def unify_types(
        self, subtype: nodes.Type, supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> UnificationResult:
        subtype = apply_mapping(subtype, mapping)
        if supertype is None:
            if isinstance(subtype, nodes.Name):
                return UnificationResult(self.build_specific_name_type(subtype), mapping)
            return UnificationResult(self.replace_template_types(subtype), mapping)
        supertype = apply_mapping(supertype, mapping)
        result = dispatch(self.unification_dispatcher, (type(subtype), type(supertype)), subtype, supertype, mapping)
        return UnificationResult(self.replace_template_types(result.type), result.mapping)

    def build_specific_name_type(self, name: nodes.Name) -> nodes.Type:
        entry = self.env.get(name)
        if isinstance(entry, entries.AlgebraicEntry):
            return nodes.AlgebraicType(
                name, [], constructor=None, constructor_types=self.build_algebraic_constructor_types_dict(entry)
            )
        return name

    def build_algebraic_constructor_types_dict(self, entry: entries.AlgebraicEntry) -> t.Dict[str, nodes.Name]:
        constructor_types = {}
        for constructor_name, constructor_entry in entry.constructors.items():
            constructor_types[constructor_name] = constructor_entry.name
        return constructor_types

    def unify_builtin_types(
        self, subtype: nodes.BuiltinType, supertype: nodes.BuiltinType, mapping: Mapping
    ) -> UnificationResult:
        if supertype.value in subtype.get_builtin_supertypes():
            return UnificationResult(supertype, mapping)
        raise self.basic_type_error(subtype, supertype)

    def unify_builtin_type_with_generic_type(
        self, subtype: nodes.BuiltinType, supertype: nodes.GenericType, mapping: Mapping
    ) -> UnificationResult:
        if isinstance(supertype.name, nodes.BuiltinType) and supertype.name.value == nodes.BuiltinType.iterable.value:
            if subtype.value == nodes.BuiltinType.string.value:
                element_result = self.unify_types(nodes.BuiltinType.char, supertype.parameters[0], mapping)
                return UnificationResult(
                    nodes.GenericType(nodes.BuiltinType.iterable, [element_result.type]), element_result.mapping
                )
        return self.unification_failed(subtype, supertype, mapping)

    def unify_builtin_type_with_template_type(
        self, subtype: nodes.BuiltinType, supertype: nodes.TemplateType, mapping: Mapping
    ) -> UnificationResult:
        assert self.template_types[supertype.id] is None
        self.template_types[supertype.id] = subtype
        return UnificationResult(subtype, mapping)

    def unify_generic_type_with_builtin_type(
        self, subtype: nodes.GenericType, supertype: nodes.BuiltinType, mapping: Mapping
    ) -> UnificationResult:
        if supertype.value == nodes.BuiltinType.self_.value:
            assert self.env.parents
            parent = self.env.parents[-1]
            try:
                self.unify_types(subtype.name, parent, mapping)
            except errors.AngelTypeError:
                raise self.basic_type_error(subtype, supertype)
            else:
                return UnificationResult(subtype, mapping)
        elif supertype.value == nodes.BuiltinType.object_.value:
            return UnificationResult(supertype, mapping)
        else:
            raise self.basic_type_error(subtype, supertype)

    def unify_name_with_builtin_type(
        self, subtype: nodes.Name, supertype: nodes.BuiltinType, mapping: Mapping
    ) -> UnificationResult:
        if supertype.value == nodes.BuiltinType.self_.value:
            assert self.env.parents
            parent = self.env.parents[-1]
            return self.unify_types(subtype, parent, mapping)
        if not supertype.is_interface:
            return self.unification_failed(subtype, supertype, mapping)
        subtype_entry = self.env.get(subtype)
        if isinstance(subtype_entry, entries.StructEntry):
            subtype_implemented_interfaces = subtype_entry.implemented_interfaces
        else:
            assert isinstance(subtype_entry, entries.ParameterEntry)
            subtype_implemented_interfaces = subtype_entry.implemented_interfaces
        if not self.is_operator(subtype_implemented_interfaces, supertype):
            return self.unification_failed(subtype, supertype, mapping)
        return UnificationResult(supertype, mapping)

    def unification_template_supertype_success(
        self, subtype: nodes.Type, supertype: nodes.TemplateType, mapping: Mapping
    ) -> UnificationResult:
        template_type = self.template_types[supertype.id]
        if template_type is None:
            self.template_types[supertype.id] = subtype
            return UnificationResult(subtype, mapping)
        return self.unify_types(subtype, template_type, mapping)

    def unification_template_subtype_success(
        self, subtype: nodes.TemplateType, supertype: nodes.Type, mapping: Mapping
    ) -> UnificationResult:
        if self.template_types[subtype.id] is None:
            self.template_types[subtype.id] = supertype
            return UnificationResult(supertype, mapping)
        subt = self.template_types[subtype.id]
        assert subt
        return self.unify_types(subt, supertype, mapping)

    def unify_vector_with_generic_type(
        self, subtype: nodes.VectorType, supertype: nodes.GenericType, mapping: Mapping
    ) -> UnificationResult:
        if isinstance(supertype.name, nodes.Name) or supertype.name.value != nodes.BuiltinType.iterable.value:
            return self.unification_failed(subtype, supertype, mapping)
        element_result = self.unify_types(subtype.subtype, supertype.parameters[0], mapping)
        return UnificationResult(
            nodes.GenericType(nodes.BuiltinType.iterable, [element_result.type]), element_result.mapping
        )

    def unify_vector_types(
        self, subtype: nodes.VectorType, supertype: nodes.VectorType, mapping: Mapping
    ) -> UnificationResult:
        try:
            element_result = self.unify_types(subtype.subtype, supertype.subtype, mapping)
            return UnificationResult(nodes.VectorType(element_result.type), element_result.mapping)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)

    def unify_type_with_name(self, subtype: nodes.Type, supertype: nodes.Name, mapping: Mapping) -> UnificationResult:
        entry = self.entry_possible_param(supertype)
        if isinstance(entry, entries.ParameterEntry):
            found = mapping.get(supertype.member)
            if found:
                return self.unify_types(subtype, found, mapping)
            mapping[supertype.member] = subtype
            return UnificationResult(subtype, mapping)
        return self.unification_failed(subtype, supertype, mapping)

    def unify_algebraic_type_with_name(
        self, subtype: nodes.AlgebraicType, supertype: nodes.Name, mapping: Mapping
    ) -> UnificationResult:
        if subtype.base == supertype:
            return UnificationResult(subtype, mapping)
        return self.unify_type_with_name(subtype, supertype, mapping)

    def unify_optional_types(
        self, subtype: nodes.OptionalType, supertype: nodes.OptionalType, mapping: Mapping
    ) -> UnificationResult:
        try:
            inner_result = self.unify_types(subtype.inner_type, supertype.inner_type, mapping=mapping)
            return UnificationResult(nodes.OptionalType(inner_result.type), inner_result.mapping)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)

    def unify_function_types(
        self, subtype: nodes.FunctionType, supertype: nodes.FunctionType, mapping: Mapping
    ) -> UnificationResult:
        arguments = []
        # TODO: unify where clauses
        clauses = subtype.where_clauses
        for sub_argument, super_argument in zip_longest(subtype.arguments, supertype.arguments):
            try:
                argument_result = self.unify_types(sub_argument, super_argument, mapping)
            except errors.AngelTypeError:
                raise self.basic_type_error(subtype, supertype)
            else:
                mapping = argument_result.mapping
                arguments.append(nodes.Argument(sub_argument.name, argument_result.type))
        try:
            return_result = self.unify_types(subtype.return_type, supertype.return_type, mapping)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)
        else:
            return UnificationResult(
                nodes.FunctionType(
                    subtype.parameters, arguments, return_result.type, clauses, subtype.saved_environment,
                    is_algebraic_method=subtype.is_algebraic_method
                ),
                return_result.mapping
            )

    def unify_name_types(self, subtype: nodes.Name, supertype: nodes.Name, mapping: Mapping) -> UnificationResult:
        subtype_entry = self.entry_possible_param(subtype)
        supertype_entry = self.entry_possible_param(supertype)

        if isinstance(supertype_entry, entries.ParameterEntry) and (
                not isinstance(subtype_entry, entries.ParameterEntry)):
            found = mapping.get(supertype.member)
            if found:
                return self.unify_types(subtype, found, mapping)
            mapping[supertype.member] = subtype
            return UnificationResult(subtype, mapping)

        if subtype.module == supertype.module and subtype.member == supertype.member:
            return UnificationResult(supertype, mapping)
        raise self.basic_type_error(subtype, supertype)

    def unify_struct_types(
        self, subtype: nodes.StructType, supertype: nodes.StructType, mapping: Mapping
    ) -> UnificationResult:
        base_result = self.unify_types(subtype.name, supertype.name, mapping)
        mapping = base_result.mapping
        parameters = []
        for param1, param2 in zip(subtype.parameters, supertype.parameters):
            try:
                param_result = self.unify_types(param1, param2, mapping)
            except errors.AngelTypeError:
                raise self.basic_type_error(subtype, supertype)
            else:
                mapping = param_result.mapping
                parameters.append(param_result.type)
        return UnificationResult(nodes.StructType(base_result.type, parameters), mapping)

    def unify_generic_types(
        self, subtype: nodes.GenericType, supertype: nodes.GenericType, mapping: Mapping
    ) -> UnificationResult:
        base_result = self.unify_types(subtype.name, supertype.name, mapping)
        mapping = base_result.mapping
        parameters = []
        for param1, param2 in zip(subtype.parameters, supertype.parameters):
            try:
                param_result = self.unify_types(param1, param2, mapping)
            except errors.AngelTypeError:
                raise self.basic_type_error(subtype, supertype)
            else:
                mapping = param_result.mapping
                parameters.append(param_result.type)
        return UnificationResult(nodes.GenericType(base_result.type, parameters), mapping)

    def unify_ref_types(
        self, subtype: nodes.RefType, supertype: nodes.RefType, mapping: Mapping
    ) -> UnificationResult:
        try:
            value_result = self.unify_types(subtype.value_type, supertype.value_type, mapping)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)
        else:
            return UnificationResult(nodes.RefType(value_result.type), value_result.mapping)

    def unify_algebraic_types(
        self, subtype: nodes.AlgebraicType, supertype: nodes.AlgebraicType, mapping: Mapping
    ) -> UnificationResult:
        try:
            base_result = self.unify_types(subtype.base, supertype.base, mapping)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)
        else:
            mapping = base_result.mapping

        parameters = []
        for param1, param2 in zip(subtype.parameters, supertype.parameters):
            try:
                param_result = self.unify_types(param1, param2, mapping)
            except errors.AngelTypeError:
                raise self.basic_type_error(subtype, supertype)
            else:
                mapping = param_result.mapping
                parameters.append(param_result.type)

        return UnificationResult(
            nodes.AlgebraicType(base_result.type, parameters, subtype.constructor, supertype.constructor_types),
            mapping
        )

    def unify_dict_types(
        self, subtype: nodes.DictType, supertype: nodes.DictType, mapping: Mapping
    ) -> UnificationResult:
        try:
            key_result = self.unify_types(subtype.key_type, supertype.key_type, mapping=mapping)
            value_result = self.unify_types(subtype.value_type, supertype.value_type, mapping=key_result.mapping)
            return UnificationResult(nodes.DictType(key_result.type, value_result.type), value_result.mapping)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)

    def unification_failed(self, subtype: nodes.Type, supertype: nodes.Type, mapping: Mapping) -> UnificationResult:
        raise self.basic_type_error(subtype, supertype)

    def unify_template_types(
        self, subtype: nodes.TemplateType, supertype: nodes.TemplateType, mapping: Mapping
    ) -> UnificationResult:
        real_type = self.template_types[subtype.id] or self.template_types[supertype.id]
        self.template_types[subtype.id] = real_type
        self.template_types[supertype.id] = real_type
        return UnificationResult(real_type or subtype, mapping)

    def unify_list_types(
        self, subtypes: t.Sequence[nodes.Type], supertype: t.Optional[nodes.Type], mapping: Mapping
    ) -> UnificationResult:
        fail = None
        for subtype in subtypes:
            try:
                result = self.unify_types(subtype, supertype, mapping=mapping)
            except errors.AngelTypeError as e:
                fail = e
            else:
                return result
        if fail is not None:
            raise errors.AngelTypeError(fail.message, self.code, list(subtypes))
        raise errors.AngelTypeError("no subtypes to unify", self.code, list(subtypes))

    def is_operator(self, implemented_interfaces: nodes.Interfaces, interface: nodes.BuiltinType) -> bool:
        def get_interface(interface: nodes.BuiltinType) -> entries.InterfaceEntry:
            return builtin_interfaces[interface.value]

        for implemented_interface in implemented_interfaces:
            assert isinstance(implemented_interface, nodes.BuiltinType)
            if implemented_interface == interface:
                return True
            entry = get_interface(implemented_interface)
            if self.is_operator(entry.implemented_interfaces, interface):
                return True
        return False

    def basic_type_error(self, subtype: nodes.Type, supertype: nodes.Type) -> errors.AngelTypeError:
        return errors.AngelTypeError(
            f"{supertype.to_code()} is not a supertype of {subtype.to_code()}", self.code, [subtype]
        )

    def create_template_type(self) -> nodes.TemplateType:
        self.template_types.append(None)
        self.template_type_id += 1
        return nodes.TemplateType(self.template_type_id)

    def update_context(self, env: environment.Environment, code: errors.Code):
        self.env = env
        self.code = code
        self.env.update_code(code)

    def estimate_expression(self, expression: nodes.Expression) -> enodes.Expression:
        assert self.estimator
        self.estimator.update_context(self.env, self.code)
        return self.estimator.estimate_expression(expression)

    def entry_possible_param(self, name: nodes.Name) -> entries.Entry:
        result = self.env[name.member]
        if result is None:
            return entries.ParameterEntry(0, name, implemented_interfaces=[], fields={}, methods={})
        return result

    def replace_template_types(self, from_type: nodes.Type) -> nodes.Type:
        return dispatch(self.replace_template_types_dispatcher, type(from_type), from_type)

    def replace_template_types_template_type(self, template_type: nodes.TemplateType) -> nodes.Type:
        return self.template_types[template_type.id] or template_type

    def eval_is(self, subtype: nodes.Type, supertype: nodes.Type, mapping: Mapping) -> bool:
        try:
            self.unify_types(subtype, supertype, mapping)
        except errors.AngelTypeError:
            return False
        else:
            return True

    def eval_where_clause(self, clause: nodes.Expression, mapping: Mapping) -> bool:
        if isinstance(clause, nodes.BinaryExpression):
            if clause.operator == nodes.Operator.is_:
                assert isinstance(clause.left, nodes.Type)
                assert isinstance(clause.right, nodes.Type)
                left_type = apply_mapping(clause.left, mapping)
                right_type = apply_mapping(clause.right, mapping)
                return self.eval_is(left_type, right_type, mapping)
            else:
                assert 0, f"Cannot eval not 'is' expression"
        else:
            assert 0, f"Cannot eval where clause {clause}"

    def satisfy_where_clauses(self, where_clauses: t.List[nodes.Expression], mapping: Mapping):
        for condition in where_clauses:
            if isinstance(condition, nodes.BinaryExpression):
                if condition.operator == nodes.Operator.and_:
                    left = self.eval_where_clause(condition.left, mapping)
                    right = self.eval_where_clause(condition.right, mapping)
                    if not (left and right):
                        raise errors.AngelUnsatisfiedWhereClause(condition, self.code)
                else:
                    assert 0, f"Cannot satisfy where clause (binary expression) {condition.operator}"
            else:
                assert 0, f"Cannot satisfy where clause with {condition} clause"

    def test(self):
        self.assertEqual(EXPRS, set(subclass.__name__ for subclass in self.type_inference_dispatcher.keys()))
        type_pairs = set()
        for type1 in TYPES:
            for type2 in TYPES:
                type_pairs.add((type1, type2))
        self.assertEqual(
            type_pairs, set((type1.__name__, type2.__name__) for type1, type2 in self.unification_dispatcher.keys())
        )
        self.assertEqual(TYPES, set(subclass.__name__ for subclass in self.infer_type_from_field_dispatcher.keys()))
        self.assertEqual(TYPES, set(subclass.__name__ for subclass in self.infer_type_from_subscript_dispatcher.keys()))
        self.assertEqual(TYPES, set(subclass.__name__ for subclass in self.replace_template_types_dispatcher.keys()))
