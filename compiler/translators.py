import typing as t

from . import nodes, cpp_nodes, environment, environment_entries as entries, errors
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
}


class Translator:
    top_nodes: cpp_nodes.AST
    main_function_body: cpp_nodes.AST
    includes: t.Dict[str, cpp_nodes.Include]

    def __init__(self, lines: t.List[str]) -> None:
        self.env = environment.Environment()
        self.lines = lines
        self.current_line = 1

        # REPL eval
        repl_eval_builtin_function_call_dispatcher: t.Dict[str, t.Callable[[t.List[nodes.Expression]], t.Any]] = {
            nodes.BuiltinFunc.print.value: lambda args: self.repl_eval_expression(args[0]),
        }

        repl_eval_function_call_dispatcher_by_function_path = {
            nodes.BuiltinFunc: lambda path, args: dispatch(
                repl_eval_builtin_function_call_dispatcher, path.value, args
            ),
        }

        repl_eval_assignment_by_left = {
            nodes.Name: self.repl_eval_name_assignment,
        }

        repl_eval_dispatcher = {
            nodes.ConstantDeclaration: self.repl_eval_constant_declaration,
            nodes.VariableDeclaration: self.repl_eval_variable_declaration,
            nodes.Assignment: lambda node: dispatch(
                repl_eval_assignment_by_left, type(node.left), node.left, node.operator, node.right
            ),
            nodes.FunctionCall: lambda node: dispatch(
                repl_eval_function_call_dispatcher_by_function_path, type(node.function_path),
                node.function_path, node.args
            ),
        }
        self.repl_eval_node = lambda node: dispatch(repl_eval_dispatcher, type(node), node)

        repl_eval_expression_dispatcher = {
            nodes.IntegerLiteral: lambda value: int(value.value),
            nodes.StringLiteral: lambda value: value.value,
            nodes.Name: self.repl_eval_name,
            type(None): lambda _: None,
        }
        self.repl_eval_expression = lambda value: dispatch(repl_eval_expression_dispatcher, type(value), value)

        # Translation
        translate_builtin_function_dispatcher = {
            nodes.BuiltinFunc.print.value: self.translate_print_function_call,
        }

        translate_function_call_dispatcher_by_function_path = {
            nodes.BuiltinFunc: lambda path, args: dispatch(translate_builtin_function_dispatcher, path.value, args),
        }

        self.translate_node_dispatcher = {
            nodes.ConstantDeclaration: lambda node: cpp_nodes.Declaration(
                self.translate_type(node.type), node.name.member, self.translate_expression(node.value)
            ),
            nodes.VariableDeclaration: lambda node: cpp_nodes.Declaration(
                self.translate_type(node.type), node.name.member, self.translate_expression(node.value)
            ),
            nodes.Assignment: lambda node: cpp_nodes.Assignment(
                self.translate_expression(node.left), self.translate_operator(node.operator),
                self.translate_expression(node.right)
            ),
            nodes.FunctionCall: lambda node: dispatch(
                translate_function_call_dispatcher_by_function_path, type(node.function_path),
                node.function_path, node.args
            ),
        }

        translate_expression_dispatcher = {
            nodes.IntegerLiteral: lambda value: cpp_nodes.IntegerLiteral(value.value),
            nodes.StringLiteral: lambda value: cpp_nodes.StringLiteral(value.value),
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

        for node in ast:
            self.current_line = node.line
            self.main_function_body.append(dispatch(self.translate_node_dispatcher, type(node), node))

        return0 = cpp_nodes.Return(cpp_nodes.IntegerLiteral("0"))
        main_function = cpp_nodes.FunctionDeclaration(
            return_type=cpp_nodes.PrimitiveTypes.int, name="main", args=[], body=self.main_function_body + [return0]
        )
        return t.cast(cpp_nodes.AST, list(self.includes.values())) + self.top_nodes + [main_function]

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

    def repl_eval(self, ast: nodes.AST) -> t.Any:
        result = None
        for node in ast:
            self.current_line = node.line
            result = self.repl_eval_node(node)
        return result

    def repl_eval_constant_declaration(self, node: nodes.ConstantDeclaration) -> None:
        assert node.type is not None
        self.env.add_constant(
            node.line, node.name, node.type, node.value, computed_value=self.repl_eval_expression(node.value)
        )

    def repl_eval_variable_declaration(self, node: nodes.VariableDeclaration) -> None:
        assert node.type is not None
        self.env.add_variable(
            node.line, node.name, node.type, computed_value=self.repl_eval_expression(node.value)
        )

    def repl_eval_name_assignment(self, left: nodes.Name, operator: nodes.Operator, right: nodes.Expression) -> None:
        entry = self.env[left.member]
        if isinstance(entry, entries.VariableEntry):
            if operator.value == nodes.Operator.eq.value:
                entry.computed_value = self.repl_eval_expression(right)
            else:
                raise errors.AngelNotImplemented
        elif isinstance(entry, entries.ConstantEntry):
            if entry.has_value:
                raise errors.AngelConstantReassignment(
                    left, self.get_code(self.current_line), self.get_code(entry.line))
            if operator.value == nodes.Operator.eq.value:
                entry.computed_value = self.repl_eval_expression(right)
                entry.has_value = True
            else:
                raise errors.AngelNotImplemented
        else:
            raise errors.AngelNameError(left, self.get_code(self.current_line))

    def repl_eval_name(self, value: nodes.Name) -> t.Any:
        entry = self.env[value.member]
        if isinstance(entry, (entries.ConstantEntry, entries.VariableEntry)):
            return entry.computed_value
        else:
            raise errors.AngelNameError(value, self.get_code(self.current_line))

    def add_include(self, module: cpp_nodes.StdModule):
        self.includes[module.value] = cpp_nodes.Include(module)

    def get_code(self, line: int) -> errors.Code:
        return errors.Code(self.lines[line - 1], line)
