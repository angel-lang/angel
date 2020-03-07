import re
import sys
import typing as t
from dataclasses import dataclass
from itertools import zip_longest

from . import nodes


IDENTIFIER_REGEX = re.compile("[a-zA-Z][a-zA-Z0-9]*")
INTEGER_REGEX = re.compile("[0-9]+")


def _linear_parser(
        flow: t.Iterable[t.Tuple[t.Callable[[], t.Any], t.Optional[t.Callable[[], t.Any]]]]
) -> t.List[t.Any]:
    results = []
    for parser, on_fail in flow:
        result = parser()
        if not result and on_fail:
            return on_fail()
        results.append(result)
    return results


@dataclass
class State:
    idx: int
    position: nodes.Position


class Parser:
    code: str
    idx: int
    position: nodes.Position

    def parse(self, string: str) -> t.List[nodes.Node]:
        self.code = string
        self.idx = 0
        self.position = nodes.Position()

        result = []
        self._spaces()
        node = self._parse_node()
        while node is not None:
            result.append(node)
            self._spaces()
            node = self._parse_node()
        if not self._is_eof():
            self._error_parser_has_stuck()
        return result

    def _parse_constant_declaration(self) -> t.Optional[nodes.ConstantDeclaration]:
        results = _linear_parser([
            (lambda: self._parse_keyword("let"), lambda: None),
            (self._spaces, None),
            (self._parse_name, lambda: self._error_expected("name")),
            (lambda: self._parse(":"), lambda: self._error_expected("':'")),
            (self._spaces, None),
            (self._parse_type, lambda: self._error_expected("type")),
            (self._spaces, None),
            (lambda: self._parse("="), lambda: self._error_expected("=")),
            (self._spaces, None),
            (self._parse_expression, lambda: self._error_expected("expression")),
        ])
        if isinstance(results, list):
            return nodes.ConstantDeclaration(results[2], results[5], results[9])
        return None

    def _parse_function_call(self) -> t.Optional[nodes.FunctionCall]:
        state = self._backup_state()
        function_path = self._parse_expression()
        if function_path is None:
            return None
        arguments = self._parse_container(
            open_container="(", close_container=")", element_separator=",", element_parser=self._parse_expression)
        if arguments is None:
            self._restore_state(state)
            return None
        return nodes.FunctionCall(function_path, arguments)

    NODE_PARSERS = [_parse_constant_declaration, _parse_function_call]

    def _parse_container(
            self, open_container: str, close_container: str, element_separator: str,
            element_parser: t.Callable[[], t.Any]
    ) -> t.Optional[t.List[t.Any]]:
        if not self._parse(open_container):
            return None
        result = []
        element = element_parser()
        while element is not None:
            result.append(element)
            if not self._parse(element_separator) and not self._next_nonspace_char_is(close_container):
                self._error_expected(element_separator)
            self._spaces()
            element = element_parser()
        if not self._parse(close_container):
            self._error_expected(close_container)
        return result

    def _parse_node(self) -> t.Optional[nodes.Node]:
        for parser in self.NODE_PARSERS:
            node = parser(self)
            if node is not None:
                return node

    def _is_eof(self) -> bool:
        return self.code[self.idx:] == ""

    def _parse_type(self) -> t.Optional[nodes.Type]:
        return self._parse_name()

    def _parse_expression(self) -> t.Optional[nodes.Expression]:
        return self._parse_expression_atom()

    def _parse_expression_atom(self) -> t.Optional[nodes.Expression]:
        for parser in [self._parse_integer_literal, self._parse_string_literal, self._parse_name]:
            result = parser()
            if result is not None:
                return result

    def _parse_integer_literal(self) -> t.Optional[nodes.IntegerLiteral]:
        match = INTEGER_REGEX.match(self.code[self.idx:])
        if match is None:
            return None
        match_length = len(match[0])
        self.idx += match_length
        self.position.column += match_length
        return nodes.IntegerLiteral(match[0])

    def _parse_string_literal(self) -> t.Optional[nodes.StringLiteral]:
        state = self._backup_state()
        if not self._parse('"'):
            return None
        result = []
        for char in self.code[self.idx:]:
            self.idx += 1
            self.position.column += 1
            if char == '"':
                break
            else:
                result.append(char)
        if result:
            return nodes.StringLiteral("".join(result))
        self._restore_state(state)
        return None

    def _parse_name(self) -> t.Optional[nodes.Name]:
        identifier = self._parse_identifier()
        if identifier:
            return nodes.Name(identifier)
        return None

    def _parse_identifier(self) -> str:
        match = IDENTIFIER_REGEX.match(self.code[self.idx:])
        if match is None:
            return ""
        match_length = len(match[0])
        self.idx += match_length
        self.position.column += match_length
        return match[0]

    def _spaces(self):
        for char in self.code[self.idx:]:
            if char == "\n":
                self.idx += 1
                self.position.line += 1
                self.position.column = 1
            elif char.isspace():
                self.idx += 1
                self.position.column += 1
            else:
                break

    def _parse_keyword(self, keyword: str) -> bool:
        state = self._backup_state()
        parsed_keyword_as_string = self._parse(keyword)
        if parsed_keyword_as_string and not self._next_char_isspace():
            self._restore_state(state)
            return False
        return parsed_keyword_as_string

    def _parse(self, string: str) -> bool:
        state = self._backup_state()
        for expected, got in zip_longest(string, self.code[self.idx:]):
            if expected is None:
                break
            elif got is None:
                return False
            elif expected != got:
                return False
            state.idx += 1
            state.position.column += 1
        self._restore_state(state)
        return True

    def _next_char_isspace(self) -> bool:
        return self.code[self.idx].isspace()

    def _next_nonspace_char_is(self, expected: str) -> bool:
        for got in self.code[self.idx:]:
            if not got.isspace():
                return expected == got
        return False

    def _backup_state(self) -> State:
        return State(idx=self.idx, position=self.position)

    def _restore_state(self, state: State):
        self.idx = state.idx
        self.position = state.position

    def _error_expected(self, expected: str) -> t.NoReturn:
        self._error_base(f"expected {expected}")

    def _error_parser_has_stuck(self) -> t.NoReturn:
        self._error_base("parser has stuck")

    def _error_base(self, message: str) -> t.NoReturn:
        print(f"Parsing Error ({self.position}): {message}; next 10 characters:")
        print(f"'{self.code[self.idx:self.idx + 10]}'")
        sys.exit(1)
