import re
import typing as t
from dataclasses import dataclass
from itertools import zip_longest

from . import nodes, errors


IDENTIFIER_REGEX = re.compile("[_]?[a-zA-Z][a-zA-Z0-9]*")
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
}


def build_binary_expression(
        left: nodes.Expression, operator: nodes.Operator, right: nodes.Expression
) -> nodes.Expression:
    if isinstance(right, nodes.BinaryExpression) and (
            OPERATOR_PRIORITY[operator.value] >= OPERATOR_PRIORITY[right.operator.value]):
        return nodes.BinaryExpression(nodes.BinaryExpression(left, operator, right.left), right.operator, right.right)
    return nodes.BinaryExpression(left, operator, right)


@dataclass
class Trailer:
    line: int


@dataclass
class TupleTrailer(Trailer):
    args: t.List[nodes.Expression]


@dataclass
class FieldTrailer(Trailer):
    field: str


@dataclass
class SubscriptTrailer(Trailer):
    index: nodes.Expression


class OptionalTypeTrailer(Trailer):
    pass


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
            self.parse_while_statement, self.parse_if_statement, self.parse_assignment, self.parse_function_call
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

    def parse_variable_declaration(self) -> t.Optional[nodes.VariableDeclaration]:
        line = self.position.line
        if not self.parse_keyword("var"):
            return None
        name, type_, value = self.parse_constant_and_variable_common()
        return nodes.VariableDeclaration(line, name, type_, value)

    def parse_constant_declaration(self) -> t.Optional[nodes.ConstantDeclaration]:
        line = self.position.line
        if not self.parse_keyword("let"):
            return None
        name, type_, value = self.parse_constant_and_variable_common()
        return nodes.ConstantDeclaration(line, name, type_, value)

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

    def parse_while_statement(self) -> t.Optional[nodes.While]:
        line = self.position.line
        if not self.parse_raw("while"):
            return None
        self.spaces()
        condition = self.parse_if_condition()
        if not self.parse_raw(":"):
            raise errors.AngelSyntaxError("expected ':'", self.get_code())
        self.additional_statement_parsers.append(self.parse_break)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return nodes.While(line, condition, body)

    def parse_if_statement(self) -> t.Optional[nodes.If]:
        line = self.position.line
        if not self.parse_raw("if"):
            return None
        self.spaces()
        condition = self.parse_if_condition()
        if not self.parse_raw(":"):
            raise errors.AngelSyntaxError("expected ':'", self.get_code())
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        elifs = []
        state = self.backup_state()
        self.spaces()
        while self.parse_raw("elif"):
            self.spaces()
            elif_condition = self.parse_if_condition()
            if not self.parse_raw(":"):
                raise errors.AngelSyntaxError("expected ':'", self.get_code())
            elif_body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
            if not elif_body:
                raise errors.AngelSyntaxError("expected statement", self.get_code())
            elifs.append((elif_condition, elif_body))
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
        if isinstance(condition, nodes.ConstantDeclaration):
            assert condition.value is not None
            return condition
        else:
            condition = self.parse_expression()
            if condition is None:
                raise errors.AngelSyntaxError("expected expression or 'let'", self.get_code())
            return condition

    def parse_init_declaration(self) -> t.Optional[nodes.InitDeclaration]:
        line = self.position.line
        if not self.parse_raw("init"):
            return None
        args: t.Optional[nodes.Arguments] = self.parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self.parse_argument)
        if args is None:
            args = []
        if not self.parse_raw(":"):
            raise errors.AngelSyntaxError("expected ':'", self.get_code())
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return nodes.InitDeclaration(line, args, body)

    def parse_function_declaration(self) -> t.Optional[nodes.FunctionDeclaration]:
        line = self.position.line
        if not self.parse_raw("fun"):
            return None
        self.spaces()
        name = self.parse_name()
        if name is None:
            raise errors.AngelSyntaxError("expected name", self.get_code())
        args: t.Optional[nodes.Arguments] = self.parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self.parse_argument)
        if args is None:
            args = []
        self.spaces()
        if self.parse_raw("->"):
            self.spaces()
            return_type = self.parse_type()
            if return_type is None:
                raise errors.AngelSyntaxError("expected type", self.get_code())
        else:
            return_type = nodes.BuiltinType.void
        if not self.parse_raw(":"):
            raise errors.AngelSyntaxError("expected ':'", self.get_code())
        self.additional_statement_parsers.append(self.parse_return_statement)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return nodes.FunctionDeclaration(line, name, args, return_type, body)

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

    def parse_struct_declaration(self) -> t.Optional[nodes.StructDeclaration]:
        line = self.position.line
        if not self.parse_raw("struct"):
            return None
        self.spaces()
        name = self.parse_name()
        if name is None:
            raise errors.AngelSyntaxError("expected name", self.get_code())
        parameters = self.parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self.parse_name)
        if parameters is None:
            parameters = []
        if not self.parse_raw(":"):
            return self.make_struct_declaration(line, name, parameters, [])
        self.additional_statement_parsers.append(self.parse_init_declaration)
        self.additional_statement_parsers.append(self.parse_function_declaration)
        self.additional_statement_parsers.append(self.parse_field_declaration)
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        self.additional_statement_parsers.pop()
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return self.make_struct_declaration(line, name, parameters, body)

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
        body = self.parse_body(self.additional_statement_parsers + self.base_body_parsers)
        self.additional_statement_parsers.pop()
        if not body:
            raise errors.AngelSyntaxError("expected statement", self.get_code())
        return self.make_algebraic_declaration(line, name, parameters, body)

    NODE_PARSERS = [
        parse_constant_declaration, parse_variable_declaration, parse_function_declaration, parse_struct_declaration,
        parse_algebraic_declaration, parse_while_statement, parse_if_statement, parse_assignment, parse_function_call
    ]

    def make_struct_declaration(
            self, line: int, name: nodes.Name, parameters: nodes.Parameters, body: nodes.AST
    ) -> nodes.StructDeclaration:
        private_fields, public_fields, init_declarations, private_methods, public_methods = [], [], [], [], []
        for node in body:
            if isinstance(node, nodes.FieldDeclaration):
                if node.name.member.startswith("_"):
                    private_fields.append(node)
                else:
                    public_fields.append(node)
            elif isinstance(node, nodes.FunctionDeclaration):
                method_declaration = nodes.MethodDeclaration(
                    node.line, node.name, node.args, node.return_type, node.body
                )
                if node.name.member.startswith("_"):
                    private_methods.append(method_declaration)
                else:
                    public_methods.append(method_declaration)
            elif isinstance(node, nodes.InitDeclaration):
                init_declarations.append(node)
            else:
                raise errors.AngelSyntaxError("expected method, field or init declaration", self.get_code(node.line))
        return nodes.StructDeclaration(
            line, name, parameters, private_fields, public_fields, init_declarations, private_methods, public_methods
        )

    def make_algebraic_declaration(
        self, line: int, name: nodes.Name, parameters: nodes.Parameters, body: nodes.AST
    ) -> nodes.AlgebraicDeclaration:
        constructors = []
        for node in body:
            if isinstance(node, nodes.StructDeclaration):
                constructors.append(node)
            else:
                raise errors.AngelSyntaxError("expected method or constructor declaration", self.get_code(node.line))
        return nodes.AlgebraicDeclaration(line, name, parameters, constructors, public_methods=[], private_methods=[])

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
        atom: t.Optional[nodes.AssignmentLeft] = self.parse_name()
        if atom is None:
            return None
        trailer = self.parse_trailer()
        while trailer is not None:
            if isinstance(trailer, FieldTrailer):
                atom = nodes.Field(trailer.line, atom, trailer.field)
            elif isinstance(trailer, SubscriptTrailer):
                atom = nodes.Subscript(trailer.line, atom, trailer.index)
            else:
                self.restore_state(state)
                return None
            trailer = self.parse_trailer()
        return atom

    def parse_assignment_operator(self) -> t.Optional[nodes.Operator]:
        for operator in nodes.Operator.assignment_operators():
            if self.parse_raw(operator.value):
                return operator
        return None

    def parse_container(
            self, open_container: str, close_container: str, element_separator: str,
            element_parser: t.Callable[[], t.Any]
    ) -> t.Optional[t.List[t.Any]]:
        if not self.parse_raw(open_container):
            return None
        result = []
        element = element_parser()
        while element is not None:
            result.append(element)
            if not self.parse_raw(element_separator) and not self.next_nonspace_char_is(close_container):
                raise errors.AngelSyntaxError(f"expected '{element_separator}' or '{close_container}'", self.get_code())
            self.spaces()
            element = element_parser()
        if not self.parse_raw(close_container):
            raise errors.AngelSyntaxError(f"expected '{close_container}'", self.get_code())
        return result

    def parse_node(self) -> t.Optional[nodes.Node]:
        for parser in self.NODE_PARSERS:
            node = parser(self)
            if node is not None:
                return node
        return None

    def is_eof(self) -> bool:
        return self.code[self.idx:] == ""

    def parse_type(self) -> t.Optional[nodes.Type]:
        inner_type = self.parse_type_atom()
        if inner_type is None:
            return None
        type_trailer = self.parse_type_trailer()
        while type_trailer is not None:
            if isinstance(type_trailer, OptionalTypeTrailer):
                inner_type = nodes.OptionalType(inner_type)
            else:
                raise errors.AngelNotImplemented
            type_trailer = self.parse_type_trailer()
        return inner_type

    def parse_type_trailer(self) -> t.Optional[Trailer]:
        if self.parse_raw("?"):
            return OptionalTypeTrailer(self.position.line)
        return None

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
        return self.parse_expression_comparison()

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
        atom = self.parse_expression_atom()
        if atom is None:
            return None
        trailer = self.parse_trailer()
        while trailer is not None:
            if isinstance(trailer, TupleTrailer):
                atom = nodes.FunctionCall(trailer.line, atom, trailer.args)
            elif isinstance(trailer, FieldTrailer):
                atom = nodes.Field(trailer.line, atom, trailer.field)
            elif isinstance(trailer, SubscriptTrailer):
                atom = nodes.Subscript(trailer.line, atom, trailer.index)
            else:
                raise errors.AngelNotImplemented
            trailer = self.parse_trailer()
        return atom

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
        args = self.parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self.parse_expression)
        if args is None:
            if self.parse_raw("."):
                field = self.parse_identifier()
                if not field:
                    raise errors.AngelSyntaxError("expected identifier", self.get_code())
                return FieldTrailer(line, field)
            elif self.parse_raw("["):
                index = self.parse_expression()
                if not index:
                    raise errors.AngelSyntaxError("expected expression", self.get_code())
                if not self.parse_raw("]"):
                    raise errors.AngelSyntaxError("expected ']'", self.get_code())
                return SubscriptTrailer(line, index)
            return None
        return TupleTrailer(line, args)

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
