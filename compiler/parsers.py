import re
import typing as t
from dataclasses import dataclass
from itertools import zip_longest
from functools import partial

from . import nodes, errors
from .enums import DeclType


IDENTIFIER_REGEX = re.compile("[_]?[_]?[a-zA-Z][a-zA-Z0-9]*(?:__)?")
INTEGER_REGEX = re.compile("[0-9]+")


OPERATOR_PRIORITY = {
    nodes.Operator.add.value: 1,
    nodes.Operator.sub.value: 1,

    nodes.Operator.mul.value: 2,
    nodes.Operator.div.value: 2,

    nodes.Operator.eq_eq.value: 3,
    nodes.Operator.neq.value: 3,
    nodes.Operator.lt_eq.value: 3,
    nodes.Operator.gt_eq.value: 3,
    nodes.Operator.lt.value: 3,
    nodes.Operator.gt.value: 3,

    nodes.Operator.and_.value: 2,
    nodes.Operator.or_.value: 2,

    nodes.Operator.is_.value: 4,
}


def build_binary_expression(
        left: nodes.Expression, operator: nodes.Operator, right: nodes.Expression
) -> nodes.BinaryExpression:
    op_priority = OPERATOR_PRIORITY[operator.value]
    if isinstance(left, nodes.BinaryExpression) and isinstance(right, nodes.BinaryExpression):
        # a + b, +, c + d
        # a * b, +, c + d
        # a + c, *, c ** d
        left_priority = OPERATOR_PRIORITY[left.operator.value]
        right_priority = OPERATOR_PRIORITY[right.operator.value]
        if left_priority >= op_priority and right_priority > op_priority:
            # (a * b) + (c * d)
            # (a + b) + (c * d)
            return nodes.BinaryExpression(left, operator, right)
        elif left_priority >= op_priority >= right_priority:
            # ((a + b) + c) + d
            # ((a * b) + c) + d
            # ((a ** b) * c) + d
            return nodes.BinaryExpression(
                nodes.BinaryExpression(left, operator, right.left), right.operator, right.right
            )
        elif left_priority < op_priority and right_priority == op_priority:
            # a + ((b * c) * d)
            return nodes.BinaryExpression(
                left.left, left.operator, nodes.BinaryExpression(
                    nodes.BinaryExpression(left.right, operator, right.left),
                    right.operator, right.right
                )
            )
        elif left_priority < op_priority < right_priority:
            # a + (b * (c ** d))
            return nodes.BinaryExpression(
                left.left, left.operator, nodes.BinaryExpression(left.right, operator, right)
            )
        elif left_priority < op_priority and right_priority < op_priority:
            # (a + (b * c)) + d
            return nodes.BinaryExpression(
                nodes.BinaryExpression(
                    left.left, left.operator, nodes.BinaryExpression(left.right, operator, right.left)
                ), right.operator, right.right
            )
        else:
            assert 0, "UNKNOWN CASE"
    elif isinstance(left, nodes.BinaryExpression):
        left_priority = OPERATOR_PRIORITY[left.operator.value]
        if left_priority < op_priority:
            # a + (b * c)
            return nodes.BinaryExpression(
                left.left, left.operator, nodes.BinaryExpression(left.right, operator, right)
            )
        elif left_priority >= op_priority:
            # (a + b) + c
            return nodes.BinaryExpression(left, operator, right)
        else:
            assert 0, "UNKNOWN CASE"
    elif isinstance(right, nodes.BinaryExpression):
        right_priority = OPERATOR_PRIORITY[right.operator.value]
        if op_priority < right_priority:
            # a + (b * c)
            return nodes.BinaryExpression(left, operator, right)
        elif op_priority >= right_priority:
            # (a + b) + c
            return nodes.BinaryExpression(
                nodes.BinaryExpression(left, operator, right.left),
                right.operator, right.right
            )
        else:
            assert 0, "UNKNOWN  CASE"
    else:
        return nodes.BinaryExpression(left, operator, right)


@dataclass
class Trailer:
    line: int


@dataclass
class TupleTrailer(Trailer):
    arguments: t.List[nodes.Expression]


@dataclass
class FieldTrailer(Trailer):
    field: nodes.Name


@dataclass
class SubscriptTrailer(Trailer):
    index: nodes.Expression


@dataclass
class CastTrailer(Trailer):
    to_type: nodes.Type


class OptionalTypeTrailer(Trailer):
    pass


@dataclass
class GenericTypeTrailer(Trailer):
    parameters: t.List[nodes.Type]


@dataclass
class NamedArgumentTrailer(Trailer):
    value: nodes.Expression


@dataclass
class State:
    idx: int
    position: nodes.Position


