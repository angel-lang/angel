import typing as t

from . import (
    nodes, estimation, type_checking, environment, estimation_nodes as enodes, errors, environment_entries as entries
)
from .utils import dispatch


class Analyzer:

    def __init__(self, lines: t.List[str], env: t.Optional[environment.Environment] = None):
        self.env = env or environment.Environment()
        self.lines = lines
        self.line = 0
        self.function_return_types: t.List[nodes.Type] = []

        self.type_checker = type_checking.TypeChecker()
        self.estimator = estimation.Estimator()

        self.assignment_dispatcher = {
            nodes.Name: self.check_name_reassignment
        }

        self.function_dispatcher = {
            nodes.Name: self.analyze_name_function_call,
            nodes.BuiltinFunc: self.analyze_builtin_function_call,
        }

        self.node_dispatcher = {
            nodes.ConstantDeclaration: self.analyze_constant_declaration,
            nodes.VariableDeclaration: self.analyze_variable_declaration,
            nodes.FunctionDeclaration: self.analyze_function_declaration,
            nodes.StructDeclaration: self.analyze_struct_declaration,
            nodes.FieldDeclaration: self.analyze_field_declaration,

            nodes.Assignment: self.analyze_assignment,
            nodes.If: self.analyze_if_statement,
            nodes.While: self.analyze_while_statement,
            nodes.Return: self.analyze_return,
            nodes.Break: self.analyze_break,
            nodes.FunctionCall: lambda call: dispatch(
                self.function_dispatcher, type(call.function_path), call.line, call.function_path, call.args
            ),
        }

    def analyze_ast(self, ast: nodes.AST) -> nodes.AST:
        return [self.analyze_node(node) for node in ast]

    def analyze_node(self, node: nodes.Node) -> nodes.Node:
        self.line = node.line
        return dispatch(self.node_dispatcher, type(node), node)

    def analyze_constant_declaration(self, declaration: nodes.ConstantDeclaration) -> nodes.ConstantDeclaration:
        if declaration.value:
            constant_type = self.infer_type(declaration.value, supertype=declaration.type)
            estimated_value: t.Optional[enodes.Expression] = self.estimate_value(declaration.value)
        else:
            assert declaration.type is not None
            constant_type = self.check_type(declaration.type)
            estimated_value = None
        self.env.add_constant(
            declaration.line, declaration.name, constant_type, declaration.value, estimated_value
        )
        return nodes.ConstantDeclaration(declaration.line, declaration.name, constant_type, declaration.value)

    def analyze_variable_declaration(self, declaration: nodes.VariableDeclaration) -> nodes.VariableDeclaration:
        if declaration.value:
            constant_type = self.infer_type(declaration.value, supertype=declaration.type)
            estimated_value: t.Optional[enodes.Expression] = self.estimate_value(declaration.value)
        else:
            assert declaration.type is not None
            constant_type = self.check_type(declaration.type)
            estimated_value = None
        self.env.add_variable(
            declaration.line, declaration.name, constant_type, declaration.value, estimated_value
        )
        return nodes.VariableDeclaration(declaration.line, declaration.name, constant_type, declaration.value)

    def analyze_function_declaration(self, declaration: nodes.FunctionDeclaration) -> nodes.FunctionDeclaration:
        args = [nodes.Argument(arg.name, self.check_type(arg.type)) for arg in declaration.args]
        return_type = self.check_type(declaration.return_type)
        self.env.add_function(declaration.line, declaration.name, args, return_type)
        self.env.inc_nesting()
        self.function_return_types.append(return_type)
        for arg in args:
            self.env.add_constant(declaration.line, arg.name, arg.type, value=None)
        body = self.analyze_ast(declaration.body)
        self.function_return_types.pop()
        self.env.dec_nesting()
        self.env.update_function_body(declaration.name, body)
        return nodes.FunctionDeclaration(declaration.line, declaration.name, args, return_type, body)

    def analyze_struct_declaration(self, declaration: nodes.StructDeclaration) -> nodes.StructDeclaration:
        self.env.add_struct(declaration.line, declaration.name)
        self.env.inc_nesting(declaration.name)
        body = self.analyze_ast(declaration.body)
        self.env.dec_nesting(declaration.name)
        return nodes.StructDeclaration(declaration.line, declaration.name, body)

    def analyze_field_declaration(self, declaration: nodes.FieldDeclaration) -> nodes.FieldDeclaration:
        field_type = self.check_type(declaration.type)
        self.env.add_field(declaration.line, declaration.name, field_type)
        return nodes.FieldDeclaration(declaration.line, declaration.name, field_type)

    def analyze_assignment(self, statement: nodes.Assignment) -> nodes.Assignment:
        if statement.operator.value != nodes.Operator.eq.value:
            right: nodes.Expression = nodes.BinaryExpression(
                statement.left, statement.operator.to_arithmetic_operator(), statement.right
            )
        else:
            right = statement.right
        self.infer_type(right, supertype=self.infer_type(statement.left))
        dispatch(self.assignment_dispatcher, type(statement.left), statement.left)
        return nodes.Assignment(statement.line, statement.left, nodes.Operator.eq, right)

    def analyze_if_statement(self, statement: nodes.If) -> nodes.If:
        if isinstance(statement.condition, nodes.ConstantDeclaration):
            condition: nodes.Expression = self.analyze_constant_declaration(statement.condition)
        else:
            condition = statement.condition
            self.infer_type(condition, supertype=nodes.BuiltinType.bool)
        self.env.inc_nesting()
        body = self.analyze_ast(statement.body)
        self.env.dec_nesting()
        elifs = []
        for elif_condition, elif_body in statement.elifs:
            if isinstance(elif_condition, nodes.ConstantDeclaration):
                cond: nodes.Expression = self.analyze_constant_declaration(elif_condition)
            else:
                cond = elif_condition
                self.infer_type(cond, supertype=nodes.BuiltinType.bool)
            self.env.inc_nesting()
            elifs.append((cond, self.analyze_ast(elif_body)))
            self.env.dec_nesting()
        self.env.inc_nesting()
        else_ = self.analyze_ast(statement.else_)
        self.env.dec_nesting()
        return nodes.If(statement.line, condition, body, elifs, else_)

    def analyze_while_statement(self, statement: nodes.While) -> nodes.While:
        if isinstance(statement.condition, nodes.ConstantDeclaration):
            condition: nodes.Expression = self.analyze_constant_declaration(statement.condition)
        else:
            condition = statement.condition
            self.infer_type(condition, supertype=nodes.BuiltinType.bool)
        self.env.inc_nesting()
        body = self.analyze_ast(statement.body)
        self.env.dec_nesting()
        return nodes.While(statement.line, condition, body)

    def analyze_return(self, statement: nodes.Return) -> nodes.Return:
        assert self.function_return_types
        self.infer_type(statement.value, supertype=self.function_return_types[-1])
        return statement

    def analyze_break(self, statement: nodes.Break) -> nodes.Break:
        return statement

    def analyze_builtin_function_call(
            self, line: int, path: nodes.BuiltinFunc, args: t.List[nodes.Expression]
    ) -> nodes.FunctionCall:
        self.infer_type(nodes.FunctionCall(line, path, args))
        value = args[0]
        value_type = self.infer_type(value)
        if isinstance(value_type, nodes.BuiltinType) and value_type.value in (
                nodes.BuiltinType.i8.value, nodes.BuiltinType.u8.value):
            value = nodes.Cast(value, nodes.BuiltinType.i16)
        return nodes.FunctionCall(line, path, [value])

    def analyze_name_function_call(
            self, line: int, path: nodes.Name, args: t.List[nodes.Expression]
    ) -> nodes.FunctionCall:
        call = nodes.FunctionCall(line, path, args)
        self.infer_type(call)
        return call

    def check_name_reassignment(self, left: nodes.Name) -> None:
        if left.module:
            assert 0, "Module system is not supported"
        entry = self.env[left.member]
        # We assume that name checking was performed.
        assert entry is not None
        if isinstance(entry, entries.ConstantEntry):
            if entry.has_value:
                raise errors.AngelConstantReassignment(left, self.get_code(), self.get_code(entry.line))
            entry.has_value = True
        elif isinstance(entry, entries.VariableEntry):
            pass
        else:
            assert 0, f"Cannot reassign {type(entry)}"

    def infer_type(self, value: nodes.Expression, supertype: t.Optional[nodes.Type] = None) -> nodes.Type:
        self.type_checker.update_context(self.env, self.get_code())
        return self.type_checker.infer_type(value, supertype)

    def check_type(self, type_: nodes.Type) -> nodes.Type:
        self.type_checker.update_context(self.env, self.get_code())
        return self.type_checker.unify_types(type_, type_)

    def estimate_value(self, value: nodes.Expression) -> enodes.Expression:
        self.estimator.update_context(self.env)
        return self.estimator.estimate_expression(value)

    def get_code(self, line: int = 0):
        if not line:
            return errors.Code(self.lines[self.line - 1], self.line)
        return errors.Code(self.lines[line - 1], line)

    @property
    def supported_nodes(self):
        return set(subclass.__name__ for subclass in self.node_dispatcher.keys())
