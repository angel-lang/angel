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

    nodes.BuiltinType.string.value: cpp_nodes.StdName.string,
    nodes.BuiltinType.bool.value: cpp_nodes.PrimitiveTypes.bool,
    nodes.BuiltinType.void.value: cpp_nodes.PrimitiveTypes.void,
}


class Translator:
    top_nodes: cpp_nodes.AST
    main_function_body: cpp_nodes.AST
    includes: t.Dict[str, cpp_nodes.Include]

    def __init__(self) -> None:
        self.env = environment.Environment()
        self.current_line = 1

        # Translation
        translate_builtin_function_dispatcher = {
            nodes.BuiltinFunc.print.value: self.translate_print_function_call,
        }

        translate_function_call_dispatcher_by_function_path = {
            nodes.BuiltinFunc: lambda path, args: dispatch(translate_builtin_function_dispatcher, path.value, args),
            nodes.Name: lambda path, args: cpp_nodes.Semicolon(
                cpp_nodes.FunctionCall(
                    self.translate_expression(path), [self.translate_expression(arg) for arg in args]
                )
            ),
        }

        self.translate_node_dispatcher = {
            nodes.ConstantDeclaration: lambda node: cpp_nodes.Declaration(
                self.translate_type(node.type), node.name.member, self.translate_expression(node.value)
            ),
            nodes.VariableDeclaration: lambda node: cpp_nodes.Declaration(
                self.translate_type(node.type), node.name.member, self.translate_expression(node.value)
            ),
            nodes.FunctionDeclaration: self.translate_function_declaration,
            nodes.Assignment: lambda node: cpp_nodes.Assignment(
                self.translate_expression(node.left), self.translate_operator(node.operator),
                self.translate_expression(node.right)
            ),
            nodes.FunctionCall: lambda node: dispatch(
                translate_function_call_dispatcher_by_function_path, type(node.function_path),
                node.function_path, node.args
            ),
            nodes.While: self.translate_while_statement,
            nodes.If: self.translate_if_statement,
        }

        translate_expression_dispatcher = {
            nodes.IntegerLiteral: lambda value: cpp_nodes.IntegerLiteral(value.value),
            nodes.StringLiteral: lambda value: cpp_nodes.StringLiteral(value.value),
            nodes.BoolLiteral: lambda value: cpp_nodes.BoolLiteral(value.value.lower()),
            nodes.BinaryExpression: lambda value: cpp_nodes.BinaryExpression(
                self.translate_expression(value.left), cpp_nodes.Operator(value.operator.value),
                self.translate_expression(value.right)
            ),
            nodes.Name: lambda value: cpp_nodes.Id(value.member),
            type(None): lambda _: None,
        }
        self.translate_expression: t.Callable[[nodes.Expression], cpp_nodes.Expression] = lambda value: \
            dispatch(translate_expression_dispatcher, type(value), value)

        translate_type_dispatcher: t.Dict[type, t.Callable] = {
            nodes.BuiltinType: self.translate_builtin_type,
            nodes.Name: lambda type_: cpp_nodes.Id(type_.member),
        }
        self.translate_type: t.Callable[[nodes.Type], cpp_nodes.Type] = lambda type_: \
            dispatch(translate_type_dispatcher, type(type_), type_)

    def translate(self, ast: nodes.AST) -> cpp_nodes.AST:
        self.includes = {}
        self.top_nodes = []
        self.main_function_body = []

        for node in self.translate_body(ast):
            if isinstance(node, cpp_nodes.FunctionDeclaration):
                self.top_nodes.append(node)
            else:
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
            result.append(dispatch(self.translate_node_dispatcher, type(node), node))
        return result

    def translate_function_declaration(self, node: nodes.FunctionDeclaration) -> cpp_nodes.FunctionDeclaration:
        return_type = self.translate_type(node.return_type)
        args = [cpp_nodes.Argument(self.translate_type(arg.type), arg.name.member) for arg in node.args]
        self.env.inc_nesting()
        body = self.translate_body(node.body)
        self.env.dec_nesting()
        return cpp_nodes.FunctionDeclaration(return_type, node.name.member, args, body)

    def translate_while_statement(self, node: nodes.While) -> cpp_nodes.While:
        condition = self.translate_expression(node.condition)
        self.env.inc_nesting()
        body = self.translate_body(node.body)
        self.env.dec_nesting()
        return cpp_nodes.While(condition, body)

    def translate_if_statement(self, node: nodes.If) -> cpp_nodes.If:
        condition = self.translate_expression(node.condition)
        self.env.inc_nesting()
        body = self.translate_body(node.body)
        self.env.dec_nesting()
        else_ifs = []
        for elif_condition, elif_body in node.elifs:
            else_if_condition = self.translate_expression(elif_condition)
            self.env.inc_nesting()
            else_if_body = self.translate_body(elif_body)
            self.env.dec_nesting()
            else_ifs.append((else_if_condition, else_if_body))
        self.env.inc_nesting()
        else_ = self.translate_body(node.else_)
        self.env.dec_nesting()
        return cpp_nodes.If(condition, body, else_ifs, else_)

    def translate_print_function_call(self, args: t.List[nodes.Expression]) -> cpp_nodes.Node:
        assert len(args) == 1
        self.add_include(cpp_nodes.StdModule.iostream)
        value = self.translate_expression(args[0])
        return cpp_nodes.Semicolon(
            cpp_nodes.BinaryExpression(
                cpp_nodes.BinaryExpression(cpp_nodes.StdName.cout, cpp_nodes.Operator.lshift, value),
                cpp_nodes.Operator.lshift, cpp_nodes.StdName.endl
            ))

    def translate_builtin_type(self, builtin_type: nodes.BuiltinType) -> cpp_nodes.Type:
        if builtin_type.value in nodes.BuiltinType.finite_int_types():
            self.add_include(cpp_nodes.StdModule.cstdint)
        elif builtin_type.value == nodes.BuiltinType.string.value:
            self.add_include(cpp_nodes.StdModule.string)
        return BUILTIN_TYPE_TO_CPP_TYPE[builtin_type.value]

    def translate_operator(self, operator: nodes.Operator) -> cpp_nodes.Operator:
        return cpp_nodes.Operator(operator.value)

    def add_include(self, module: cpp_nodes.StdModule):
        self.includes[module.value] = cpp_nodes.Include(module)
