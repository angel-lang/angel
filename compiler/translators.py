import sys
import typing as t

from . import nodes, cpp_nodes


def _error_base(message: str) -> t.NoReturn:
    print(f"Translation Error: {message}")
    sys.exit(1)


def _error_not_implemented(message: str) -> t.NoReturn:
    _error_base(message + " feature is not implemented")


def _error_unknown_node_type(node_type: type, func: t.Callable) -> t.NoReturn:
    _error_base(f"cannot dispatch node type '{node_type}' in func '{func}'")


BUILTIN_TYPE_TO_CPP_TYPE = {
    nodes.BuiltinType.i8.value: cpp_nodes.StdName.int_fast8_t,
    nodes.BuiltinType.i16.value: cpp_nodes.StdName.int_fast16_t,
    nodes.BuiltinType.i32.value: cpp_nodes.StdName.int_fast32_t,
    nodes.BuiltinType.i64.value: cpp_nodes.StdName.int_fast64_t,
}


class Translator:
    top_nodes: cpp_nodes.AST
    main_function_body: cpp_nodes.AST
    includes: t.Dict[str, cpp_nodes.Include]

    def repl_eval(self, node: nodes.Node) -> t.Any:
        dispatcher: t.Dict[type, t.Callable[[nodes.Node], t.Any]] = {
            nodes.ConstantDeclaration: lambda n: None,
            nodes.FunctionCall: self._repl_eval_function_call,
        }
        func = dispatcher.get(type(node), lambda n: _error_unknown_node_type(type(n), self.repl_eval))
        return func(node)

    def _repl_eval_function_call(self, node: nodes.Node) -> t.Any:
        assert isinstance(node, nodes.FunctionCall)
        function_path_dispatcher: t.Dict[type, t.Callable[[nodes.Expression, t.List[nodes.Expression]], t.Any]] = {
            nodes.Name: self._repl_eval_function_as_name_call
        }
        func = function_path_dispatcher.get(
            type(node.function_path),
            lambda path, _: _error_unknown_node_type(type(path), self._repl_eval_function_call))
        return func(node.function_path, node.args)

    def _repl_eval_function_as_name_call(self, path: nodes.Expression, args: t.List[nodes.Expression]) -> t.Any:
        assert isinstance(path, nodes.Name)
        builtin_func_dispatcher: t.Dict[str, t.Callable[[nodes.Name, t.List[nodes.Expression]], cpp_nodes.Node]] = {
            nodes.BuiltinFunc.print.value: self._repl_eval_print_call
        }
        func = builtin_func_dispatcher.get(path.member)
        if func is None:
            _error_not_implemented("user-defined functions")
        return func(path, args)

    def _repl_eval_print_call(self, function_path: nodes.Name, args: t.List[nodes.Expression]) -> t.Any:
        assert function_path.member == nodes.BuiltinFunc.print.value
        assert len(args) == 1
        return self._repl_eval_expression(args[0])

    def _repl_eval_expression(self, expression: nodes.Expression) -> t.Any:
        if isinstance(expression, nodes.IntegerLiteral):
            return int(expression.value)
        elif isinstance(expression, nodes.StringLiteral):
            return expression.value
        else:
            _error_unknown_node_type(type(expression), self._repl_eval_expression)

    def translate(self, ast: nodes.AST) -> cpp_nodes.AST:
        self.top_nodes = []
        self.main_function_body = []
        self.includes = {}
        for node in ast:
            self._translate_node(node)

        return0 = cpp_nodes.Return(cpp_nodes.IntegerLiteral("0"))
        main_function = cpp_nodes.FunctionDeclaration(
            return_type=cpp_nodes.PrimitiveTypes.int, name="main", args=[], body=self.main_function_body + [return0]
        )
        return t.cast(cpp_nodes.AST, list(self.includes.values())) + self.top_nodes + [main_function]

    def _translate_node(self, node: nodes.Node):
        dispatcher: t.Dict[type, t.Callable[[nodes.Node], cpp_nodes.Node]] = {
            nodes.ConstantDeclaration: self._translate_constant_declaration,
            nodes.FunctionCall: self._translate_function_call,
        }
        func = dispatcher.get(type(node), lambda n: _error_unknown_node_type(type(n), self._translate_node))
        self.main_function_body.append(func(node))

    def _translate_constant_declaration(self, node: nodes.Node) -> cpp_nodes.Node:
        assert isinstance(node, nodes.ConstantDeclaration)
        type_ = self._translate_type(node.type)
        name = node.name.member
        value = self._translate_expression(node.value)
        return cpp_nodes.Declaration(type_, name, value)

    def _translate_function_call(self, node: nodes.Node) -> cpp_nodes.Node:
        assert isinstance(node, nodes.FunctionCall)
        function_path_dispatcher: t.Dict[type, t.Callable[[nodes.FunctionCall], cpp_nodes.Node]] = {
            nodes.Name: self._translate_function_as_name_call,
        }
        func = function_path_dispatcher.get(
            type(node.function_path),
            lambda call: _error_unknown_node_type(type(call.function_path), self._translate_function_call))
        return func(node)

    def _translate_function_as_name_call(self, call: nodes.FunctionCall) -> cpp_nodes.Node:
        assert isinstance(call.function_path, nodes.Name)
        builtin_func_dispatcher: t.Dict[str, t.Callable[[nodes.Name, t.List[nodes.Expression]], cpp_nodes.Node]] = {
            nodes.BuiltinFunc.print.value: self._translate_print_call
        }
        func = builtin_func_dispatcher.get(call.function_path.member)
        if func is None:
            args = [self._translate_expression(arg) for arg in call.args]
            return cpp_nodes.FunctionCall(cpp_nodes.Id(call.function_path.member), args)
        return func(call.function_path, call.args)

    def _translate_print_call(self, function_path: nodes.Name, args: t.List[nodes.Expression]) -> cpp_nodes.Node:
        assert function_path.member == nodes.BuiltinFunc.print.value
        assert len(args) == 1
        self._add_include(cpp_nodes.StdModule.iostream)
        value = self._translate_expression(args[0])
        return cpp_nodes.Semicolon(
            cpp_nodes.BinaryExpression(
                cpp_nodes.BinaryExpression(cpp_nodes.StdName.cout, cpp_nodes.Operator.lshift, value),
                cpp_nodes.Operator.lshift, cpp_nodes.StdName.endl
            ))

    def _translate_type(self, type_: nodes.Type) -> cpp_nodes.Type:
        if isinstance(type_, nodes.Name):
            try:
                builtin_type = nodes.BuiltinType(type_.member)
            except ValueError:
                return cpp_nodes.Id(type_.member)
            else:
                return self._translate_builtin_type(builtin_type)
        else:
            _error_unknown_node_type(type(type_), self._translate_type)

    def _translate_builtin_type(self, builtin_type: nodes.BuiltinType) -> cpp_nodes.Type:
        if builtin_type.value in nodes.BuiltinType.finite_int_types():
            self._add_include(cpp_nodes.StdModule.cstdint)
        return BUILTIN_TYPE_TO_CPP_TYPE[builtin_type.value]

    def _translate_expression(self, expression: nodes.Expression) -> cpp_nodes.Expression:
        if isinstance(expression, nodes.IntegerLiteral):
            return cpp_nodes.IntegerLiteral(expression.value)
        elif isinstance(expression, nodes.StringLiteral):
            return cpp_nodes.StringLiteral(expression.value)
        elif isinstance(expression, nodes.Name):
            return cpp_nodes.Id(expression.member)
        else:
            _error_unknown_node_type(type(expression), self._translate_expression)

    def _add_include(self, module: cpp_nodes.StdModule):
        self.includes[module.value] = cpp_nodes.Include(module)
