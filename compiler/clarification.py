import enum
from typing import Iterable
from dataclasses import dataclass

from . import nodes
from .utils import submangle, mangle
from .context import Context


@dataclass
class Clarifier:
    context: Context

    def clarify_ast(self, ast: nodes.AST) -> Iterable[nodes.Node]:
        yield from (self.clarify_node(node) for node in ast)

    def clarify_node(self, node):
        if node is None:
            return None
        if isinstance(node, nodes.Name):
            for cls in (nodes.BuiltinType, nodes.BuiltinFunc, nodes.BoolLiteral, nodes.SpecialName, nodes.SpecialMethods):
                try:
                    result = cls(node.member)
                except ValueError:
                    continue
                else:
                    return result
            return mangle(node, self.context)
        elif isinstance(node, nodes.FieldDeclaration):
            value = None
            if node.value:
                value = self.clarify_node(node.value)
            return nodes.FieldDeclaration(
                node.line, submangle(node.name, self.context), self.clarify_node(node.type), value
            )
        elif isinstance(node, nodes.AlgebraicDeclaration):
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
                self.clarify_node(node.methods),
            )
        elif isinstance(node, nodes.MethodDeclaration):
            return nodes.MethodDeclaration(
                node.line, submangle(node.name, self.context), self.clarify_node(node.parameters),
                self.clarify_node(node.arguments), self.clarify_node(node.return_type), self.clarify_node(node.body)
            )
        elif isinstance(node, nodes.Field):
            base = self.clarify_node(node.base)
            if isinstance(base, nodes.BuiltinType) and (
                    base.value == nodes.BuiltinType.optional.value):
                return nodes.OptionalTypeConstructor(node.field.member)
            return nodes.Field(node.line, base, submangle(node.field, self.context))
        elif isinstance(node, nodes.FunctionCall):
            function_path = self.clarify_node(node.function_path)
            arguments = self.clarify_node(node.arguments)
            if isinstance(function_path, nodes.OptionalTypeConstructor):
                assert len(arguments) == 1
                return nodes.OptionalSomeCall(arguments[0])
            elif isinstance(function_path, nodes.Field):
                return nodes.MethodCall(node.line, function_path.base, function_path.field, arguments)
            return nodes.FunctionCall(node.line, function_path, arguments)
        elif isinstance(node, list):
            return [self.clarify_node(element) for element in node]
        elif isinstance(node, tuple):
            return tuple(self.clarify_node(element) for element in node)
        elif isinstance(node, (str, int, enum.Enum)):
            return node
        else:
            values = []
            for key, value in vars(node).items():
                values.append(self.clarify_node(value))
            return type(node)(*values)
