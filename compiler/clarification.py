import enum
from dataclasses import dataclass

from . import nodes
from .utils import mangle
from .context import Context


@dataclass
class Clarifier:
    context: Context

    def clarify_ast(self, ast: nodes.AST) -> nodes.AST:
        return [self.clarify_node(node) for node in ast]

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
        elif isinstance(node, nodes.Field):
            base = self.clarify_node(node.base)
            if isinstance(base, nodes.BuiltinType) and (
                    base.value == nodes.BuiltinType.optional.value):
                return nodes.OptionalTypeConstructor(node.field.member)
            return nodes.Field(node.line, base, self.clarify_node(node.field))
        elif isinstance(node, nodes.FunctionCall):
            function_path = self.clarify_node(node.function_path)
            args = self.clarify_node(node.args)
            if isinstance(function_path, nodes.OptionalTypeConstructor):
                assert len(args) == 1
                return nodes.OptionalSomeCall(args[0])
            elif isinstance(function_path, nodes.Field):
                return nodes.MethodCall(node.line, function_path.base, function_path.field, args)
            return nodes.FunctionCall(node.line, function_path, args)
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
