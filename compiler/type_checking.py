import typing as t
from decimal import Decimal
from itertools import zip_longest

from . import nodes, errors, environment, environment_entries as entries
from .utils import dispatch


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
    return get_possible_signed_int_types_based_on_value(value) + get_possible_unsigned_int_types_based_on_value(value)


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


class TypeChecker:

    def __init__(self):
        self.env: environment.Environment = environment.Environment()
        self.code: errors.Code = errors.Code("", 0)

        self.template_types = []
        self.template_type_id = -1

        self.type_inference_dispatcher = {
            nodes.Name: self.infer_type_from_name,
            nodes.BuiltinFunc: self.infer_type_from_builtin_func,
            nodes.BinaryExpression: self.infer_type_from_binary_expression,
            nodes.FunctionCall: self.infer_type_from_function_call,
            nodes.Cast: lambda value, supertype: self.unify_types(value.to_type, supertype),

            nodes.IntegerLiteral: self.infer_type_from_integer_literal,
            nodes.DecimalLiteral: self.infer_type_from_decimal_literal,
            nodes.StringLiteral: lambda _, supertype: self.unify_types(nodes.BuiltinType.string, supertype),
            nodes.VectorLiteral: self.infer_type_from_vector_literal,
            nodes.DictLiteral: self.infer_type_from_dict_literal,
            nodes.CharLiteral: lambda _, supertype: self.unify_types(nodes.BuiltinType.char, supertype),
            nodes.BoolLiteral: lambda _, supertype: self.unify_types(nodes.BuiltinType.bool, supertype),

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

            (nodes.BuiltinType, nodes.VectorType): self.unification_failed,
            (nodes.BuiltinType, nodes.DictType): self.unification_failed,
            (nodes.BuiltinType, nodes.OptionalType): self.unification_failed,
            (nodes.BuiltinType, nodes.TemplateType): self.unification_template_supertype_success,

            (nodes.VectorType, nodes.BuiltinType): lambda subtype, supertype: (
                supertype if supertype.value == nodes.BuiltinType.convertible_to_string.value
                else self.unification_failed(subtype, supertype)
            ),
            (nodes.VectorType, nodes.TemplateType): self.unification_template_supertype_success,
            (nodes.VectorType, nodes.DictType): self.unification_failed,
            (nodes.VectorType, nodes.OptionalType): self.unification_failed,

            (nodes.TemplateType, nodes.BuiltinType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.VectorType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.DictType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.OptionalType): self.unification_template_subtype_success,

            (nodes.DictType, nodes.BuiltinType): lambda subtype, supertype: (
                supertype if supertype.value == nodes.BuiltinType.convertible_to_string.value
                else self.unification_failed(subtype, supertype)
            ),
            (nodes.DictType, nodes.VectorType): self.unification_failed,
            (nodes.DictType, nodes.OptionalType): self.unification_failed,
            (nodes.DictType, nodes.TemplateType): self.unification_template_supertype_success,

            (nodes.OptionalType, nodes.BuiltinType): lambda subtype, supertype: (
                supertype if supertype.value == nodes.BuiltinType.convertible_to_string.value
                else self.unification_failed(subtype, supertype)
            ),
            (nodes.OptionalType, nodes.VectorType): self.unification_failed,
            (nodes.OptionalType, nodes.DictType): self.unification_failed,
            (nodes.OptionalType, nodes.TemplateType): self.unification_template_supertype_success,
        }

    def infer_type(self, value: nodes.Expression, supertype: t.Optional[nodes.Type] = None) -> nodes.Type:
        return dispatch(self.type_inference_dispatcher, type(value), value, supertype)

    def infer_type_from_name(self, name: nodes.Name, supertype: t.Optional[nodes.Type]) -> nodes.Type:
        if name.module:
            assert None, "Module system is not supported"
        entry = self.env[name.member]
        if entry is None:
            raise errors.AngelNameError(name, self.code)
        elif isinstance(entry, (entries.ConstantEntry, entries.VariableEntry)):
            return self.unify_types(entry.type, supertype)
        else:
            assert None, f"Type inference from name can't handle {type(entry)}"

    def infer_type_from_builtin_func(
            self, builtin_func: nodes.BuiltinFunc, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        return self.unify_types({
            nodes.BuiltinFunc.print.value: nodes.FunctionType(
                args=[nodes.Argument('value', nodes.BuiltinType.convertible_to_string)],
                return_type=nodes.BuiltinType.void
            ),
            nodes.BuiltinFunc.read.value: nodes.FunctionType(
                args=[nodes.Argument('prompt', nodes.BuiltinType.string)],
                return_type=nodes.BuiltinType.string
            ),
        }[builtin_func.value], supertype)

    def infer_type_from_function_call(self, call: nodes.FunctionCall, supertype: t.Optional[nodes.Type]) -> nodes.Type:
        function_type = self.infer_type(call.function_path)
        if not isinstance(function_type, nodes.FunctionType):
            raise errors.AngelNoncallableCall(call.function_path, self.code)
        for arg, value in zip_longest(function_type.args, call.args):
            if arg is None or value is None:
                raise errors.AngelWrongArguments(
                    f'({", ".join(arg.to_code() for arg in function_type.args)})', self.code,
                    call.args
                )
            self.infer_type(value, arg.type)
        return self.unify_types(function_type.return_type, supertype)

    def infer_type_from_integer_literal(
            self, value: nodes.IntegerLiteral, supertype: t.Optional[nodes.Type]) -> nodes.Type:
        possible_types = get_possible_int_types_based_on_value(int(value.value))
        try:
            result = self.unify_list_types(possible_types, supertype)
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
            return result

    def infer_type_from_decimal_literal(
            self, value: nodes.DecimalLiteral, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        possible_types = get_possible_float_types_base_on_value(value.value)
        try:
            result = self.unify_list_types(possible_types, supertype)
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
            return result

    def infer_type_from_vector_literal(
            self, value: nodes.VectorLiteral, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        element_type: nodes.Type = self.create_template_type()
        for element in value.elements:
            current_element_type = self.infer_type(element)
            try:
                element_type = self.unify_types(element_type, current_element_type)
            except errors.AngelTypeError:
                element_type = self.unify_types(current_element_type, element_type)
        return self.unify_types(nodes.VectorType(element_type), supertype)

    def infer_type_from_dict_literal(
            self, value: nodes.DictLiteral, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        key_type: nodes.Type = self.create_template_type()
        value_type: nodes.Type = self.create_template_type()
        for key, val in zip(value.keys, value.values):
            current_key_type = self.infer_type(key)
            try:
                key_type = self.unify_types(key_type, current_key_type)
            except errors.AngelTypeError:
                key_type = self.unify_types(current_key_type, key_type)

            current_value_type = self.infer_type(val)
            try:
                value_type = self.unify_types(value_type, current_value_type)
            except errors.AngelTypeError:
                value_type = self.unify_types(current_value_type, value_type)
        return self.unify_types(nodes.DictType(key_type, value_type), supertype)

    def infer_type_from_binary_expression(
            self, value: nodes.BinaryExpression, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        result_type = self.infer_type(value.right, self.infer_type(value.left))
        if value.operator.value in nodes.Operator.comparison_operators_names():
            return self.unify_types(nodes.BuiltinType.bool, supertype)
        return self.unify_types(result_type, supertype)

    def infer_type_from_read_function_call(
            self, _: t.List[nodes.Expression], supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        return self.unify_types(nodes.BuiltinType.string, supertype)

    def infer_type_from_optional_type_constructor(
            self, _: nodes.OptionalTypeConstructor, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        inner_type = self.create_template_type()
        return self.unify_types(nodes.OptionalType(inner_type), supertype)

    def infer_type_from_optional_some_call(
            self, value: nodes.OptionalSomeCall, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        inner_type = self.infer_type(value.value)
        return self.unify_types(nodes.OptionalType(inner_type), supertype)

    def infer_type_from_optional_some_value(
            self, value: nodes.OptionalSomeValue, _: t.Optional[nodes.Type]
    ) -> nodes.Type:
        optional_type = self.infer_type(value.value)
        assert isinstance(optional_type, nodes.OptionalType)
        # OptionalSomeValue is generated by compiler, so we assume that it is correct.
        return optional_type.inner_type

    def unify_types(self, subtype: nodes.Type, supertype: t.Optional[nodes.Type]) -> nodes.Type:
        if supertype is None:
            return subtype
        return dispatch(self.unification_dispatcher, (type(subtype), type(supertype)), subtype, supertype)

    def unify_builtin_types(self, subtype: nodes.BuiltinType, supertype: nodes.BuiltinType) -> nodes.Type:
        if supertype.value in subtype.get_builtin_supertypes():
            return supertype
        raise self.basic_type_error(subtype, supertype)

    def unify_builtin_type_with_template_type(
            self, subtype: nodes.BuiltinType, supertype: nodes.TemplateType
    ) -> nodes.Type:
        assert self.template_types[supertype.id] is None
        self.template_types[supertype.id] = subtype
        return subtype

    def unification_template_supertype_success(self, subtype: nodes.Type, supertype: nodes.TemplateType) -> nodes.Type:
        assert self.template_types[supertype.id] is None
        self.template_types[supertype.id] = subtype
        return subtype

    def unification_template_subtype_success(self, subtype: nodes.TemplateType, supertype: nodes.Type) -> nodes.Type:
        assert self.template_types[subtype.id] is None
        self.template_types[subtype.id] = supertype
        return supertype

    def unify_vector_types(self, subtype: nodes.VectorType, supertype: nodes.VectorType) -> nodes.Type:
        try:
            element_type = self.unify_types(subtype.subtype, supertype.subtype)
            return nodes.VectorType(element_type)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)

    def unify_optional_types(self, subtype: nodes.OptionalType, supertype: nodes.OptionalType) -> nodes.Type:
        try:
            inner_type = self.unify_types(subtype.inner_type, supertype.inner_type)
            return nodes.OptionalType(inner_type)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)

    def unify_dict_types(self, subtype: nodes.DictType, supertype: nodes.DictType) -> nodes.Type:
        try:
            key_type = self.unify_types(subtype.key_type, supertype.key_type)
            value_type = self.unify_types(subtype.value_type, supertype.value_type)
            return nodes.DictType(key_type, value_type)
        except errors.AngelTypeError:
            raise self.basic_type_error(subtype, supertype)

    def unification_failed(self, subtype: nodes.Type, supertype: nodes.Type) -> nodes.Type:
        raise self.basic_type_error(subtype, supertype)

    def unify_template_types(self, subtype: nodes.TemplateType, supertype: nodes.TemplateType) -> nodes.Type:
        real_type = self.template_types[subtype.id] or self.template_types[supertype.id]
        self.template_types[subtype.id] = real_type
        self.template_types[supertype.id] = real_type
        return real_type or subtype

    def unify_list_types(self, subtypes: t.Sequence[nodes.Type], supertype: t.Optional[nodes.Type]) -> nodes.Type:
        fail = None
        for subtype in subtypes:
            try:
                result = self.unify_types(subtype, supertype)
            except errors.AngelTypeError as e:
                fail = e
            else:
                return result
        if fail is not None:
            raise errors.AngelTypeError(fail.message, self.code, list(subtypes))
        raise errors.AngelTypeError("no subtypes to unify", self.code, list(subtypes))

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

    @property
    def supported_nodes_by_type_inference(self):
        return set(node_type.__name__ for node_type in self.type_inference_dispatcher.keys())
