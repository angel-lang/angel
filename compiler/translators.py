import typing as t

from . import nodes, cpp_nodes, environment
from .utils import dispatch

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


TMP_PREFIX = "__tmp_"


class Translator:
    top_nodes: cpp_nodes.AST
    main_function_body: cpp_nodes.AST
    nodes_buffer: cpp_nodes.AST
    includes: t.Dict[str, cpp_nodes.Include]

    def __init__(self) -> None:
        self.env = environment.Environment()
        self.current_line = 1
        self.tmp_count = 0

        # Translation
        translate_builtin_function_dispatcher = {
            nodes.BuiltinFunc.print.value: self.translate_print_function_call,
            nodes.BuiltinFunc.read.value: self.translate_read_function_call,
        }

        translate_function_call_dispatcher_by_function_path = {
            nodes.BuiltinFunc: lambda path, args: dispatch(translate_builtin_function_dispatcher, path.value, args),
            nodes.Name: self.translate_function_as_name_call,
        }
        self.translate_function_call = lambda node: dispatch(
            translate_function_call_dispatcher_by_function_path, type(node.function_path),
            node.function_path, node.args
        )

        self.translate_node_dispatcher = {
            nodes.ConstantDeclaration: lambda node: cpp_nodes.Declaration(
                self.translate_type(node.type), node.name.member, self.translate_expression(node.value)
            ),
            nodes.VariableDeclaration: lambda node: cpp_nodes.Declaration(
                self.translate_type(node.type), node.name.member, self.translate_expression(node.value)
            ),
            nodes.FunctionDeclaration: self.translate_function_declaration,
            nodes.StructDeclaration: self.translate_struct_declaration,
            nodes.FieldDeclaration: self.translate_field_declaration,
            nodes.Assignment: self.translate_assignment,
            nodes.FunctionCall: lambda node: cpp_nodes.Semicolon(self.translate_function_call(node)),
            nodes.While: self.translate_while_statement,
            nodes.If: self.translate_if_statement,
        }

        translate_expression_dispatcher = {
            nodes.IntegerLiteral: lambda value: cpp_nodes.IntegerLiteral(value.value),
            nodes.DecimalLiteral: lambda value: cpp_nodes.DecimalLiteral(value.value),
            nodes.StringLiteral: lambda value: cpp_nodes.StringLiteral(value.value),
            nodes.VectorLiteral: self.translate_vector_literal,
            nodes.DictLiteral: self.translate_dict_literal,
            nodes.CharLiteral: lambda value: cpp_nodes.CharLiteral(value.value),
            nodes.BoolLiteral: lambda value: cpp_nodes.BoolLiteral(value.value.lower()),
            nodes.BinaryExpression: self.translate_binary_expression,
            nodes.FunctionCall: lambda value: self.translate_function_call(value),
            nodes.Name: lambda value: cpp_nodes.Id(value.member),
            nodes.Cast: self.translate_cast,
            type(None): lambda _: None,
        }
        self.translate_expression: t.Callable[[nodes.Expression], t.Optional[cpp_nodes.Expression]] = lambda value: \
            dispatch(translate_expression_dispatcher, type(value), value)

        translate_type_dispatcher: t.Dict[type, t.Callable] = {
            nodes.BuiltinType: self.translate_builtin_type,
            nodes.Name: lambda type_: cpp_nodes.Id(type_.member),
            nodes.VectorType: self.translate_vector_type,
            nodes.DictType: self.translate_dict_type,
            nodes.TemplateType: lambda type_: cpp_nodes.VoidPtr(),
        }
        self.translate_type: t.Callable[[nodes.Type], cpp_nodes.Type] = lambda type_: \
            dispatch(translate_type_dispatcher, type(type_), type_)

    def translate_cast(self, value: nodes.Cast) -> cpp_nodes.Expression:
        expr = self.translate_expression(value.value)
        assert expr is not None
        return cpp_nodes.Cast(expr, self.translate_type(value.to_type))

    def translate_function_as_name_call(
            self, path: nodes.Expression, args: t.List[nodes.Expression]
    ) -> cpp_nodes.Expression:
        translated_path = self.translate_expression(path)
        assert translated_path is not None
        translated_args = []
        for arg in args:
            translated_arg = self.translate_expression(arg)
            assert translated_arg is not None
            translated_args.append(translated_arg)
        return cpp_nodes.FunctionCall(translated_path, translated_args)

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
        tmp = self.create_tmp(self.translate_type(literal.annotation))
        for key, value in zip(literal.keys, literal.values):
            translated_key = self.translate_expression(key)
            translated_value = self.translate_expression(value)
            assert translated_key is not None
            assert translated_value is not None
            left = cpp_nodes.Subscript(tmp, translated_key)
            self.nodes_buffer.append(cpp_nodes.Assignment(left, cpp_nodes.Operator.eq, translated_value))
        return tmp

    def translate_binary_expression(self, value: nodes.BinaryExpression) -> cpp_nodes.Expression:
        left = self.translate_expression(value.left)
        assert left is not None
        right = self.translate_expression(value.right)
        assert right is not None
        return cpp_nodes.BinaryExpression(left, cpp_nodes.Operator(value.operator.value), right)

    def translate(self, ast: nodes.AST) -> cpp_nodes.AST:
        self.includes = {}
        self.top_nodes = []
        self.main_function_body = []
        self.nodes_buffer = []
        self.tmp_count = 0

        for node in self.translate_body(ast):
            if isinstance(node, (cpp_nodes.FunctionDeclaration, cpp_nodes.StructDeclaration)):
                self.top_nodes.append(node)
            else:
                self.main_function_body.extend(self.nodes_buffer)
                self.nodes_buffer = []
                self.main_function_body.append(node)

        return0 = cpp_nodes.Return(cpp_nodes.IntegerLiteral("0"))
        main_function = cpp_nodes.FunctionDeclaration(
            return_type=cpp_nodes.PrimitiveTypes.int, name="main", args=[], body=self.main_function_body + [return0]
        )
        return t.cast(cpp_nodes.AST, list(self.includes.values())) + self.top_nodes + [main_function]

    def translate_body(self, ast: nodes.AST) -> cpp_nodes.AST:
        result = []
        for node in ast:
            self.current_line = node.line
            translated = dispatch(self.translate_node_dispatcher, type(node), node)
            result.extend(self.nodes_buffer)
            self.nodes_buffer = []
            result.append(translated)
        return result

    def translate_function_declaration(self, node: nodes.FunctionDeclaration) -> cpp_nodes.FunctionDeclaration:
        return_type = self.translate_type(node.return_type)
        args = [cpp_nodes.Argument(self.translate_type(arg.type), arg.name.member) for arg in node.args]
        self.env.inc_nesting()
        body = self.translate_body(node.body)
        self.env.dec_nesting()
        return cpp_nodes.FunctionDeclaration(return_type, node.name.member, args, body)

    def translate_struct_declaration(self, node: nodes.StructDeclaration) -> cpp_nodes.StructDeclaration:
        body = self.translate_body(node.body)
        return cpp_nodes.StructDeclaration(node.name.member, body)

    def translate_field_declaration(self, node: nodes.FieldDeclaration) -> cpp_nodes.Declaration:
        return cpp_nodes.Declaration(self.translate_type(node.type), node.name.member, value=None)

    def translate_assignment(self, node: nodes.Assignment) -> cpp_nodes.Assignment:
        left = self.translate_expression(node.left)
        right = self.translate_expression(node.right)
        assert left is not None
        assert right is not None
        return cpp_nodes.Assignment(left, self.translate_operator(node.operator), right)

    def translate_while_statement(self, node: nodes.While) -> cpp_nodes.While:
        condition = self.translate_expression(node.condition)
        assert condition is not None
        self.env.inc_nesting()
        body = self.translate_body(node.body)
        self.env.dec_nesting()
        return cpp_nodes.While(condition, body)

    def translate_if_statement(self, node: nodes.If) -> cpp_nodes.If:
        condition = self.translate_expression(node.condition)
        assert condition is not None
        self.env.inc_nesting()
        body = self.translate_body(node.body)
        self.env.dec_nesting()
        else_ifs = []
        for elif_condition, elif_body in node.elifs:
            else_if_condition = self.translate_expression(elif_condition)
            assert else_if_condition is not None
            self.env.inc_nesting()
            else_if_body = self.translate_body(elif_body)
            self.env.dec_nesting()
            else_ifs.append((else_if_condition, else_if_body))
        self.env.inc_nesting()
        else_ = self.translate_body(node.else_)
        self.env.dec_nesting()
        return cpp_nodes.If(condition, body, else_ifs, else_)

    def translate_print_function_call(self, args: t.List[nodes.Expression]) -> cpp_nodes.Expression:
        assert len(args) == 1
        self.add_include(cpp_nodes.StdModule.iostream)
        value = self.translate_expression(args[0])
        assert value is not None
        return cpp_nodes.BinaryExpression(
            cpp_nodes.BinaryExpression(cpp_nodes.StdName.cout, cpp_nodes.Operator.lshift, value),
            cpp_nodes.Operator.lshift, cpp_nodes.StdName.endl
        )

    def translate_read_function_call(self, args: t.List[nodes.Expression]) -> cpp_nodes.Expression:
        assert len(args) == 1
        self.add_include(cpp_nodes.StdModule.iostream)
        tmp = self.create_tmp(self.translate_type(nodes.BuiltinType.string))
        self.nodes_buffer.append(cpp_nodes.Semicolon(self.translate_print_function_call(args)))
        self.nodes_buffer.append(
            cpp_nodes.Semicolon(cpp_nodes.BinaryExpression(cpp_nodes.StdName.cin, cpp_nodes.Operator.rshift, tmp))
        )
        return tmp

    def translate_vector_type(self, vector_type: nodes.VectorType) -> cpp_nodes.Type:
        self.add_include(cpp_nodes.StdModule.vector)
        return cpp_nodes.GenericType(
            cpp_nodes.StdName.vector, [self.translate_type(vector_type.subtype)]
        )

    def translate_dict_type(self, dict_type: nodes.DictType) -> cpp_nodes.Type:
        self.add_include(cpp_nodes.StdModule.map)
        return cpp_nodes.GenericType(
            cpp_nodes.StdName.map, [self.translate_type(dict_type.key_type), self.translate_type(dict_type.value_type)]
        )

    def translate_builtin_type(self, builtin_type: nodes.BuiltinType) -> cpp_nodes.Type:
        if builtin_type.value in nodes.BuiltinType.finite_int_types():
            self.add_include(cpp_nodes.StdModule.cstdint)
        elif builtin_type.value == nodes.BuiltinType.string.value:
            self.add_include(cpp_nodes.StdModule.string)
        return BUILTIN_TYPE_TO_CPP_TYPE[builtin_type.value]

    def translate_operator(self, operator: nodes.Operator) -> cpp_nodes.Operator:
        return cpp_nodes.Operator(operator.value)

    def create_tmp(self, type_: cpp_nodes.Type) -> cpp_nodes.Id:
        tmp_name = TMP_PREFIX + str(self.tmp_count)
        self.nodes_buffer.append(cpp_nodes.Declaration(type_, tmp_name, value=None))
        self.tmp_count += 1
        return cpp_nodes.Id(tmp_name)

    def add_include(self, module: cpp_nodes.StdModule):
        self.includes[module.value] = cpp_nodes.Include(module)
