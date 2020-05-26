import enum
from dataclasses import dataclass

from . import nodes
from .utils import dispatch, submangle, mangle, EXPRS
from .context import Context


@dataclass
class Clarifier:
    context: Context

    def __post_init__(self):
        self.get_module_from_expr_dispatcher = {
            nodes.Name: lambda name: name.module,
            nodes.FunctionCall: lambda call: self.get_module_from_expr(call.function_path),
        }

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
        elif isinstance(node, nodes.FieldDeclaration):
            value = None
            if node.value:
                value = self.clarify_node(node.value)
            return nodes.FieldDeclaration(
                node.line, submangle(node.name, self.context), self.clarify_node(node.type), value
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

    def get_module_from_expr(self, expr: nodes.Expression) -> str:
        return dispatch(self.get_module_from_expr_dispatcher, type(expr), expr)

    def test(self):
        self.assertEqual(EXPRS, set(subclass.__name__ for subclass in self.get_module_from_expr_dispatcher.keys()))
