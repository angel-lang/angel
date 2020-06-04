import typing as t
import unittest

from . import nodes, cpp_nodes, environment, library
from .utils import dispatch, TYPES, EXPRS, NODES
from .enums import DeclType
from .context import Context


BUILTIN_TYPE_TO_CPP_TYPE = {
    nodes.BuiltinType.i8.value: cpp_nodes.StdName.int_fast8_t,
    nodes.BuiltinType.i16.value: cpp_nodes.StdName.int_fast16_t,
    nodes.BuiltinType.i32.value: cpp_nodes.StdName.int_fast32_t,
    nodes.BuiltinType.i64.value: cpp_nodes.StdName.int_fast64_t,

    nodes.BuiltinType.u8.value: cpp_nodes.StdName.uint_fast8_t,
    nodes.BuiltinType.u16.value: cpp_nodes.StdName.uint_fast16_t,
    nodes.BuiltinType.u32.value: cpp_nodes.StdName.uint_fast32_t,
    nodes.BuiltinType.u64.value: cpp_nodes.StdName.uint_fast64_t,

    nodes.BuiltinType.f32.value: cpp_nodes.PrimitiveTypes.float,
    nodes.BuiltinType.f64.value: cpp_nodes.PrimitiveTypes.double,

    nodes.BuiltinType.string.value: cpp_nodes.StdName.string,
    nodes.BuiltinType.char.value: cpp_nodes.PrimitiveTypes.char,
    nodes.BuiltinType.bool.value: cpp_nodes.PrimitiveTypes.bool,
    nodes.BuiltinType.void.value: cpp_nodes.PrimitiveTypes.void,
}


SPECIAL_METHOD_TO_OPERATOR = {
    nodes.SpecialMethods.add.value: cpp_nodes.Operator.add.value,
    nodes.SpecialMethods.sub.value: cpp_nodes.Operator.sub.value,
    nodes.SpecialMethods.mul.value: cpp_nodes.Operator.mul.value,
    nodes.SpecialMethods.div.value: cpp_nodes.Operator.div.value,
    nodes.SpecialMethods.eq.value: cpp_nodes.Operator.eq_eq.value,
    nodes.SpecialMethods.lt.value: cpp_nodes.Operator.lt.value,
    nodes.SpecialMethods.gt.value: cpp_nodes.Operator.gt.value,
}


TMP_PREFIX = "__tmp_"


def algebraic_constructor_name(algebraic: nodes.Name, constructor: nodes.Name) -> str:
    return algebraic.member + "_a_" + constructor.member


def algebraic_method_name(algebraic: nodes.Name, method: nodes.Name) -> str:
    return algebraic.member + "_m_" + method.member


def has_default_constructor(init_declarations: t.List[nodes.InitDeclaration]) -> bool:
    for decl in init_declarations:
        if not decl.arguments:
            return True
    return False