class Parser:
    code: str
    code_lines: t.List[str]
    idx: int
    indentation_level: int
    position: nodes.Position
    additional_statement_parsers: t.List[t.Callable[[], t.Optional[nodes.Node]]]

    def __init__(self):
        self.base_body_parsers = [
            self.parse_constant_declaration, self.parse_variable_declaration,
            self.parse_while_statement, self.parse_for_statement, self.parse_if_statement,
            self.parse_assignment, self.parse_function_call
        ]

    def parse(self, string: str) -> nodes.AST:
        self.code = string
        self.code_lines = string.split("\n")
        self.idx = 0
        self.indentation_level = 0
        self.position = nodes.Position()
        self.additional_statement_parsers = []

        result = []
        self.spaces()
        node = self.parse_node()
        while node is not None:
            result.append(node)
            self.spaces()
            node = self.parse_node()
        if not self.is_eof():
            raise errors.AngelSyntaxError("expected a statement", self.get_code())
        return result

    def parse_variable_declaration(self) -> t.Optional[nodes.Decl]:
        line = self.position.line
        if not self.parse_keyword("var"):
            return None
        name, type_, value = self.parse_constant_and_variable_common()
        return nodes.Decl(line, DeclType.variable, name, type_, value)

    def parse_constant_declaration(self) -> t.Optional[nodes.Decl]:
        line = self.position.line
        if not self.parse_keyword("let"):
            return None
        name, type_, value = self.parse_constant_and_variable_common()
        return nodes.Decl(line, DeclType.constant, name, type_, value)

    def parse_constant_and_variable_common(
        self
    ) -> t.Tuple[nodes.Name, t.Optional[nodes.Type], t.Optional[nodes.Expression]]:
        self.spaces()
        name = self.parse_name()
        if not name:
            raise errors.AngelSyntaxError("expected name", self.get_code())
        if self.parse_raw(":"):
            self.spaces()
            type_ = self.parse_type()
            if not type_:
                raise errors.AngelSyntaxError("expected type", self.get_code())
            state = self.backup_state()
            self.spaces()
            if self.parse_raw("="):
                self.spaces()
                value = self.parse_expression()
                if not value:
                    raise errors.AngelSyntaxError("expected expression", self.get_code())
                return name, type_, value
            else:
                self.restore_state(state)
                return name, type_, None
        else:
            self.spaces()
            if not self.parse_raw("="):
                raise errors.AngelSyntaxError("expected '=' (or ':' but without spaces)", self.get_code())
            self.spaces()
            value = self.parse_expression()
            if not value:
                raise errors.AngelSyntaxError("expected expression", self.get_code())
            return name, None, value

    def parse_function_call(self) -> t.Optional[nodes.FunctionCall]:
        state = self.backup_state()
        call = self.parse_expression()
        if call is None:
            return None
        if isinstance(call, nodes.FunctionCall):
            return call
        else:
            self.restore_state(state)
            return None

    def parse_assignment(self) -> t.Optional[nodes.Assignment]:
        state = self.backup_state()
        line = self.position.line
        left = self.parse_assignment_left()
        if left is None:
            return None
        elif isinstance(left, nodes.NamedArgument):
            return nodes.Assignment(line, left.name, nodes.Operator.eq, left.value)
        self.spaces()
        operator = self.parse_assignment_operator()
        if operator is None:
            self.restore_state(state)
            return None
        self.spaces()
        right = self.parse_expression()
        if right is None:
            raise errors.AngelSyntaxError("expected expression", self.get_code())
        return nodes.Assignment(line, left, operator, right)

    def parse_for_statement(self) -> t.Optional[nodes.For]:
        line = self.position.line
        if not self.parse_raw("for"):
            return None
        self.spaces()
        element = self.parse_name()
        if not element:
            raise errors.AngelSyntaxError("expected name", self.get_code())
        self.spaces()
        if not self.parse_raw("in"):
            raise errors.AngelSyntaxError("expected 'in'", self.get_code())
        self.spaces()
        container = self.parse_expression()
        if not container:
            raise errors.AngelSyntaxError("expected expression", self.get_code())
        body = self._parse_loop_body()
        return nodes.For(line, element, container, body)

    def _parse_loop_body(self) -> nodes.AST:
        if not self.parse_raw(":"):
            raise errors.AngelSyntaxError("expected ':'", self.get_code())
        self.additional_statement_parsers.append(self.parse_break)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return body

    def parse_while_statement(self) -> t.Optional[nodes.While]:
        line = self.position.line
        if not self.parse_raw("while"):
            return None
        self.spaces()
        condition = self.parse_if_condition()
        body = self._parse_loop_body()
        return nodes.While(line, condition, body)

    def _parse_conditional_common(self) -> t.Tuple[nodes.Expression, nodes.AST]:
        self.spaces()
        condition = self.parse_if_condition()
        if not self.parse_raw(":"):
            raise errors.AngelSyntaxError("expected ':'", self.get_code())
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return condition, body

    def parse_if_statement(self) -> t.Optional[nodes.If]:
        line = self.position.line
        if not self.parse_raw("if"):
            return None
        condition, body = self._parse_conditional_common()
        elifs = []
        state = self.backup_state()
        self.spaces()
        while self.parse_raw("elif"):
            elifs.append(self._parse_conditional_common())
            state = self.backup_state()
            self.spaces()
        else_: nodes.AST = []
        if self.parse_raw("else:"):
            else_ = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
            if not else_:
                raise errors.AngelSyntaxError("expected statement", self.get_code())
        elif elifs:
            self.restore_state(state)
        if not elifs and not else_:
            self.restore_state(state)
        return nodes.If(line, condition, body, elifs, else_)

    def parse_if_condition(self) -> nodes.Expression:
        condition: t.Optional[nodes.Expression] = self.parse_constant_declaration()
        if isinstance(condition, nodes.Decl) and condition.is_constant:
            assert condition.value is not None
            return condition
        else:
            condition = self.parse_expression()
            if condition is None:
                raise errors.AngelSyntaxError("expected expression or 'let'", self.get_code())
            return condition

    def parse_init_call(self) -> t.Optional[nodes.Node]:
        line = self.position.line
        state = self.backup_state()
        if not self.parse_raw('init'):
            return None
        arguments = self.parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self.parse_expression)
        if arguments is None:
            self.restore_state(state)
            return None
        return nodes.InitCall(line, arguments)

    def parse_init_declaration(self) -> t.Optional[nodes.InitDeclaration]:
        line = self.position.line
        if not self.parse_raw("init"):
            return None
        arguments: t.Optional[nodes.Arguments] = self.parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self.parse_argument)
        if arguments is None:
            arguments = []
        if not self.parse_raw(":"):
            raise errors.AngelSyntaxError("expected ':'", self.get_code())
        self.additional_statement_parsers = [self.parse_init_call] + self.additional_statement_parsers
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers = self.additional_statement_parsers[1:]
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return nodes.InitDeclaration(line, arguments, body)

    def parse_function_declaration(self) -> t.Optional[nodes.FunctionDeclaration]:
        line = self.position.line
        if not self.parse_raw("fun"):
            return None
        self.spaces()
        name = self.parse_name()
        if name is None:
            raise errors.AngelSyntaxError("expected name", self.get_code())
        parameters: t.Optional[nodes.Parameters] = self.parse_container(
            open_container="<", close_container=">", element_separator=",", element_parser=self.parse_name
        )
        if parameters is None:
            parameters = []
        arguments: t.Optional[nodes.Arguments] = self.parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self.parse_argument
        )
        if arguments is None:
            arguments = []
        self.spaces()
        if self.parse_raw("->"):
            self.spaces()
            return_type = self.parse_type()
            if return_type is None:
                raise errors.AngelSyntaxError("expected type", self.get_code())
        else:
            return_type = nodes.BuiltinType.void
        where_clause = self.parse_where_clause()
        if not self.parse_raw(":"):
            return nodes.FunctionDeclaration(line, name, parameters, arguments, return_type, where_clause, [])
        self.additional_statement_parsers.append(self.parse_return_statement)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return nodes.FunctionDeclaration(line, name, parameters, arguments, return_type, where_clause, body)

    def parse_return_statement(self) -> t.Optional[nodes.Return]:
        line = self.position.line
        if not self.parse_raw("return"):
            return None
        self.spaces()
        value = self.parse_expression()
        if value is None:
            raise errors.AngelSyntaxError("expected expression", self.get_code())
        return nodes.Return(line, value)

    def parse_break(self) -> t.Optional[nodes.Break]:
        line = self.position.line
        if not self.parse_raw("break"):
            return None
        return nodes.Break(line)

    def parse_field_declaration(self) -> t.Optional[nodes.FieldDeclaration]:
        line = self.position.line
        state = self.backup_state()
        name = self.parse_name()
        if name is None:
            return None
        if not self.parse_raw(":"):
            self.restore_state(state)
            return None
        self.spaces()
        type_ = self.parse_type()
        if type_ is None:
            raise errors.AngelSyntaxError("expected type", self.get_code())
        new_state = self.backup_state()
        self.spaces()
        if not self.parse_raw("="):
            self.restore_state(new_state)
            return nodes.FieldDeclaration(line, name, type_, value=None)
        self.spaces()
        value = self.parse_expression()
        if value is None:
            raise errors.AngelSyntaxError("expected expression", self.get_code())
        return nodes.FieldDeclaration(line, name, type_, value)

    def _parse_implemented_interfaces(self) -> t.List[nodes.Interface]:
        backup_state = self.backup_state()
        self.spaces()
        if self.parse_raw("is"):
            self.spaces()
            interfaces = self.parse_elements(
                element_separator=",", element_parser=self.parse_parent_interface, chars_ending_sequence=":",
                raise_error=False
            )
        else:
            self.restore_state(backup_state)
            interfaces = []
        return interfaces

    def _parse_struct_common(self) -> t.Tuple[nodes.Name, t.List[nodes.Name], t.List[nodes.Interface]]:
        self.spaces()
        name = self.parse_name()
        if name is None:
            raise errors.AngelSyntaxError("expected name", self.get_code())
        parameters = self.parse_container(
            open_container="<", close_container=">", element_separator=",", element_parser=self.parse_name)
        if parameters is None:
            parameters = []
        interfaces = self._parse_implemented_interfaces()
        return name, parameters, interfaces

    def parse_struct_declaration(self) -> t.Optional[nodes.StructDeclaration]:
        line = self.position.line
        if not self.parse_raw("struct"):
            return None
        name, parameters, interfaces = self._parse_struct_common()
        if not self.parse_raw(":"):
            return self.make_struct_declaration(line, name, parameters, interfaces, [])
        self.additional_statement_parsers.append(self.parse_init_declaration)
        self.additional_statement_parsers.append(self.parse_function_declaration)
        self.additional_statement_parsers.append(self.parse_field_declaration)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        self.additional_statement_parsers.pop()
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return self.make_struct_declaration(line, name, parameters, interfaces, body)

    def parse_extension_declaration(self) -> t.Optional[nodes.ExtensionDeclaration]:
        line = self.position.line
        if not self.parse_raw("extension"):
            return None
        name, parameters, interfaces = self._parse_struct_common()
        where_clause = self.parse_where_clause()
        if not self.parse_raw(":"):
            return self.make_extension_declaration(line, name, parameters, interfaces, where_clause, [])
        self.additional_statement_parsers.append(self.parse_function_declaration)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return self.make_extension_declaration(line, name, parameters, interfaces, where_clause, body)

    def parse_where_clause(self) -> t.Optional[nodes.Expression]:
        state = self.backup_state()
        self.spaces()
        if not self.parse_raw("where"):
            self.restore_state(state)
            return None
        self.spaces()
        condition = self.parse_expression()
        if condition is None:
            raise errors.AngelSyntaxError("expected condition after 'where'", self.get_code())
        return condition

    def parse_algebraic_declaration(self) -> t.Optional[nodes.AlgebraicDeclaration]:
        line = self.position.line
        if not self.parse_raw("algebraic"):
            return None
        self.spaces()
        name = self.parse_name()
        if name is None:
            raise errors.AngelSyntaxError("expected name", self.get_code())
        parameters: nodes.Parameters = []
        if not self.parse_raw(":"):
            return self.make_algebraic_declaration(line, name, parameters, [])
        self.additional_statement_parsers.append(self.parse_struct_declaration)
        self.additional_statement_parsers.append(self.parse_function_declaration)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return self.make_algebraic_declaration(line, name, parameters, body)

    def parse_interface_declaration(self) -> t.Optional[nodes.InterfaceDeclaration]:
        line = self.position.line
        if not self.parse_raw("interface"):
            return None
        self.spaces()
        name = self.parse_name()
        if name is None:
            raise errors.AngelSyntaxError("expected name", self.get_code())
        parameters: nodes.Parameters = []
        implemented_interfaces = self._parse_implemented_interfaces()
        if not self.parse_raw(":"):
            return self.make_interface_declaration(line, name, parameters, implemented_interfaces, [])
        self.additional_statement_parsers.append(self.parse_field_declaration)
        self.additional_statement_parsers.append(self.parse_function_declaration)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return self.make_interface_declaration(line, name, parameters, implemented_interfaces, body)

    NODE_PARSERS = [
        parse_constant_declaration, parse_variable_declaration, parse_function_declaration, parse_struct_declaration,
        parse_algebraic_declaration, parse_interface_declaration, parse_extension_declaration,
        parse_while_statement, parse_for_statement, parse_if_statement, parse_assignment, parse_function_call
    ]

    def _decide_method_scope(self, node: nodes.FunctionDeclaration, methods: nodes.DeclaredMethods):
        method_declaration = nodes.MethodDeclaration(
            node.line, node.name, node.parameters, node.arguments, node.return_type, node.body
        )
        if node.name.member.startswith("__") or node.name.member == "as":
            methods.special.append(method_declaration)
        elif node.name.member.startswith("_"):
            methods.private.append(method_declaration)
        else:
            methods.public.append(method_declaration)

    def make_struct_declaration(
        self, line: int, name: nodes.Name, parameters: nodes.Parameters, interfaces: nodes.Interfaces, body: nodes.AST
    ) -> nodes.StructDeclaration:
        init_declarations = []
        fields = nodes.DeclaredFields()
        methods = nodes.DeclaredMethods()
        for node in body:
            if isinstance(node, nodes.FieldDeclaration):
                if node.name.member.startswith("_"):
                    fields.private.append(node)
                else:
                    fields.public.append(node)
            elif isinstance(node, nodes.FunctionDeclaration):
                self._decide_method_scope(node, methods)
            elif isinstance(node, nodes.InitDeclaration):
                init_declarations.append(node)
            else:
                raise errors.AngelSyntaxError("expected method, field or init declaration", self.get_code(node.line))
        return nodes.StructDeclaration(
            line, name, parameters, interfaces, fields, init_declarations, methods
        )

    def make_extension_declaration(
        self, line: int, name: nodes.Name, parameters: nodes.Parameters, interfaces: nodes.Interfaces,
        where_clause: t.Optional[nodes.Expression], body: nodes.AST
    ) -> nodes.ExtensionDeclaration:
        methods = nodes.DeclaredMethods()
        for node in body:
            if isinstance(node, nodes.FunctionDeclaration):
                self._decide_method_scope(node, methods)
            else:
                raise errors.AngelSyntaxError("expected method declaration", self.get_code(node.line))
        return nodes.ExtensionDeclaration(line, name, parameters, interfaces, where_clause, methods)

    def make_algebraic_declaration(
        self, line: int, name: nodes.Name, parameters: nodes.Parameters, body: nodes.AST
    ) -> nodes.AlgebraicDeclaration:
        constructors = []
        methods = nodes.DeclaredMethods()
        for node in body:
            if isinstance(node, nodes.StructDeclaration):
                constructors.append(node)
            elif isinstance(node, nodes.FunctionDeclaration):
                self._decide_method_scope(node, methods)
            else:
                raise errors.AngelSyntaxError("expected method or constructor declaration", self.get_code(node.line))
        return nodes.AlgebraicDeclaration(line, name, parameters, constructors, methods)

    def make_interface_declaration(
        self, line: int, name: nodes.Name, parameters: nodes.Parameters, implemented_interfaces: nodes.Interfaces,
        body: nodes.AST
    ) -> nodes.InterfaceDeclaration:
        methods, fields = [], []
        for node in body:
            if isinstance(node, nodes.FunctionDeclaration):
                method_declaration = nodes.MethodDeclaration(
                    node.line, node.name, node.parameters, node.arguments, node.return_type, node.body
                )
                methods.append(method_declaration)
            elif isinstance(node, nodes.FieldDeclaration):
                fields.append(node)
            else:
                raise errors.AngelSyntaxError("expected method or field declaration", self.get_code(node.line))
        return nodes.InterfaceDeclaration(line, name, parameters, implemented_interfaces, fields, methods)

    def parse_body(self, statement_parsers) -> nodes.AST:
        def mega_parser() -> t.Optional[nodes.Node]:
            for parser in statement_parsers:
                parsed = parser()
                if parsed is not None:
                    return parsed
            return None

        self.indentation_level += 1
        result: nodes.AST = []
        state = self.backup_state()
        indentation = self.parse_indentation()
        if not indentation:
            self.restore_state(state)
            self.indentation_level -= 1
            return result
        node = mega_parser()
        while node is not None:
            result.append(node)
            state = self.backup_state()
            indentation = self.parse_indentation()
            if not indentation:
                self.restore_state(state)
                break
            node = mega_parser()
        self.indentation_level -= 1
        return result

    def parse_indentation(self) -> bool:
        result = []
        for char in self.code[self.idx:]:
            if char == "\n":
                result.append(char)
                self.idx += 1
                self.position.line += 1
                self.position.column = 1
            elif char.isspace():
                result.append(char)
                self.idx += 1
                self.position.column += 1
            else:
                break

        expected_indentation = nodes.INDENTATION * self.indentation_level
        return ''.join(result).endswith(expected_indentation)

    def parse_argument(self) -> t.Optional[nodes.Argument]:
        name = self.parse_name()
        if name is None:
            return None
        if not self.parse_raw(":"):
            raise errors.AngelSyntaxError("expected name", self.get_code())
        self.spaces()
        type_ = self.parse_type()
        if type_ is None:
            raise errors.AngelSyntaxError("expected type", self.get_code())
        return nodes.Argument(name, type_)

    def parse_assignment_left(self) -> t.Optional[nodes.AssignmentLeft]:
        state = self.backup_state()
        atom: t.Optional[nodes.Expression] = self.parse_name()
        if atom is None:
            return None
        trailer = self.parse_trailer()
        while trailer is not None:
            if isinstance(trailer, FieldTrailer):
                atom = nodes.Field(trailer.line, atom, trailer.field)
            elif isinstance(trailer, SubscriptTrailer):
                atom = nodes.Subscript(trailer.line, atom, trailer.index)
            elif isinstance(trailer, NamedArgumentTrailer):
                assert isinstance(atom, nodes.AssignmentLeft)
                atom = nodes.NamedArgument(atom, trailer.value)
            else:
                self.restore_state(state)
                return None
            trailer = self.parse_trailer()
        return t.cast(nodes.AssignmentLeft, atom)

    def parse_assignment_operator(self) -> t.Optional[nodes.Operator]:
        for operator in nodes.Operator.assignment_operators():
            if self.parse_raw(operator.value):
                return operator
        return None

    def parse_elements(
        self, element_separator: str, element_parser: t.Callable[[], t.Any],
        chars_ending_sequence: t.Optional[str] = None, raise_error: bool = True
    ) -> t.List[t.Any]:
        if chars_ending_sequence is None:
            chars_ending_sequence = ""

        result = []
        element = element_parser()
        while element is not None:
            result.append(element)
            if not self.parse_raw(element_separator) and \
                    not any(self.next_nonspace_char_is(char) for char in chars_ending_sequence):
                if raise_error:
                    raise errors.AngelSyntaxError(
                        f"expected '{element_separator}' or any char in '{chars_ending_sequence}'", self.get_code()
                    )
                return result
            self.spaces()
            element = element_parser()
        return result

    def parse_container(
        self, open_container: str, close_container: str, element_separator: str, element_parser: t.Callable[[], t.Any]
    ) -> t.Optional[t.List[t.Any]]:
        if not self.parse_raw(open_container):
            return None
        result = self.parse_elements(element_separator, element_parser, chars_ending_sequence=close_container)
        if not self.parse_raw(close_container):
            raise errors.AngelSyntaxError(f"expected '{close_container}'", self.get_code())
        return result

    def parse_node(self) -> t.Optional[nodes.Node]:
        for parser in self.NODE_PARSERS:
            node = t.cast(t.Callable[..., t.Optional[nodes.Node]], parser)(self)
            if node is not None:
                return node
        return None

    def is_eof(self) -> bool:
        return self.code[self.idx:] == ""

    def parse_parent_interface(self) -> t.Optional[nodes.Interface]:
        raw = self.parse_type()
        if raw is None:
            return None
        assert isinstance(raw, (nodes.Name, nodes.GenericType))
        return raw

    def parse_type(self) -> t.Optional[nodes.Type]:
        inner_type = self.parse_type_atom_with_prefixes()
        if inner_type is None:
            return None
        type_trailer = self.parse_type_trailer()
        while type_trailer is not None:
            if isinstance(type_trailer, OptionalTypeTrailer):
                inner_type = nodes.OptionalType(inner_type)
            elif isinstance(type_trailer, GenericTypeTrailer):
                assert isinstance(inner_type, nodes.Name)
                inner_type = nodes.GenericType(inner_type, type_trailer.parameters)
            else:
                raise errors.AngelNotImplemented
            type_trailer = self.parse_type_trailer()
        return inner_type

    def parse_type_trailer(self) -> t.Optional[Trailer]:
        if self.parse_raw("?"):
            return OptionalTypeTrailer(self.position.line)
        parameters = self.parse_container('<', '>', ',', element_parser=self.parse_type)
        if parameters:
            return GenericTypeTrailer(self.position.line, parameters)
        return None

    def parse_type_atom_with_prefixes(self) -> t.Optional[nodes.Type]:
        if self.parse_raw('ref'):
            self.spaces()
            value_type = self.parse_type()
            if value_type is None:
                raise errors.AngelSyntaxError('expected type', self.get_code())
            return nodes.RefType(value_type)
        return self.parse_type_atom()

    def parse_type_atom(self) -> t.Optional[nodes.Type]:
        for parser in [self.parse_vector_or_dict_type, self.parse_name]:
            result = parser()
            if result is not None:
                return result
        return None

    def parse_vector_or_dict_type(self) -> t.Optional[nodes.Type]:
        if not self.parse_raw("["):
            return None
        subtype = self.parse_type()
        if subtype is None:
            raise errors.AngelSyntaxError("expected type", self.get_code())
        if self.parse_raw(":"):
            self.spaces()
            value_type = self.parse_type()
            if value_type is None:
                raise errors.AngelSyntaxError("expected type", self.get_code())
            if not self.parse_raw("]"):
                raise errors.AngelSyntaxError("expected ']'", self.get_code())
            return nodes.DictType(subtype, value_type)
        elif not self.parse_raw("]"):
            raise errors.AngelSyntaxError("expected ']'", self.get_code())
        return nodes.VectorType(subtype)

    def parse_binary_expression(self, left_parser, operators, right_parser) -> t.Optional[nodes.Expression]:
        left = left_parser()
        if left is None:
            return None
        state = self.backup_state()
        self.spaces()
        got_op = None
        for operator in operators:
            if self.parse_raw(operator.value):
                got_op = operator
                break
        if got_op is None:
            self.restore_state(state)
            return left
        self.spaces()
        right = right_parser()
        if right is None:
            raise errors.AngelSyntaxError("expected expression", self.get_code())
        return build_binary_expression(left, got_op, right)

    def parse_expression(self) -> t.Optional[nodes.Expression]:
        return self.parse_boolean_expression()

    def parse_boolean_expression(self) -> t.Optional[nodes.Expression]:
        return self.parse_binary_expression(
            self.parse_expression_comparison, nodes.Operator.higher_order_boolean_operators(),
            self.parse_boolean_expression
        )

    def parse_expression_comparison(self) -> t.Optional[nodes.Expression]:
        return self.parse_binary_expression(
            self.parse_expression_subexpression, nodes.Operator.comparison_operators(), self.parse_expression_comparison
        )

    def parse_expression_subexpression(self) -> t.Optional[nodes.Expression]:
        return self.parse_binary_expression(
            self.parse_expression_term, (nodes.Operator.sub, nodes.Operator.add), self.parse_expression_subexpression
        )

    def parse_expression_term(self) -> t.Optional[nodes.Expression]:
        return self.parse_binary_expression(
            self.parse_expression_atom_with_trailers, (nodes.Operator.mul, nodes.Operator.div),
            self.parse_expression_term
        )

    def parse_expression_atom_with_trailers(self) -> t.Optional[nodes.Expression]:
        atom = self.parse_expression_atom_with_prefixes()
        if atom is None:
            return None
        trailer = self.parse_trailer()
        while trailer is not None:
            if isinstance(trailer, TupleTrailer):
                atom = nodes.FunctionCall(trailer.line, atom, trailer.arguments)
            elif isinstance(trailer, FieldTrailer):
                atom = nodes.Field(trailer.line, atom, trailer.field)
            elif isinstance(trailer, SubscriptTrailer):
                atom = nodes.Subscript(trailer.line, atom, trailer.index)
            elif isinstance(trailer, CastTrailer):
                atom = nodes.Cast(atom, trailer.to_type)
            elif isinstance(trailer, NamedArgumentTrailer):
                assert isinstance(atom, nodes.AssignmentLeft)
                atom = nodes.NamedArgument(atom, trailer.value)
            else:
                raise errors.AngelNotImplemented
            trailer = self.parse_trailer()
        return atom

    def parse_expression_atom_with_prefixes(self) -> t.Optional[nodes.Expression]:
        if self.parse_raw('ref'):
            self.spaces()
            # ref 1 + 2 corresponds to (ref 1) + 2
            value = self.parse_expression_atom_with_trailers()
            if value is None:
                raise errors.AngelSyntaxError('expected expression', self.get_code())
            return nodes.Ref(value)
        elif self.parse_raw('('):
            self.spaces()
            expr = self.parse_expression()
            if not expr:
                raise errors.AngelSyntaxError('expected expression', self.get_code())
            if not self.parse_raw(')'):
                raise errors.AngelSyntaxError("expected ')'", self.get_code())
            return nodes.Parentheses(expr)
        return self.parse_expression_atom()

    def parse_expression_atom(self) -> t.Optional[nodes.Expression]:
        literal_parsers = [
            self.parse_number_literal, self.parse_vector_or_dict_literal, self.parse_char_literal,
            self.parse_string_literal, self.parse_name
        ]
        for parser in literal_parsers:
            result = parser()
            if result is not None:
                return result
        return None

    def parse_trailer(self) -> t.Optional[Trailer]:
        line = self.position.line
        state = self.backup_state()
        arguments = self.parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self.parse_expression)
        if arguments is None:
            if self.parse_raw("."):
                field = self.parse_identifier()
                if not field:
                    raise errors.AngelSyntaxError("expected identifier", self.get_code())
                return FieldTrailer(line, nodes.Name(field))
            elif self.parse_raw("["):
                index = self.parse_expression()
                if not index:
                    raise errors.AngelSyntaxError("expected expression", self.get_code())
                if not self.parse_raw("]"):
                    raise errors.AngelSyntaxError("expected ']'", self.get_code())
                return SubscriptTrailer(line, index)
            self.spaces()
            if self.parse_raw("as"):
                self.spaces()
                to_type = self.parse_type()
                if not to_type:
                    raise errors.AngelSyntaxError("expected type", self.get_code())
                return CastTrailer(line, to_type)
            elif self.parse_raw('=') and self.next_char_isspace():
                self.spaces()
                value = self.parse_expression()
                if not value:
                    raise errors.AngelSyntaxError('expected expression', self.get_code())
                return NamedArgumentTrailer(line, value)
            else:
                self.restore_state(state)
            return None
        return TupleTrailer(line, arguments)

    def parse_comparison_operator(self) -> t.Optional[nodes.Operator]:
        for operator in nodes.Operator.comparison_operators():
            if self.parse_raw(operator.value):
                return operator
        return None

    def parse_vector_or_dict_literal(self) -> t.Optional[nodes.Expression]:
        if self.parse_raw("[:]"):
            return nodes.DictLiteral([], [])
        elements = self.parse_container(
            open_container="[", close_container="]", element_separator=",",
            element_parser=self.parse_vector_or_dict_element
        )
        if elements is None:
            return None
        type_of_element = None
        keys, values = [], []
        for element in elements:
            if isinstance(element, tuple):
                keys.append(element[0])
                values.append(element[1])
            if type_of_element is None:
                type_of_element = type(element)
            elif not isinstance(element, type_of_element):
                raise errors.AngelSyntaxError("unknown container", self.get_code())
        if type_of_element is None or type_of_element != tuple:
            return nodes.VectorLiteral(elements)
        return nodes.DictLiteral(keys, values)

    def parse_vector_or_dict_element(
        self
    ) -> t.Optional[t.Union[nodes.Expression, t.Tuple[nodes.Expression, nodes.Expression]]]:
        key = self.parse_expression()
        if key is None:
            return key
        if self.parse_raw(":"):
            self.spaces()
            value = self.parse_expression()
            if value is None:
                raise errors.AngelSyntaxError("expected expression", self.get_code())
            return key, value
        return key

    def parse_number_literal(self) -> t.Optional[t.Union[nodes.IntegerLiteral, nodes.DecimalLiteral]]:
        integer = self.parse_integer_literal()
        if integer is None:
            return None
        if not self.parse_raw("."):
            return integer
        fractional = self.parse_integer_literal(unary_operators=False)
        if not fractional:
            raise errors.AngelSyntaxError("expected fractional part", self.get_code())
        return nodes.DecimalLiteral(integer.value + "." + fractional.value)

    def parse_integer_literal(self, unary_operators: bool = True) -> t.Optional[nodes.IntegerLiteral]:
        state = self.backup_state()
        minuses = []
        while unary_operators and self.parse_raw("-"):
            minuses.append("-")
        match = INTEGER_REGEX.match(self.code[self.idx:])
        if match is None:
            self.restore_state(state)
            return None
        match_length = len(match[0])
        self.idx += match_length
        self.position.column += match_length
        return nodes.IntegerLiteral("".join(minuses) + match[0])

    def parse_char_literal(self) -> t.Optional[nodes.CharLiteral]:
        if not self.parse_raw("'"):
            return None
        char = None
        for c in self.code[self.idx:]:
            char = c
            self.idx += 1
            self.position.column += 1
            break
        if char is None:
            raise errors.AngelSyntaxError("expected exactly one character", self.get_code())
        if not self.parse_raw("'"):
            raise errors.AngelSyntaxError('expected "\'"', self.get_code())
        return nodes.CharLiteral(char)

    def parse_string_literal(self) -> t.Optional[nodes.StringLiteral]:
        if not self.parse_raw('"'):
            return None
        result = []
        end_quote_seen = False
        for char in self.code[self.idx:]:
            self.idx += 1
            self.position.column += 1
            if char == '"':
                end_quote_seen = True
                break
            else:
                result.append(char)
        if end_quote_seen:
            return nodes.StringLiteral("".join(result))
        raise errors.AngelSyntaxError("expected '\"'", self.get_code())

    def parse_name(self) -> t.Optional[nodes.Name]:
        identifier = self.parse_identifier()
        if identifier:
            if self.parse_raw('#'):
                member = self.parse_identifier()
                if not member:
                    raise errors.AngelSyntaxError('expected identifier', self.get_code())
                return nodes.Name(member, identifier)
            return nodes.Name(identifier)
        return None

    def parse_identifier(self) -> str:
        match = IDENTIFIER_REGEX.match(self.code[self.idx:])
        if match is None:
            return ""
        match_length = len(match[0])
        self.idx += match_length
        self.position.column += match_length
        return match[0]

    def spaces(self) -> None:
        prepared_for_line_comment = False
        in_line_comment = False
        state = self.backup_state()
        for char in self.code[self.idx:]:
            if char == "\n":
                in_line_comment = False
                self.idx += 1
                self.position.line += 1
                self.position.column = 1
            elif char.isspace():
                self.idx += 1
                self.position.column += 1
            elif char == "/":
                state = self.backup_state()
                self.idx += 1
                self.position.column += 1
                if in_line_comment:
                    continue
                if prepared_for_line_comment:
                    in_line_comment = True
                    prepared_for_line_comment = False
                else:
                    prepared_for_line_comment = True
            elif in_line_comment:
                self.idx += 1
                self.position.column += 1
            else:
                if prepared_for_line_comment:
                    self.restore_state(state)
                break

    def parse_keyword(self, keyword: str) -> bool:
        state = self.backup_state()
        parsed_keyword_as_string = self.parse_raw(keyword)
        if parsed_keyword_as_string and not self.next_char_isspace():
            self.restore_state(state)
            return False
        return parsed_keyword_as_string

    def parse_raw(self, string: str) -> bool:
        state = self.backup_state()
        for expected, got in zip_longest(string, self.code[self.idx:]):
            if expected is None:
                break
            elif got is None:
                return False
            elif expected != got:
                return False
            state.idx += 1
            state.position.column += 1
        self.restore_state(state)
        return True

    def next_char_isspace(self) -> bool:
        return self.code[self.idx].isspace()

    def next_nonspace_char_is(self, expected: str) -> bool:
        for got in self.code[self.idx:]:
            if not got.isspace():
                return expected == got
        return False

    def backup_state(self) -> State:
        return State(idx=self.idx, position=nodes.Position(self.position.column, self.position.line))

    def restore_state(self, state: State) -> None:
        self.idx = state.idx
        self.position = state.position

    def get_code(self, line: t.Optional[int] = None, column: t.Optional[int] = None) -> errors.Code:
        if line is not None:
            return errors.Code(self.code_lines[line - 1], line, column)
        return errors.Code(self.code_lines[self.position.line - 1], self.position.line, self.position.column)
