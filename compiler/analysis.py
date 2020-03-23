import typing as t
import unittest

from . import (
    nodes, estimation, type_checking, environment, estimation_nodes as enodes, errors, environment_entries as entries
)
from .utils import dispatch, NODES, ASSIGNMENTS


class Analyzer(unittest.TestCase):

    def __init__(self, lines: t.List[str], env: t.Optional[environment.Environment] = None):
        super().__init__()
        self.env = env or environment.Environment()
        self.lines = lines
        self.line = 0
        self.function_return_types: t.List[nodes.Type] = []

        self.type_checker = type_checking.TypeChecker()
        self.estimator = estimation.Estimator()

        self.assignment_dispatcher = {
            nodes.Name: self.check_name_reassignment,
            nodes.Field: self.check_field_reassignment,
        }

        self.node_dispatcher = {
            nodes.ConstantDeclaration: self.analyze_constant_declaration,
            nodes.VariableDeclaration: self.analyze_variable_declaration,
            nodes.FunctionDeclaration: self.analyze_function_declaration,
            nodes.StructDeclaration: self.analyze_struct_declaration,
            nodes.FieldDeclaration: self.analyze_field_declaration,
            nodes.MethodDeclaration: self.analyze_method_declaration,
            nodes.InitDeclaration: self.analyze_init_declaration,

            nodes.Assignment: self.analyze_assignment,
            nodes.If: self.analyze_if_statement,
            nodes.While: self.analyze_while_statement,
            nodes.Return: self.analyze_return,
            nodes.Break: self.analyze_break,
            nodes.FunctionCall: self.analyze_function_call,
            nodes.MethodCall: self.analyze_method_call,
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
        # list(...) for mypy
        private_fields = t.cast(t.List[nodes.FieldDeclaration], self.analyze_ast(list(declaration.private_fields)))
        public_fields = t.cast(t.List[nodes.FieldDeclaration], self.analyze_ast(list(declaration.public_fields)))
        init_declarations = self.generate_default_init(
            private_fields, public_fields, list(declaration.init_declarations)
        )
        init_declarations = t.cast(t.List[nodes.InitDeclaration], self.analyze_ast(init_declarations))
        private_methods = t.cast(t.List[nodes.MethodDeclaration], self.analyze_ast(list(declaration.private_methods)))
        public_methods = t.cast(t.List[nodes.MethodDeclaration], self.analyze_ast(list(declaration.public_methods)))
        self.env.dec_nesting(declaration.name)
        return nodes.StructDeclaration(
            declaration.line, declaration.name, private_fields, public_fields, init_declarations, private_methods,
            public_methods
        )

    def generate_default_init(self, private_fields, public_fields, init_declarations: t.List[nodes.InitDeclaration]):
        if not init_declarations:
            init_declaration_body: nodes.AST = []
            args = []
            for field in public_fields:
                args.append(nodes.Argument(field.name, field.type, field.value))
                init_declaration_body.append(
                    nodes.Assignment(
                        0, nodes.Field(0, nodes.SpecialName.self, field.name.member), nodes.Operator.eq, field.name
                    )
                )
            for field in private_fields:
                if field.value is None:
                    raise errors.AngelPrivateFieldsNotInitializedAndNoInit(field.name, self.get_code(field.line))
                init_declaration_body.append(
                    nodes.Assignment(
                        0, nodes.Field(0, nodes.SpecialName.self, field.name.member), nodes.Operator.eq, field.value
                    )
                )
            default_init_declaration = nodes.InitDeclaration(0, args, init_declaration_body)
            return [default_init_declaration] + init_declarations
        return init_declarations

    def analyze_field_declaration(self, declaration: nodes.FieldDeclaration) -> nodes.FieldDeclaration:
        if declaration.value:
            field_type = self.infer_type(declaration.value, declaration.type)
        else:
            field_type = self.check_type(declaration.type)
        self.env.add_field(declaration.line, declaration.name, field_type)
        return nodes.FieldDeclaration(declaration.line, declaration.name, field_type, declaration.value)

    def analyze_method_declaration(self, declaration: nodes.MethodDeclaration) -> nodes.MethodDeclaration:
        args = []
        for arg in declaration.args:
            if arg.value is not None:
                argument = nodes.Argument(arg.name, self.infer_type(arg.value, arg.type), arg.value)
            else:
                argument = nodes.Argument(arg.name, self.check_type(arg.type), arg.value)
            args.append(argument)
        return_type = self.check_type(declaration.return_type)
        self.env.add_method(declaration.line, declaration.name, args, return_type)
        self.env.inc_nesting()
        self.function_return_types.append(return_type)
        self.env.add_variable(
            declaration.line, nodes.Name(nodes.SpecialName.self.value), self.env.parents[-1], value=None
        )
        for arg in args:
            self.env.add_constant(declaration.line, arg.name, arg.type, value=None)
        body = self.analyze_ast(declaration.body)
        self.function_return_types.pop()
        self.env.dec_nesting()
        self.env.update_method_body(declaration.name, body)
        return nodes.MethodDeclaration(declaration.line, declaration.name, args, return_type, body)

    def analyze_init_declaration(self, declaration: nodes.InitDeclaration) -> nodes.InitDeclaration:
        args = []
        for arg in declaration.args:
            if arg.value is not None:
                argument = nodes.Argument(arg.name, self.infer_type(arg.value, arg.type), arg.value)
            else:
                argument = nodes.Argument(arg.name, self.check_type(arg.type), arg.value)
            args.append(argument)
        self.env.add_init_declaration(declaration.line, args)
        self.env.inc_nesting()
        self.env.add_variable(
            declaration.line, nodes.Name(nodes.SpecialName.self.value), self.env.parents[-1], value=None
        )
        for arg in args:
            self.env.add_constant(declaration.line, arg.name, arg.type, value=None)
        body = self.analyze_ast(declaration.body)
        self.env.dec_nesting()
        self.env.update_init_declaration_body(args, body)
        return nodes.InitDeclaration(declaration.line, args, body)

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

    def analyze_builtin_function_call(self, function_call: nodes.FunctionCall) -> nodes.FunctionCall:
        assert isinstance(function_call.function_path, nodes.BuiltinFunc)
        self.infer_type(function_call)
        value = function_call.args[0]
        value_type = self.infer_type(value)
        if isinstance(value_type, nodes.BuiltinType) and value_type.value in (
                nodes.BuiltinType.i8.value, nodes.BuiltinType.u8.value):
            value = nodes.Cast(value, nodes.BuiltinType.i16)
        return nodes.FunctionCall(function_call.line, function_call.function_path, [value])

    def analyze_function_call(self, function_call: nodes.FunctionCall) -> nodes.FunctionCall:
        if isinstance(function_call.function_path, nodes.BuiltinFunc):
            return self.analyze_builtin_function_call(function_call)
        self.infer_type(function_call)
        return function_call

    def analyze_method_call(self, method_call: nodes.MethodCall) -> nodes.MethodCall:
        self.infer_type(method_call)
        return method_call

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
            raise errors.AngelConstantReassignment(left, self.get_code(), self.get_code(entry.line))

    def check_field_reassignment(self, left: nodes.Field) -> None:
        # @WIP
        pass

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

    def test(self):
        self.assertEqual(NODES, set(subclass.__name__ for subclass in self.node_dispatcher.keys()))
        self.assertEqual(ASSIGNMENTS, set(subclass.__name__ for subclass in self.assignment_dispatcher.keys()))