class Translator(unittest.TestCase):
    top_nodes: cpp_nodes.AST
    top_nodes_end: cpp_nodes.AST
    main_function_body: cpp_nodes.AST
    nodes_buffer: cpp_nodes.AST
    includes: t.Dict[str, cpp_nodes.Include]

    def __init__(self, context: Context) -> None:
        super().__init__()
        self.env = environment.Environment()
        self.current_line = 1
        self.tmp_count = 0
        self.struct_name = ""

        self.context = context

        # Translation
        self.translate_builtin_function_dispatcher = {
            nodes.BuiltinFunc.print.value: self.translate_print_function_call,
            nodes.BuiltinFunc.read.value: self.translate_read_function_call,
        }

        self.builtin_type_method_call = {
            nodes.BuiltinType.string.value: self.translate_string_type_method_call
        }
        self.method_call_dispatcher = {
            nodes.BuiltinType: lambda method_call: dispatch(
                self.builtin_type_method_call, t.cast(nodes.BuiltinType, method_call.instance_type).value, method_call
            ),
            nodes.Name: self.translate_method_call_name,
            nodes.GenericType: self.translate_method_call_name,
            nodes.VectorType: self.translate_vector_type_method_call,
            nodes.DictType: lambda _: NotImplementedError,
            nodes.OptionalType: lambda _: NotImplementedError,
            nodes.FunctionType: lambda _: NotImplementedError,
            nodes.TemplateType: lambda _: NotImplementedError,
            nodes.StructType: lambda _: NotImplementedError,
            nodes.AlgebraicType: self.translate_algebraic_type_method_call,
            nodes.RefType: lambda _: NotImplementedError,
        }

        self.field_dispatcher = {
            nodes.Name: self.translate_name_type_field,
            nodes.BuiltinType: self.translate_builtin_type_field,
            nodes.VectorType: self.translate_vector_type_field,
            nodes.DictType: self.translate_dict_type_field,
            nodes.OptionalType: lambda _: NotImplementedError,
            nodes.FunctionType: lambda _: NotImplementedError,
            nodes.TemplateType: lambda _: NotImplementedError,
            nodes.StructType: lambda _: NotImplementedError,
            nodes.GenericType: self.translate_generic_type_field,
            nodes.AlgebraicType: self.translate_algebraic_type_field,
            nodes.RefType: self.translate_ref_field,
        }

        self.subscript_dispatcher = {
            nodes.Name: lambda _: NotImplementedError,
            nodes.BuiltinType: self.translate_builtin_type_subscript,
            nodes.VectorType: self.translate_collection_type_subscript,
            nodes.DictType: self.translate_collection_type_subscript,
            nodes.OptionalType: lambda _: NotImplementedError,
            nodes.FunctionType: lambda _: NotImplementedError,
            nodes.TemplateType: lambda _: NotImplementedError,
            nodes.StructType: lambda _: NotImplementedError,
            nodes.GenericType: lambda _: NotImplementedError,
            nodes.AlgebraicType: lambda _: NotImplementedError,
            nodes.RefType: lambda _: NotImplementedError,
        }

        self.node_dispatcher = {
            nodes.Decl: self.translate_declaration,
            nodes.FunctionDeclaration: self.translate_function_declaration,
            nodes.StructDeclaration: self.translate_struct_declaration,
            nodes.InterfaceDeclaration: self.translate_interface_declaration,
            nodes.AlgebraicDeclaration: self.translate_algebraic_declaration,
            nodes.FieldDeclaration: self.translate_field_declaration,
            nodes.MethodDeclaration: self.translate_method_declaration,
            nodes.InitDeclaration: self.translate_init_declaration,
            nodes.Assignment: self.translate_assignment,
            nodes.InitCall: lambda node: None,
            nodes.FunctionCall: lambda node: cpp_nodes.Semicolon(self.translate_function_call(node)),
            nodes.MethodCall: lambda node: cpp_nodes.Semicolon(self.translate_method_call(node)),
            nodes.While: self.translate_while_statement,
            nodes.For: self.translate_for_statement,
            nodes.If: self.translate_if_statement,
            nodes.Return: self.translate_return_statement,
            nodes.Break: lambda node: cpp_nodes.Break(),
        }

        self.expression_dispatcher = {
            nodes.IntegerLiteral: lambda value: cpp_nodes.IntegerLiteral(value.value),
            nodes.DecimalLiteral: lambda value: cpp_nodes.DecimalLiteral(value.value),
            nodes.StringLiteral: lambda value: cpp_nodes.StringLiteral(value.value),
            nodes.VectorLiteral: self.translate_vector_literal,
            nodes.OptionalTypeConstructor: self.translate_optional_type_constructor,
            nodes.OptionalSomeCall: self.translate_optional_some_call,
            nodes.OptionalSomeValue: self.translate_optional_some_value,
            nodes.DictLiteral: self.translate_dict_literal,
            nodes.CharLiteral: lambda value: cpp_nodes.CharLiteral(value.value),
            nodes.BoolLiteral: lambda value: cpp_nodes.BoolLiteral(value.value.lower()),
            nodes.BinaryExpression: self.translate_binary_expression,
            nodes.FunctionCall: self.translate_function_call,
            nodes.MethodCall: self.translate_method_call,
            nodes.Name: lambda value: cpp_nodes.Id(value.member),
            nodes.Cast: self.translate_cast,
            nodes.Ref: self.translate_ref,
            nodes.Parentheses: lambda value: cpp_nodes.Parentheses(self.translate_expression(value.value)),
            nodes.Field: self.translate_field,
            nodes.Subscript: self.translate_subscript,
            nodes.SpecialName: self.translate_special_name,
            nodes.BuiltinFunc: self.translate_builtin_func,
            nodes.PrivateBuiltinFunc: self.translate_private_builtin_func,
            nodes.Decl: self.translate_declaration,
            nodes.NamedArgument: self.translate_named_argument,
        }
        self.translate_expression: t.Callable[[nodes.Expression], cpp_nodes.Expression] = lambda value: \
            dispatch(self.expression_dispatcher, type(value), value)

        self.type_dispatcher: t.Dict[type, t.Callable] = {
            nodes.BuiltinType: self.translate_builtin_type,
            nodes.Name: self.translate_name_type,
            nodes.VectorType: self.translate_vector_type,
            nodes.OptionalType: self.translate_optional_type,
            nodes.DictType: self.translate_dict_type,
            nodes.TemplateType: self.translate_template_type,
            nodes.FunctionType: self.translate_function_type,
            nodes.StructType: self.translate_struct_type,
            nodes.GenericType: self.translate_generic_type,
            nodes.AlgebraicType: self.translate_algebraic_type,
            nodes.RefType: self.translate_ref_type,
        }
        self.translate_type: t.Callable[[nodes.Type], cpp_nodes.Type] = lambda type_: \
            dispatch(self.type_dispatcher, type(type_), type_)

    def translate_method_call(self, method_call: nodes.MethodCall) -> cpp_nodes.Expression:
        assert method_call.instance_type is not None
        return dispatch(self.method_call_dispatcher, type(method_call.instance_type), method_call)

    def translate_method_call_name(self, method_call: nodes.MethodCall) -> cpp_nodes.Expression:
        return cpp_nodes.MethodCall(
            self.translate_expression(method_call.instance_path), method_call.method.member,
            [self.translate_expression(arg) for arg in method_call.arguments]
        )

    def translate_vector_type_method_call(self, method_call: nodes.MethodCall) -> cpp_nodes.Expression:
        method = method_call.method.unmangled or method_call.method.member
        if method == nodes.VectorFields.append.value:
            self.add_include(cpp_nodes.StdModule.vector)
            arguments = [self.translate_expression(arg) for arg in method_call.arguments]
            return cpp_nodes.MethodCall(self.translate_expression(method_call.instance_path), "push_back", arguments)
        elif method == nodes.VectorFields.pop.value:
            self.add_include(cpp_nodes.StdModule.vector)
            return cpp_nodes.MethodCall(self.translate_expression(method_call.instance_path), "pop_back", [])
        else:
            assert 0, f"Cannot translate method '{method_call.method}' call on Vector type"

    def translate_algebraic_type_method_call(self, method_call: nodes.MethodCall) -> cpp_nodes.Expression:
        instance_type = method_call.instance_type
        assert isinstance(instance_type, nodes.AlgebraicType)
        if instance_type.constructor:
            if method_call.is_algebraic_method:
                base = self.translate_expression(method_call.instance_path)
                return cpp_nodes.FunctionCall(
                    cpp_nodes.Id(algebraic_method_name(instance_type.base, method_call.method)),
                    [base] + [self.translate_expression(arg) for arg in method_call.arguments]
                )
            base = cpp_nodes.FunctionCall(
                cpp_nodes.StdName.get, [self.translate_expression(method_call.instance_path)],
                parameters=[cpp_nodes.Id(algebraic_constructor_name(instance_type.base, instance_type.constructor))]
            )
            return cpp_nodes.MethodCall(
                base, method_call.method.member, [self.translate_expression(arg) for arg in method_call.arguments]
            )
        return cpp_nodes.FunctionCall(
            cpp_nodes.Id(algebraic_constructor_name(instance_type.base, method_call.method)),
            [self.translate_expression(arg) for arg in method_call.arguments]
        )

    def translate_string_type_method_call(self, method_call: nodes.MethodCall) -> cpp_nodes.Expression:
        method = method_call.method.unmangled or method_call.method.member
        if method == nodes.StringFields.split.value:
            self.add_include(cpp_nodes.StdModule.vector)
            self.add_include(cpp_nodes.StdModule.string)
            self.add_library_include(library.Modules.string)
            arguments = []
            for arg in method_call.arguments:
                translated_arg = self.translate_expression(arg)
                assert translated_arg is not None
                arguments.append(translated_arg)
            instance = self.translate_expression(method_call.instance_path)
            assert instance is not None
            return cpp_nodes.FunctionCall(cpp_nodes.Id(library.StringFields.split_char.value), [instance] + arguments)
        else:
            assert 0, f"Cannot translate method '{method_call.method}' call on String type"

    def translate_cast(self, value: nodes.Cast) -> cpp_nodes.Expression:
        to_type = self.translate_type(value.to_type)
        expr = self.translate_expression(value.value)
        if isinstance(to_type, cpp_nodes.StdName) and to_type.value == cpp_nodes.StdName.string.value:
            if value.is_builtin:
                return cpp_nodes.FunctionCall(cpp_nodes.StdName.to_string, [expr])
            return cpp_nodes.MethodCall(expr, 'toString', [])
        return cpp_nodes.Cast(expr, to_type)

    def translate_ref(self, ref: nodes.Ref) -> cpp_nodes.Expression:
        assert ref.value_type is not None
        _, id_ = self.create_tmp(
            self.translate_type(ref.value_type), value=self.translate_expression(ref.value)
        )
        return cpp_nodes.AddrExpression(id_)

    def translate_field(self, field: nodes.Field) -> cpp_nodes.Expression:
        assert field.base_type is not None
        return dispatch(self.field_dispatcher, type(field.base_type), field)

    def translate_subscript(self, subscript: nodes.Subscript) -> cpp_nodes.Expression:
        assert subscript.base_type is not None
        return dispatch(self.subscript_dispatcher, type(subscript.base_type), subscript)

    def translate_name_type_field(self, field: nodes.Field) -> cpp_nodes.Expression:
        base = self.translate_expression(field.base)
        assert base is not None
        if isinstance(base, cpp_nodes.SpecialName) and base.value == cpp_nodes.SpecialName.this.value:
            return cpp_nodes.ArrowField(base, field.field.member)
        return cpp_nodes.DotField(base, field.field.member)

    def translate_ref_field(self, field: nodes.Field) -> cpp_nodes.Expression:
        base = self.translate_expression(field.base)
        assert (field.field.unmangled or field.field.member) == 'value'
        return cpp_nodes.Deref(base)

    def translate_generic_type_field(self, field: nodes.Field) -> cpp_nodes.Expression:
        base = self.translate_expression(field.base)
        assert base is not None
        if isinstance(base, cpp_nodes.SpecialName) and base.value == cpp_nodes.SpecialName.this.value:
            return cpp_nodes.ArrowField(base, field.field.member)
        return cpp_nodes.DotField(base, field.field.member)

    def translate_algebraic_type_field(self, field: nodes.Field) -> cpp_nodes.Expression:
        assert isinstance(field.base_type, nodes.AlgebraicType) and field.base_type.constructor
        field_base = self.translate_expression(field.base)
        if isinstance(field_base, cpp_nodes.SpecialName) and field_base.value == cpp_nodes.SpecialName.this.value:
            return cpp_nodes.ArrowField(field_base, field.field.member)
        base = cpp_nodes.FunctionCall(
            cpp_nodes.StdName.get, [field_base],
            parameters=[cpp_nodes.Id(algebraic_constructor_name(field.base_type.base, field.base_type.constructor))]
        )
        return cpp_nodes.DotField(base, field.field.member)

    def translate_vector_type_field(self, field: nodes.Field) -> cpp_nodes.Expression:
        assert isinstance(field.base_type, nodes.VectorType)
        field_name = field.field.unmangled or field.field.member
        if field_name == nodes.VectorFields.length.value:
            self.add_include(cpp_nodes.StdModule.vector)
            return cpp_nodes.MethodCall(self.translate_expression(field.base), "size", [])
        else:
            assert 0, f"Cannot translate '{field.field}' field on Vector type"

    def translate_dict_type_field(self, field: nodes.Field) -> cpp_nodes.Expression:
        assert isinstance(field.base_type, nodes.DictType)
        field_name = field.field.unmangled or field.field.member
        if field_name == nodes.DictFields.length.value:
            self.add_include(cpp_nodes.StdModule.map)
            return cpp_nodes.MethodCall(self.translate_expression(field.base), "size", [])
        else:
            assert 0, f"Cannot translate '{field.field}' field on Dict type"

    def translate_builtin_type_field(self, field: nodes.Field) -> cpp_nodes.Expression:
        assert isinstance(field.base_type, nodes.BuiltinType)
        if field.base_type.value == nodes.BuiltinType.string.value:
            field_name = field.field.unmangled or field.field.member
            if field_name == nodes.StringFields.length.value:
                base = self.translate_expression(field.base)
                assert base is not None
                return cpp_nodes.MethodCall(base, field.field.member, arguments=[])
            assert 0, f"Field 'String.{field.field}' is not supported"
        else:
            assert 0, f"Fields for '{field.base_type.to_code()}' are not supported"

    def translate_builtin_type_subscript(self, subscript: nodes.Subscript) -> cpp_nodes.Expression:
        assert isinstance(subscript.base_type, nodes.BuiltinType)
        if subscript.base_type.value == nodes.BuiltinType.string.value:
            return cpp_nodes.Subscript(
                self.translate_expression(subscript.base), self.translate_expression(subscript.index)
            )
        else:
            assert 0, f"Subscript of '{subscript.base_type.to_code()}' is not supported"

    def translate_collection_type_subscript(self, subscript: nodes.Subscript) -> cpp_nodes.Expression:
        return cpp_nodes.Subscript(
            self.translate_expression(subscript.base), self.translate_expression(subscript.index)
        )

    def translate_special_name(self, name: nodes.SpecialName) -> cpp_nodes.Expression:
        return {
            nodes.SpecialName.self.value: cpp_nodes.SpecialName.this
        }[name.value]

    def translate_builtin_func(self, func: nodes.BuiltinFunc) -> cpp_nodes.Expression:
        self.add_library_include(library.Modules.builtins)
        return cpp_nodes.Id(library.Builtins.from_builtin_func(func).value)

    def translate_private_builtin_func(self, func: nodes.PrivateBuiltinFunc) -> cpp_nodes.Expression:
        self.add_library_include(library.Modules.builtins)
        return cpp_nodes.Id(func.value)

    def translate_named_argument(self, named_argument: nodes.NamedArgument) -> cpp_nodes.Expression:
        name = self.translate_expression(named_argument.name)
        assert isinstance(name, cpp_nodes.Id)
        return cpp_nodes.NamedArgument(
            name, self.translate_expression(named_argument.value)
        )

    def translate_function_call(self, function_call: nodes.FunctionCall) -> cpp_nodes.Expression:
        if isinstance(function_call.function_path, nodes.BuiltinFunc):
            return dispatch(
                self.translate_builtin_function_dispatcher, function_call.function_path.value, function_call.arguments
            )
        init_parameters: t.List[cpp_nodes.Type] = []
        if function_call.instance_call_parameters:
            init_parameters = [self.translate_type(param) for param in function_call.instance_call_parameters]
        return cpp_nodes.FunctionCall(
            self.translate_expression(function_call.function_path),
            [self.translate_expression(arg) for arg in function_call.arguments], init_parameters
        )

    def translate_vector_literal(self, literal: nodes.VectorLiteral) -> cpp_nodes.Expression:
        elements = []
        for element in literal.elements:
            translated_element = self.translate_expression(element)
            assert translated_element is not None
            elements.append(translated_element)
        return cpp_nodes.ArrayLiteral(elements)

    def translate_dict_literal(self, literal: nodes.DictLiteral) -> t.Optional[cpp_nodes.Expression]:
        assert literal.annotation is not None
        if not literal.keys:
            return None
        _, cpp_tmp = self.create_tmp(self.translate_type(literal.annotation))
        for key, value in zip(literal.keys, literal.values):
            translated_key = self.translate_expression(key)
            translated_value = self.translate_expression(value)
            assert translated_key is not None
            assert translated_value is not None
            left = cpp_nodes.Subscript(cpp_tmp, translated_key)
            self.nodes_buffer.append(cpp_nodes.Assignment(left, cpp_nodes.Operator.eq, translated_value))
        return cpp_tmp

    def translate_optional_type_constructor(self, constructor: nodes.OptionalTypeConstructor) -> cpp_nodes.Expression:
        assert constructor.value == nodes.OptionalTypeConstructor.none.value
        return cpp_nodes.StdName.nullopt

    def translate_optional_some_call(self, call: nodes.OptionalSomeCall) -> cpp_nodes.Expression:
        result = self.translate_expression(call.value)
        assert result is not None
        return result

    def translate_optional_some_value(self, value: nodes.OptionalSomeValue) -> cpp_nodes.Expression:
        inner_value = self.translate_expression(value.value)
        assert inner_value is not None
        return cpp_nodes.Deref(inner_value)

    def translate_binary_expression(self, value: nodes.BinaryExpression) -> cpp_nodes.Expression:
        if value.operator.value == nodes.Operator.is_.value:
            assert isinstance(value.right, nodes.BuiltinType) and value.right.value == nodes.BuiltinType.object_.value
            return cpp_nodes.BoolLiteral.true
        left = self.translate_expression(value.left)
        assert left is not None
        right = self.translate_expression(value.right)
        assert right is not None
        if isinstance(left, cpp_nodes.ArrayLiteral) and value.operator.value == nodes.Operator.add.value:
            assert isinstance(right, cpp_nodes.ArrayLiteral)
            assert isinstance(value.left, nodes.VectorLiteral) and isinstance(value.right, nodes.VectorLiteral)
            assert value.left.typ is not None and value.right.typ is not None
            _, tmp1 = self.create_tmp(self.translate_type(value.left.typ), left)
            _, tmp2 = self.create_tmp(self.translate_type(value.right.typ), right)
            self.nodes_buffer.append(
                cpp_nodes.Semicolon(
                    cpp_nodes.MethodCall(
                        tmp1, "insert", [
                            cpp_nodes.MethodCall(tmp1, "end", []), cpp_nodes.MethodCall(tmp2, "begin", []),
                            cpp_nodes.MethodCall(tmp2, "end", [])
                        ]
                    )
                )
            )
            return tmp1
        if value.operator in nodes.Operator.higher_order_boolean_operators():
            operator = {
                nodes.Operator.and_.value: cpp_nodes.Operator.and_,
                nodes.Operator.or_.value: cpp_nodes.Operator.or_
            }[value.operator.value]
        else:
            operator = cpp_nodes.Operator(value.operator.value)
        return cpp_nodes.BinaryExpression(left, operator, right)

    def translate(self, ast: nodes.AST) -> cpp_nodes.AST:
        def add_node(node: cpp_nodes.Node):
            buf = self.nodes_buffer
            self.nodes_buffer = []
            for n in buf:
                add_node(n)

            if isinstance(node, (cpp_nodes.FunctionDeclaration, cpp_nodes.ClassDeclaration, cpp_nodes.Template)):
                self.top_nodes.append(node)
            else:
                self.main_function_body.append(node)

        self.includes = {}
        self.top_nodes = []
        self.top_nodes_end = []
        self.main_function_body = []
        self.nodes_buffer = []
        self.tmp_count = 0

        to_be_translated = {}

        for node in ast:
            if isinstance(node, (
                    nodes.StructDeclaration, nodes.AlgebraicDeclaration, nodes.InterfaceDeclaration,
                    nodes.FunctionDeclaration)):
                to_be_translated[node.name.member] = node
            elif isinstance(node, nodes.ExtensionDeclaration):
                entry = to_be_translated[node.name.member]
                assert isinstance(entry, nodes.StructDeclaration)
                entry.interfaces += node.interfaces
                entry.private_methods += node.private_methods
                entry.public_methods += node.public_methods
                entry.special_methods += node.special_methods
            else:
                translated_list = self.translate_body([node])
                for n in translated_list:
                    add_node(n)

        structs = []
        for struct in self.translate_body(list(to_be_translated.values())):
            structs.append(struct)

        return0 = cpp_nodes.Return(cpp_nodes.IntegerLiteral("0"))
        main_function = cpp_nodes.FunctionDeclaration(
            return_type=cpp_nodes.PrimitiveTypes.int, name="main", arguments=[], body=self.main_function_body + [return0]
        )
        return (
            t.cast(cpp_nodes.AST, list(self.includes.values())) + structs + self.top_nodes +
            self.top_nodes_end + [main_function]
        )

    def translate_body(self, ast: nodes.AST) -> cpp_nodes.AST:
        result = []
        for node in ast:
            self.current_line = node.line
            translated = dispatch(self.node_dispatcher, type(node), node)
            result.extend(self.nodes_buffer)
            self.nodes_buffer = []
            if translated is not None:
                result.append(translated)
        return result

    def translate_function_declaration(self, node: nodes.FunctionDeclaration) -> cpp_nodes.Node:
        return_type = self.translate_type(node.return_type)
        arguments = [cpp_nodes.Argument(self.translate_type(arg.type), arg.name.member) for arg in node.arguments]
        self.env.inc_nesting()
        body = self.translate_body(node.body)
        self.env.dec_nesting()
        func_decl = cpp_nodes.FunctionDeclaration(return_type, node.name.member, arguments, body)
        if node.parameters:
            return cpp_nodes.Template([self.translate_type(param) for param in node.parameters], func_decl)
        return func_decl

    def translate_method_declaration(self, node: nodes.MethodDeclaration) -> cpp_nodes.FunctionDeclaration:
        return_type = self.translate_type(node.return_type)
        arguments = [cpp_nodes.Argument(self.translate_type(arg.type), arg.name.member) for arg in node.arguments]
        self.env.inc_nesting()
        body = self.translate_body(node.body)
        self.env.dec_nesting()
        return cpp_nodes.FunctionDeclaration(return_type, node.name.member, arguments, body)

    def translate_special_method(self, node: nodes.MethodDeclaration) -> cpp_nodes.FunctionDeclaration:
        if isinstance(node.name, nodes.SpecialMethods):
            real_name = node.name.value
        elif isinstance(node.name, nodes.Name):
            real_name = node.name.unmangled or node.name.member
        if real_name == nodes.SpecialMethods.as_.value:
            assert isinstance(node.return_type, nodes.BuiltinType) and node.return_type == nodes.BuiltinType.string
            printing_override_arguments = [
                cpp_nodes.Argument(cpp_nodes.Addr(cpp_nodes.StdName.ostream), '_arg1'),
                cpp_nodes.Argument(cpp_nodes.Addr(cpp_nodes.Id(self.struct_name)), '_arg2')
            ]
            printing_override = cpp_nodes.FunctionDeclaration(
                cpp_nodes.Addr(cpp_nodes.StdName.ostream), 'operator<<', printing_override_arguments, body=[
                    cpp_nodes.Semicolon(
                        cpp_nodes.BinaryExpression(
                            cpp_nodes.Id('_arg1'), cpp_nodes.Operator.lshift,
                            cpp_nodes.MethodCall(cpp_nodes.Id('_arg2'), 'toString', [])
                        )
                    ),
                    cpp_nodes.Return(cpp_nodes.Id('_arg1'))
                ]
            )
            self.top_nodes_end.append(printing_override)
            node.name = nodes.Name('toString')
            return self.translate_method_declaration(node)
        node.name = nodes.Name('operator' + SPECIAL_METHOD_TO_OPERATOR[real_name])
        return self.translate_method_declaration(node)

    def translate_struct_declaration(self, node: nodes.StructDeclaration) -> cpp_nodes.Node:
        # list(...) for mypy
        private = self.translate_body(list(node.private_fields)) + self.translate_body(list(node.private_methods))
        self.struct_name = node.name.member
        special_methods: t.List[cpp_nodes.Node] = [
            self.translate_special_method(method) for method in node.special_methods
        ]
        public: t.List[cpp_nodes.Node] = []
        if not has_default_constructor(node.init_declarations):
            public.append(cpp_nodes.InitDeclaration(node.name.member, [], delegation_arguments=None, body=[]))
        public.extend(
            self.translate_body(list(node.public_fields)) +
            self.translate_body(list(node.init_declarations)) +
            self.translate_body(list(node.public_methods)) + special_methods
        )
        parents = []
        for interface in node.interfaces:
            if not isinstance(interface, nodes.BuiltinType) or not interface.is_interface:
                parents.append((cpp_nodes.AccessModifier.public, self.translate_type(interface)))
        struct_declaration = cpp_nodes.ClassDeclaration(node.name.member, parents, private, public)
        if node.parameters:
            return cpp_nodes.Template(
                [self.translate_type(parameter) for parameter in node.parameters], struct_declaration
            )
        return struct_declaration

    def translate_interface_declaration(self, node: nodes.InterfaceDeclaration) -> cpp_nodes.Node:
        # list(...) for mypy
        class_declaration = cpp_nodes.ClassDeclaration(
            node.name.member,
            [(cpp_nodes.AccessModifier.public, self.translate_type(interface)) for interface in node.implemented_interfaces],
            private=[], public=self.translate_body(list(node.fields)) + self.translate_body(list(node.methods))
        )
        if node.parameters:
            return cpp_nodes.Template(
                [self.translate_type(parameter) for parameter in node.parameters], class_declaration
            )
        return class_declaration

    def translate_algebraic_declaration(self, node: nodes.AlgebraicDeclaration) -> None:
        # list(...) for mypy
        constructor_names = []
        for constructor in node.constructors:
            constructor_names.append(constructor.name)
            constructor.name = nodes.Name(algebraic_constructor_name(node.name, constructor.name))
        body = self.translate_body(list(node.constructors))
        funcs: t.List[nodes.Node] = []
        self_type = nodes.AlgebraicType(
            node.name, parameters=[], constructor=None,
            constructor_types={name.member: name for name in constructor_names}
        )
        self_arg = nodes.Argument("self", self_type)
        for method in node.private_methods + node.public_methods:
            funcs.append(
                nodes.FunctionDeclaration(
                    method.line, nodes.Name(algebraic_method_name(node.name, method.name)), [],
                    [self_arg] + method.arguments, method.return_type, where_clause=None, body=method.body
                )
            )
        methods = self.translate_body(funcs)
        self.nodes_buffer.extend(body)
        self.nodes_buffer.extend(methods)
        return None

    def translate_init_declaration(self, declaration: nodes.InitDeclaration) -> cpp_nodes.InitDeclaration:
        arguments = []
        for arg in declaration.arguments:
            if arg.value is not None:
                value: t.Optional[cpp_nodes.Expression] = self.translate_expression(arg.value)
            else:
                value = None
            arguments.append(cpp_nodes.Argument(self.translate_type(arg.type), arg.name.member, value))
        if len(declaration.body) == 1 and isinstance(declaration.body[0], nodes.InitCall):
            delegation_arguments = [
                # TODO: rearrange named arguments if needed
                self.translate_expression(argument.value)
                if isinstance(argument, nodes.NamedArgument) else self.translate_expression(argument)
                for argument in declaration.body[0].arguments
            ]
            return cpp_nodes.InitDeclaration(
                self.struct_name, arguments, delegation_arguments=delegation_arguments, body=[]
            )
        body = self.translate_body(declaration.body)
        return cpp_nodes.InitDeclaration(
            self.struct_name, arguments, delegation_arguments=None, body=body
        )

    def translate_field_declaration(self, node: nodes.FieldDeclaration) -> cpp_nodes.Declaration:
        return cpp_nodes.Declaration(self.translate_type(node.type), node.name.member, value=None)

    def translate_assignment(self, node: nodes.Assignment) -> cpp_nodes.Assignment:
        left = self.translate_expression(node.left)
        right = self.translate_expression(node.right)
        assert left is not None
        assert right is not None
        return cpp_nodes.Assignment(left, self.translate_operator(node.operator), right)

    def translate_for_statement(self, node: nodes.For) -> cpp_nodes.For:
        if isinstance(node.container_type, nodes.VectorType):
            element_type = node.container_type.subtype
        elif isinstance(node.container_type, nodes.BuiltinType):
            element_type = nodes.BuiltinType.char
        else:
            raise NotImplementedError
        container_type = self.translate_type(node.container_type)
        _, container_tmp = self.create_tmp(container_type, self.translate_expression(node.container))
        iterator_tmp = self.create_tmp_name()
        iterator_type = cpp_nodes.MemberName(container_type, "iterator")
        start_condition = cpp_nodes.SubDeclaration(
            iterator_type, iterator_tmp.value, cpp_nodes.MethodCall(container_tmp, 'begin', [])
        )
        continue_condition = cpp_nodes.BinaryExpression(
            iterator_tmp, cpp_nodes.Operator.neq, cpp_nodes.MethodCall(container_tmp, 'end', [])
        )
        end_condition = cpp_nodes.UnaryExpression(cpp_nodes.Operator.increment, iterator_tmp)
        self.env.inc_nesting()
        nodes_buffer = self.nodes_buffer
        self.nodes_buffer = []
        body = self.translate_body(node.body)
        self.nodes_buffer = nodes_buffer
        self.env.dec_nesting()
        element_declaration: cpp_nodes.Node = cpp_nodes.Declaration(
            self.translate_type(element_type), node.element.member, cpp_nodes.Deref(iterator_tmp)
        )
        return cpp_nodes.For(start_condition, continue_condition, end_condition, [element_declaration] + body)

    def translate_while_statement(self, node: nodes.While) -> cpp_nodes.While:
        translated_condition, body, assignment = self.desugar_if_condition(node.condition, node.body)
        if assignment is not None:
            body.append(assignment)
        assert translated_condition is not None
        self.env.inc_nesting()
        nodes_buffer = self.nodes_buffer
        self.nodes_buffer = []
        translated_body = self.translate_body(body)
        self.nodes_buffer = nodes_buffer
        self.env.dec_nesting()
        return cpp_nodes.While(translated_condition, translated_body)

    def translate_declaration(self, node: nodes.Decl) -> cpp_nodes.Declaration:
        assert node.type is not None
        if node.value is None:
            value = None
        else:
            value = self.translate_expression(node.value)
        return cpp_nodes.Declaration(self.translate_type(node.type), node.name.member, value)

    def translate_if_statement(self, node: nodes.If) -> cpp_nodes.If:
        condition, new_body, _ = self.desugar_if_condition(node.condition, node.body)
        self.env.inc_nesting()
        nodes_buffer = self.nodes_buffer
        self.nodes_buffer = []
        body = self.translate_body(new_body)
        self.nodes_buffer = nodes_buffer
        self.env.dec_nesting()
        else_ifs = []
        for elif_condition, elif_body in node.elifs:
            else_if_condition, new_elif_body, _ = self.desugar_if_condition(elif_condition, elif_body)
            self.env.inc_nesting()
            nodes_buffer = self.nodes_buffer
            self.nodes_buffer = []
            else_if_body = self.translate_body(new_elif_body)
            self.nodes_buffer = nodes_buffer
            self.env.dec_nesting()
            else_ifs.append((else_if_condition, else_if_body))
        self.env.inc_nesting()
        nodes_buffer = self.nodes_buffer
        self.nodes_buffer = []
        else_ = self.translate_body(node.else_)
        self.nodes_buffer = nodes_buffer
        self.env.dec_nesting()
        return cpp_nodes.If(condition, body, else_ifs, else_)

    def desugar_if_condition(
        self, condition: nodes.Expression, body: nodes.AST
    ) -> t.Tuple[cpp_nodes.Expression, nodes.AST, t.Optional[nodes.Assignment]]:
        if isinstance(condition, nodes.Decl) and condition.is_constant:
            assert condition.value is not None
            tmp, cpp_tmp = self.create_tmp(type_=cpp_nodes.Auto(), value=self.translate_expression(condition.value))
            new_condition = cpp_nodes.BinaryExpression(cpp_tmp, cpp_nodes.Operator.neq, cpp_nodes.StdName.nullopt)
            assert isinstance(condition.type, nodes.OptionalType)
            new_declaration: nodes.Node = nodes.Decl(
                condition.line, DeclType.constant, condition.name, condition.type.inner_type,
                nodes.OptionalSomeValue(tmp)
            )
            new_body = [new_declaration] + body
            assignment = nodes.Assignment(condition.line, tmp, nodes.Operator.eq, condition.value)
            return new_condition, new_body, assignment
        else:
            expression = self.translate_expression(condition)
            assert expression is not None
            return expression, body, None

    def translate_return_statement(self, statement: nodes.Return) -> cpp_nodes.Return:
        value = self.translate_expression(statement.value)
        assert value is not None
        return cpp_nodes.Return(value)

    def translate_print_function_call(self, arguments: t.List[nodes.Expression]) -> cpp_nodes.Expression:
        assert len(arguments) == 1
        self.add_library_include(library.Modules.builtins)
        return cpp_nodes.FunctionCall(cpp_nodes.Id(library.Builtins.print.value), [self.translate_expression(arguments[0])])

    def translate_read_function_call(self, arguments: t.List[nodes.Expression]) -> cpp_nodes.Expression:
        assert len(arguments) == 1
        self.add_library_include(library.Modules.builtins)
        return cpp_nodes.FunctionCall(cpp_nodes.Id(library.Builtins.read.value), [self.translate_expression(arguments[0])])

    def translate_template_type(self, template_type: nodes.TemplateType) -> cpp_nodes.Type:
        result = self.context.template_types[template_type.id]
        if result:
            return self.translate_type(result)
        return cpp_nodes.VoidPtr()

    def translate_vector_type(self, vector_type: nodes.VectorType) -> cpp_nodes.Type:
        self.add_include(cpp_nodes.StdModule.vector)
        return cpp_nodes.GenericType(
            cpp_nodes.StdName.vector, [self.translate_type(vector_type.subtype)]
        )

    def translate_optional_type(self, optional_type: nodes.OptionalType) -> cpp_nodes.Type:
        self.add_include(cpp_nodes.StdModule.optional)
        return cpp_nodes.GenericType(
            cpp_nodes.StdName.optional, [self.translate_type(optional_type.inner_type)]
        )

    def translate_dict_type(self, dict_type: nodes.DictType) -> cpp_nodes.Type:
        self.add_include(cpp_nodes.StdModule.map)
        return cpp_nodes.GenericType(
            cpp_nodes.StdName.map, [self.translate_type(dict_type.key_type), self.translate_type(dict_type.value_type)]
        )

    def translate_function_type(self, function_type: nodes.FunctionType) -> cpp_nodes.Type:
        self.add_include(cpp_nodes.StdModule.functional)
        return cpp_nodes.FunctionType(
            self.translate_type(function_type.return_type),
            [self.translate_type(arg.type) for arg in function_type.arguments]
        )

    def translate_struct_type(self, struct_type: nodes.StructType) -> cpp_nodes.Type:
        base = self.translate_type(struct_type.name)
        if struct_type.parameters:
            return cpp_nodes.GenericType(base, [self.translate_type(param) for param in struct_type.parameters])
        return base

    def translate_generic_type(self, generic_type: nodes.GenericType) -> cpp_nodes.Type:
        base = self.translate_type(generic_type.name)
        if generic_type.parameters:
            return cpp_nodes.GenericType(base, [self.translate_type(param) for param in generic_type.parameters])
        return base

    def translate_algebraic_type(self, algebraic: nodes.AlgebraicType) -> cpp_nodes.Type:
        self.add_include(cpp_nodes.StdModule.variant)
        return cpp_nodes.GenericType(
            cpp_nodes.StdName.variant,
            [cpp_nodes.Id(algebraic_constructor_name(algebraic.base, constructor))
             for constructor in algebraic.constructor_types.values()]
        )

    def translate_ref_type(self, ref_type: nodes.RefType) -> cpp_nodes.Type:
        return cpp_nodes.Pointer(self.translate_type(ref_type.value_type))

    def translate_builtin_type(self, builtin_type: nodes.BuiltinType) -> cpp_nodes.Type:
        if builtin_type.value in nodes.BuiltinType.finite_int_types():
            self.add_include(cpp_nodes.StdModule.cstdint)
        elif builtin_type.value == nodes.BuiltinType.string.value:
            self.add_include(cpp_nodes.StdModule.string)
        return BUILTIN_TYPE_TO_CPP_TYPE[builtin_type.value]

    def translate_name_type(self, name: nodes.Name) -> cpp_nodes.Type:
        return cpp_nodes.Id(name.member)

    def translate_operator(self, operator: nodes.Operator) -> cpp_nodes.Operator:
        return cpp_nodes.Operator(operator.value)

    def create_tmp_name(self) -> cpp_nodes.Id:
        tmp_name = TMP_PREFIX + str(self.tmp_count)
        self.tmp_count += 1
        return cpp_nodes.Id(tmp_name)

    def create_tmp(
        self, type_: cpp_nodes.Type, value: t.Optional[cpp_nodes.Expression] = None
    ) -> t.Tuple[nodes.Name, cpp_nodes.Id]:
        tmp_name = self.create_tmp_name()
        self.nodes_buffer.append(cpp_nodes.Declaration(type_, tmp_name.value, value=value))
        return nodes.Name(tmp_name.value), tmp_name

    def add_include(self, module: cpp_nodes.StdModule):
        self.includes[module.value] = cpp_nodes.Include(module.value)

    def add_library_include(self, module: library.Modules):
        self.includes[module.value] = cpp_nodes.Include(module.header, standard=False)
        for include in module.includes:
            self.add_include(include)

    def test(self):
        self.assertEqual(TYPES, set(subclass.__name__ for subclass in self.type_dispatcher.keys()))
        self.assertEqual(EXPRS, set(subclass.__name__ for subclass in self.expression_dispatcher.keys()))
        self.assertEqual(
            NODES.difference([nodes.ExtensionDeclaration.__name__]),
            set(subclass.__name__ for subclass in self.node_dispatcher.keys())
        )

        builtin_funcs = set(func.value for func in nodes.BuiltinFunc)
        self.assertEqual(builtin_funcs, set(self.translate_builtin_function_dispatcher.keys()))

        self.assertEqual(TYPES, set(subclass.__name__ for subclass in self.field_dispatcher.keys()))
        self.assertEqual(TYPES, set(subclass.__name__ for subclass in self.subscript_dispatcher.keys()))
        self.assertEqual(TYPES, set(subclass.__name__ for subclass in self.method_call_dispatcher.keys()))
