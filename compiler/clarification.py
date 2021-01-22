import enum
from typing import Iterable

from . import nodes
from .utils import submangle, mangle
from .context import Context


class Clarifier:
    """Provides in-place node context by traversing the AST and replacing node objects with more specific ones."""

    def __init__(self, context: Context):
        self.context = context
        self._clarify_node_dispatcher = {
            nodes.Name: self._clarify_name,
            nodes.Field: self._clarify_field,
            nodes.FunctionCall: self._clarify_function_call,
            nodes.FieldDeclaration: self._clarify_field_declaration,
            nodes.MethodDeclaration: self._clarify_method_declaration,
            nodes.AlgebraicDeclaration: self._clarify_algebraic_declaration,

            (list, tuple): lambda node: type(node)(self.clarify_node(element) for element in node),
            (str, int, enum.Enum): lambda node: node,
        }
        self._name_enums = (
            nodes.BuiltinType, nodes.BuiltinFunc, nodes.BoolLiteral, nodes.SpecialName, nodes.SpecialMethods
        )

    def clarify_ast(self, ast: nodes.AST) -> Iterable[nodes.Node]:
        yield from (self.clarify_node(node) for node in ast)

    def clarify_node(self, node):
        if node is None:
            return None

        for types, handler in self._clarify_node_dispatcher.items():
            if isinstance(node, types):
                return handler(node)

        return type(node)(*(self.clarify_node(value) for value in vars(node).values()))

    def _clarify_name(self, node: nodes.Name):
        for cls in self._name_enums:
            try:
                result = cls(node.member)
            except ValueError:
                continue
            else:
                return result
        return mangle(node, self.context)

    def _clarify_field(self, node: nodes.Field):
        base = self.clarify_node(node.base)
        if isinstance(base, nodes.BuiltinType) and base.value == nodes.BuiltinType.optional.value:
            return nodes.OptionalTypeConstructor(node.field.member)
        return nodes.Field(node.line, base, submangle(node.field, self.context))

    def _clarify_function_call(self, node: nodes.FunctionCall):
        function_path = self.clarify_node(node.function_path)
        arguments = self.clarify_node(node.arguments)
        if isinstance(function_path, nodes.OptionalTypeConstructor):
            # TODO: replace assert with meaningful error handling and user-friendly message
            assert len(arguments) == 1
            return nodes.OptionalSomeCall(arguments[0])
        elif isinstance(function_path, nodes.Field):
            return nodes.MethodCall(node.line, function_path.base, function_path.field, arguments)
        return nodes.FunctionCall(node.line, function_path, arguments)

    def _clarify_field_declaration(self, node: nodes.FieldDeclaration):
        return nodes.FieldDeclaration(
            node.line, submangle(node.name, self.context), self.clarify_node(node.type), self.clarify_node(node.value)
        )

    def _clarify_method_declaration(self, node: nodes.MethodDeclaration):
        return nodes.MethodDeclaration(
            node.line, submangle(node.name, self.context), self.clarify_node(node.parameters),
            self.clarify_node(node.arguments), self.clarify_node(node.return_type), self.clarify_node(node.body)
        )

    def _clarify_algebraic_declaration(self, node: nodes.AlgebraicDeclaration):
        body = []
        for statement in node.constructors:
            if isinstance(statement, nodes.StructDeclaration):
                statement = nodes.StructDeclaration(
                    statement.line, submangle(statement.name, self.context),
                    self.clarify_node(statement.parameters), self.clarify_node(statement.interfaces),
                    self.clarify_node(statement.fields), self.clarify_node(statement.init_declarations),
                    self.clarify_node(statement.methods),
                )
            body.append(statement)
        return nodes.AlgebraicDeclaration(
            node.line, self.clarify_node(node.name), self.clarify_node(node.parameters), body,
            self.clarify_node(node.methods)
        )
