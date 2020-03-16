import json
import typing as t
from itertools import zip_longest
from functools import partial
from decimal import Decimal
from dataclasses import dataclass

from . import (
    nodes, errors, environment, environment_entries as entries,
    type_checking
)
from .utils import dispatch


OPERATOR_TO_METHOD_NAME = {
    nodes.Operator.eq_eq.value: nodes.SpecialMethods.eq.value,
    nodes.Operator.lt.value: nodes.SpecialMethods.lt.value,
    nodes.Operator.gt.value: nodes.SpecialMethods.gt.value,

    nodes.Operator.add.value: nodes.SpecialMethods.add.value,
    nodes.Operator.sub.value: nodes.SpecialMethods.sub.value,
    nodes.Operator.mul.value: nodes.SpecialMethods.mul.value,
    nodes.Operator.div.value: nodes.SpecialMethods.div.value,
}


def add(x, y):
    if isinstance(x, nodes.DynValue):
        return nodes.DynValue(x.type)
    elif isinstance(y, nodes.DynValue):
        return nodes.DynValue(y.type)
    return x + y


def sub(x, y):
    if isinstance(x, nodes.DynValue):
        return nodes.DynValue(x.type)
    elif isinstance(y, nodes.DynValue):
        return nodes.DynValue(y.type)
    return x - y


def mul(x, y):
    if isinstance(x, nodes.DynValue):
        return nodes.DynValue(x.type)
    elif isinstance(y, nodes.DynValue):
        return nodes.DynValue(y.type)
    return x * y


def div(x, y):
    if y == 0:
        raise errors.AngelDivByZero
    if isinstance(x, nodes.DynValue):
        return nodes.DynValue(x.type)
    elif isinstance(y, nodes.DynValue):
        return nodes.DynValue(y.type)
    return x / y


def eq_eq(x, y):
    if isinstance(x, nodes.DynValue) or isinstance(y, nodes.DynValue):
        return nodes.DynValue(nodes.BuiltinType.bool)
    return x == y


def lt_eq(x, y):
    if isinstance(x, nodes.DynValue) or isinstance(y, nodes.DynValue):
        return nodes.DynValue(nodes.BuiltinType.bool)
    return x <= y


def gt_eq(x, y):
    if isinstance(x, nodes.DynValue) or isinstance(y, nodes.DynValue):
        return nodes.DynValue(nodes.BuiltinType.bool)
    return x >= y


def neq(x, y):
    if isinstance(x, nodes.DynValue) or isinstance(y, nodes.DynValue):
        return nodes.DynValue(nodes.BuiltinType.bool)
    return x != y


def lt(x, y):
    if isinstance(x, nodes.DynValue) or isinstance(y, nodes.DynValue):
        return nodes.DynValue(nodes.BuiltinType.bool)
    return x < y


def gt(x, y):
    if isinstance(x, nodes.DynValue) or isinstance(y, nodes.DynValue):
        return nodes.DynValue(nodes.BuiltinType.bool)
    return x > y


OPERATOR_TO_EVAL_FUNC = {
    nodes.Operator.eq_eq.value: eq_eq,
    nodes.Operator.lt_eq.value: lt_eq,
    nodes.Operator.gt_eq.value: gt_eq,
    nodes.Operator.neq.value: neq,
    nodes.Operator.lt.value: lt,
    nodes.Operator.gt.value: gt,

    nodes.Operator.add.value: add,
    nodes.Operator.sub.value: sub,
    nodes.Operator.mul.value: mul,
    nodes.Operator.div.value: div,
}


class BreakEvaluated:
    pass


@dataclass  # For eq.
class OptionalNoneEvaluated:
    pass


@dataclass
class OptionalSomeEvaluated:
    value: t.Any


class Analyzer:

    def __init__(self, lines: t.List[str], env: t.Optional[environment.Environment] = None):
        self.env = env or environment.Environment()
        self.lines = lines
        self.current_line = 1
        self.function_return_types: t.List[nodes.Type] = []
        self.parents: t.List[nodes.Name] = []
        self.repl_tmp_count = 0

        self.type_checker = type_checking.TypeChecker()

        # REPL eval
        repl_eval_builtin_function_call_dispatcher: t.Dict[str, t.Callable[[t.List[nodes.Expression]], t.Any]] = {
            nodes.BuiltinFunc.print.value: lambda args: print(
                self.repl_tweak_for_printing(self.repl_eval_expression(args[0]))
            ),
            nodes.BuiltinFunc.read.value: self.repl_eval_read_function_call,
        }

        repl_eval_function_call_dispatcher_by_function_path = {
            nodes.BuiltinFunc: lambda path, args: dispatch(
                repl_eval_builtin_function_call_dispatcher, path.value, args
            ),
            nodes.Name: self.repl_eval_function_as_name_call,
        }

        repl_eval_node_dispatcher = {
            nodes.ConstantDeclaration: self.repl_eval_constant_declaration,
            nodes.VariableDeclaration: self.repl_eval_variable_declaration,
            nodes.FunctionDeclaration: lambda _: None,
            nodes.StructDeclaration: lambda _: None,
            nodes.Assignment: self.repl_eval_assignment,
            nodes.FunctionCall: lambda node: dispatch(
                repl_eval_function_call_dispatcher_by_function_path, type(node.function_path), node.function_path,
                node.args
            ),
            nodes.While: self.repl_eval_while_statement,
            nodes.Break: self.repl_eval_break_statement,
            nodes.If: self.repl_eval_if_statement,
        }
        self.repl_eval_node = lambda node: dispatch(repl_eval_node_dispatcher, type(node), node)

        self.repl_eval_expression: t.Callable[[t.Optional[nodes.Expression]], t.Any] = lambda value: dispatch(
            repl_eval_expression_dispatcher, type(value), value
        )
        repl_eval_expression_dispatcher = {
            nodes.IntegerLiteral: lambda value: int(value.value),
            nodes.DecimalLiteral: lambda value: Decimal(value.value),
            nodes.StringLiteral: lambda value: value.value,
            nodes.VectorLiteral: lambda value: [self.repl_eval_expression(element) for element in value.elements],
            nodes.DictLiteral: lambda value: {
                self.repl_eval_expression(key): self.repl_eval_expression(val)
                for key, val in zip(value.keys, value.values)
            },
            nodes.OptionalTypeConstructor: self.repl_eval_optional_type_constructor,
            nodes.OptionalSomeCall: self.repl_eval_optional_some_call,
            nodes.OptionalSomeValue: self.repl_eval_optional_some_value,
            nodes.CharLiteral: lambda value: value.value,
            nodes.BoolLiteral: lambda value: value.value == nodes.BoolLiteral.true.value,
            nodes.BinaryExpression: partial(self.eval_binary_expression, self.repl_eval_expression),
            nodes.Name: self.repl_eval_name,
            nodes.FunctionCall: lambda node: dispatch(
                repl_eval_function_call_dispatcher_by_function_path, type(node.function_path), node.function_path,
                node.args
            ),
            nodes.Cast: lambda node: self.repl_eval_expression(node.value),
            type(None): lambda _: None,
        }

        analyzer_eval_builtin_function_call_dispatcher: t.Dict[str, t.Callable[[t.List[nodes.Expression]], t.Any]] = {
            nodes.BuiltinFunc.print.value: lambda _: None,
            nodes.BuiltinFunc.read.value: self.analyzer_eval_read_function_call,
        }

        analyzer_eval_function_call_dispatcher_by_function_path = {
            nodes.BuiltinFunc: lambda path, args: dispatch(
                analyzer_eval_builtin_function_call_dispatcher, path.value, args
            ),
            nodes.Name: self.analyzer_eval_function_as_name_call,
        }

        self.analyzer_eval_expression: t.Callable[[t.Optional[nodes.Expression]], t.Any] = lambda value: dispatch(
            analyzer_eval_expression_dispatcher, type(value), value
        )
        analyzer_eval_expression_dispatcher = {
            nodes.IntegerLiteral: lambda value: int(value.value),
            nodes.DecimalLiteral: lambda value: Decimal(value.value),
            nodes.StringLiteral: lambda value: value.value,
            nodes.VectorLiteral: lambda value: [self.analyzer_eval_expression(element) for element in value.elements],
            nodes.DictLiteral: lambda value: {
                self.analyzer_eval_expression(key): self.analyzer_eval_expression(val)
                for key, val in zip(value.keys, value.values)
            },
            nodes.OptionalTypeConstructor: self.analyzer_eval_optional_type_constructor,
            nodes.OptionalSomeCall: self.analyzer_eval_optional_some_call,
            nodes.OptionalSomeValue: self.analyzer_eval_optional_some_value,
            nodes.CharLiteral: lambda value: value.value,
            nodes.BoolLiteral: lambda value: value.value == nodes.BoolLiteral.true.value,
            nodes.BinaryExpression: partial(self.eval_binary_expression, self.analyzer_eval_expression),
            nodes.Name: self.analyzer_eval_name,
            nodes.FunctionCall: lambda node: dispatch(
                analyzer_eval_function_call_dispatcher_by_function_path, type(node.function_path), node.function_path,
                node.args
            ),
            nodes.Cast: lambda node: self.analyzer_eval_expression(node.value),
            type(None): lambda _: None,
        }

        repl_reassign_dispatcher = {
            nodes.Name: self.repl_reassign_name,
        }
        self.repl_reassign = lambda node: dispatch(repl_reassign_dispatcher, type(node.left), node.left, node.right)

        analyzer_reassign_dispatcher = {
            nodes.Name: self.analyzer_reassign_name,
        }
        self.analyzer_reassign = lambda node: dispatch(
            analyzer_reassign_dispatcher, type(node.left), node.left, node.right)

        # Analyzer
        analyze_node_dispatcher = {
            nodes.ConstantDeclaration: self.analyze_constant_declaration,
            nodes.VariableDeclaration: self.analyze_variable_declaration,
            nodes.FunctionDeclaration: self.analyze_function_declaration,
            nodes.StructDeclaration: self.analyze_struct_declaration,
            nodes.FieldDeclaration: self.analyze_field_declaration,
            nodes.Assignment: self.analyze_assignment,
            nodes.FunctionCall: self.analyze_function_call,
            nodes.While: self.analyze_while_statement,
            nodes.Break: lambda node: node,
            nodes.If: self.analyze_if_statement,
            nodes.Return: self.analyze_return_statement,
        }
        self.analyze_node = lambda node: dispatch(analyze_node_dispatcher, type(node), node)
        self.analyze = lambda ast: [self.analyze_node(node) for node in ast]

        can_assign_dispatcher = {
            nodes.Name: self.can_assign_name,
        }
        self.can_assign = lambda value: dispatch(can_assign_dispatcher, type(value), value)

        get_definition_code_dispatcher = {
            nodes.Name: self.get_name_definition_code,
        }
        self.get_definition_code = lambda value: dispatch(get_definition_code_dispatcher, type(value), value)

        checked_function_as_builtin_func_call_dispatcher = {
            nodes.BuiltinFunc.print.value: self.checked_print_call,
            nodes.BuiltinFunc.read.value: self.checked_read_call,
        }
        self.checked_function_as_builtin_func_call = lambda line, path, args: dispatch(
            checked_function_as_builtin_func_call_dispatcher, path.value, line, path, args
        )
        checked_function_call_dispatcher_by_function_path = {
            nodes.Name: self.checked_function_as_name_call,
            nodes.BuiltinFunc: self.checked_function_as_builtin_func_call,
            nodes.OptionalTypeConstructor: self.checked_function_as_optional_constructor_call,
        }
        self.checked_function_call = lambda line, path, args: dispatch(
            checked_function_call_dispatcher_by_function_path, type(path), line, path, args
        )

    def repl_eval_constant_declaration(self, node: nodes.ConstantDeclaration) -> None:
        entry = self.env[node.name.member]
        assert isinstance(entry, entries.ConstantEntry)
        entry.computed_value=self.repl_eval_expression(node.value)

    def repl_eval_variable_declaration(self, node: nodes.VariableDeclaration) -> None:
        entry = self.env[node.name.member]
        assert isinstance(entry, entries.VariableEntry)
        entry.computed_value = self.repl_eval_expression(node.value)

    def analyze_constant_declaration(self, node: nodes.ConstantDeclaration) -> nodes.ConstantDeclaration:
        self.current_line = node.line
        if node.value:
            type_ = self.infer_type(node.value, supertype=node.type)
        else:
            assert node.type is not None
            type_ = self.unify_types(node.type, node.type)
        self.env.add_constant(
            node.line, node.name, type_, node.value, analyzed_value=self.analyzer_eval_expression(node.value)
        )
        return nodes.ConstantDeclaration(node.line, node.name, type_, node.value)

    def analyze_variable_declaration(self, node: nodes.VariableDeclaration) -> nodes.VariableDeclaration:
        self.current_line = node.line
        if node.value:
            type_ = self.infer_type(node.value, supertype=node.type)
        else:
            assert node.type is not None
            type_ = self.unify_types(node.type, node.type)
        self.env.add_variable(
            node.line, node.name, type_, analyzed_value=self.analyzer_eval_expression(node.value)
        )
        return nodes.VariableDeclaration(node.line, node.name, type_, node.value)

    def analyze_function_declaration(self, node: nodes.FunctionDeclaration) -> nodes.FunctionDeclaration:
        self.current_line = node.line
        args = []
        for arg in node.args:
            args.append(nodes.Argument(arg.name, self.unify_types(arg.type, arg.type)))
        return_type = self.unify_types(node.return_type, node.return_type)
        if self.parents:
            self.env.add_method(self.parents[-1], node.line, node.name, args, return_type)
        else:
            self.env.add_function(node.line, node.name, args, return_type)
        self.env.inc_nesting()
        self.env.add_arguments(node.line, args)
        self.function_return_types.append(return_type)
        body = self.analyze(node.body)
        self.function_return_types.pop()
        self.env.dec_nesting()
        if self.parents:
            self.env.update_method_body(self.parents[-1], node.name, body)
        else:
            self.env.update_function_body(node.name, body)
        return nodes.FunctionDeclaration(node.line, node.name, args, return_type, body)

    def analyze_struct_declaration(self, node: nodes.StructDeclaration) -> nodes.StructDeclaration:
        self.current_line = node.line
        self.env.add_struct(node.line, node.name)
        self.parents.append(node.name)
        body = self.analyze(node.body)
        self.parents.pop()
        return nodes.StructDeclaration(node.line, node.name, body)

    def analyze_field_declaration(self, node: nodes.FieldDeclaration) -> nodes.FieldDeclaration:
        assert self.parents
        self.current_line = node.line
        self.env.add_field(self.parents[-1], node.line, node.name, node.type)
        return nodes.FieldDeclaration(node.line, node.name, node.type)

    def analyze_assignment(self, node: nodes.Assignment) -> nodes.Assignment:
        self.current_line = node.line
        if not self.can_assign(node.left):
            raise errors.AngelConstantReassignment(
                node.left, self.get_code(node.line), self.get_definition_code(node.left)
            )
        if node.operator.value != nodes.Operator.eq.value:
            right: nodes.Expression = nodes.BinaryExpression(
                node.left, node.operator.to_arithmetic_operator(), node.right
            )
        else:
            right = node.right
        # Type checking
        self.infer_type(right, supertype=self.infer_type(node.left))
        result = nodes.Assignment(node.line, node.left, nodes.Operator.eq, right)
        self.analyzer_reassign(result)
        return result

    def repl_eval_assignment(self, node: nodes.Assignment) -> None:
        self.repl_reassign(node)

    def analyze_function_call(self, node: nodes.FunctionCall) -> nodes.FunctionCall:
        self.current_line = node.line
        return self.checked_function_call(node.line, node.function_path, node.args)

    def analyze_while_statement(self, node: nodes.While) -> nodes.While:
        self.current_line = node.line
        self.infer_type(node.condition, supertype=nodes.BuiltinType.bool)
        self.env.inc_nesting()
        body = self.analyze(node.body)
        self.env.dec_nesting()
        return nodes.While(node.line, node.condition, body)

    def analyze_if_statement(self, node: nodes.If) -> nodes.If:
        self.current_line = node.line
        if isinstance(node.condition, nodes.ConstantDeclaration):
            condition = self.analyze_node(node.condition)
        else:
            condition = node.condition
            self.infer_type(condition, supertype=nodes.BuiltinType.bool)
        self.env.inc_nesting()
        body = self.analyze(node.body)
        self.env.dec_nesting()
        elifs = []
        for elif_condition, elif_body in node.elifs:
            if isinstance(elif_condition, nodes.ConstantDeclaration):
                elif_condition = self.analyze_node(elif_condition)
            else:
                self.infer_type(elif_condition, supertype=nodes.BuiltinType.bool)
            self.env.inc_nesting()
            elif_body_analyzed = self.analyze(elif_body)
            self.env.dec_nesting()
            elifs.append((elif_condition, elif_body_analyzed))
        self.env.inc_nesting()
        else_ = self.analyze(node.else_)
        self.env.dec_nesting()
        return nodes.If(node.line, condition, body, elifs, else_)

    def analyze_return_statement(self, node: nodes.Return) -> nodes.Return:
        self.current_line = node.line
        self.infer_type(node.value, supertype=self.function_return_types[-1])
        return nodes.Return(node.line, node.value)

    def checked_function_as_name_call(self, line: int, path: nodes.Name, args: t.List[nodes.Expression]):
        entry = self.env[path.member]
        if entry is None:
            raise errors.AngelNameError(path, self.get_code(self.current_line))
        if isinstance(entry, entries.FunctionEntry):
            for passed_arg, declared_arg in zip_longest(args, entry.args):
                if passed_arg is None or declared_arg is None:
                    raise errors.AngelWrongArguments(
                        "(" + ", ".join([arg.to_code() for arg in entry.args]) + ")",
                        self.get_code(self.current_line), args
                    )
                self.infer_type(passed_arg, supertype=declared_arg.type)
        else:
            raise errors.AngelNoncallableCall(path, self.get_code(self.current_line))
        return nodes.FunctionCall(line, path, args)

    def checked_function_as_optional_constructor_call(
            self, line: int, path: nodes.OptionalTypeConstructor, args: t.List[nodes.Expression]
    ) -> nodes.Expression:
        if path.value == nodes.OptionalTypeConstructor.none.value:
            raise errors.AngelNoncallableCall(path, self.get_code(line))
        if len(args) != 1:
            raise errors.AngelWrongArguments("(value: T)", self.get_code(self.current_line), args)
        return nodes.OptionalSomeCall(args[0])

    def checked_print_call(self, line: int, path: nodes.BuiltinFunc, args: t.List[nodes.Expression]):
        if len(args) != 1:
            raise errors.AngelWrongArguments(
                f"(value: {nodes.BuiltinType.convertible_to_string.value})", self.get_code(self.current_line), args
            )
        arg_type = self.infer_type(args[0])
        self.unify_types(arg_type, nodes.BuiltinType.convertible_to_string)
        return nodes.FunctionCall(line, path, [self.tweak_for_printing(args[0], arg_type)])

    def checked_read_call(self, line: int, path: nodes.BuiltinFunc, args: t.List[nodes.Expression]):
        if len(args) != 1:
            raise errors.AngelWrongArguments(
                f"(prompt: {nodes.BuiltinType.string.value})", self.get_code(self.current_line), args
            )
        self.infer_type(args[0], supertype=nodes.BuiltinType.string)
        return nodes.FunctionCall(line, path, args)

    def can_assign_name(self, value: nodes.Name) -> bool:
        entry = self.env[value.member]
        if isinstance(entry, entries.VariableEntry):
            return True
        elif isinstance(entry, entries.ConstantEntry):
            return not entry.has_value
        return False

    def get_code(self, line: int) -> errors.Code:
        return errors.Code(self.lines[line - 1], line)

    def get_name_definition_code(self, value: nodes.Name) -> errors.Code:
        entry = self.env[value.member]
        if entry is None:
            raise errors.AngelNameError(value, self.get_code(self.current_line))
        return self.get_code(entry.line)

    def analyzer_reassign_name(self, left: nodes.Name, right: nodes.Expression) -> None:
        entry = self.env[left.member]
        if isinstance(entry, entries.VariableEntry):
            entry.analyzed_value = self.analyzer_eval_expression(right)
        elif isinstance(entry, entries.ConstantEntry):
            if entry.has_value:
                raise errors.AngelConstantReassignment(
                    left, self.get_code(self.current_line), self.get_code(entry.line))
            entry.analyzed_value = self.analyzer_eval_expression(right)
            entry.has_value = True
        else:
            raise errors.AngelNameError(left, self.get_code(self.current_line))

    def repl_reassign_name(self, left: nodes.Name, right: nodes.Expression) -> None:
        entry = self.env[left.member]
        if isinstance(entry, entries.VariableEntry):
            entry.computed_value = self.repl_eval_expression(right)
        elif isinstance(entry, entries.ConstantEntry):
            if entry.has_value:
                raise errors.AngelConstantReassignment(
                    left, self.get_code(self.current_line), self.get_code(entry.line))
            entry.computed_value = self.repl_eval_expression(right)
            entry.has_value = True
        else:
            raise errors.AngelNameError(left, self.get_code(self.current_line))

    def repl_eval_ast(self, ast: nodes.AST, execute_only_last_node: bool = False) -> t.Any:
        if execute_only_last_node:
            for node in ast[:-1]:
                self.analyze_node(node)
            return self.repl_eval_node(self.analyze_node(ast[-1]))
        result = None
        for node in ast:
            result = self.repl_eval_node(self.analyze_node(node))
        return result

    def repl_eval_while_statement(self, node: nodes.While):
        while self.repl_eval_expression(node.condition):
            result = self.repl_eval_ast(node.body)
            if isinstance(result, BreakEvaluated):
                break
            if result is not None:
                return result

    def repl_eval_break_statement(self, _: nodes.Break):
        return BreakEvaluated()

    def repl_eval_if_statement(self, node: nodes.If):
        condition = node.condition
        body = node.body
        if isinstance(condition, nodes.ConstantDeclaration):
            assert condition.value is not None
            tmp_right = self.create_repl_tmp(condition.value)
            to_prepend: t.List[nodes.Node] = [
                nodes.ConstantDeclaration(
                    condition.line, condition.name, condition.type, nodes.OptionalSomeValue(tmp_right)
                )
            ]
            body = to_prepend + body
            condition = nodes.BinaryExpression(tmp_right, nodes.Operator.neq, nodes.OptionalTypeConstructor.none)
        if self.repl_eval_expression(condition):
            return self.repl_eval_ast(body)
        for elif_condition, elif_body in node.elifs:
            if isinstance(elif_condition, nodes.ConstantDeclaration):
                assert elif_condition.value is not None
                tmp_right = self.create_repl_tmp(elif_condition.value)
                elif_to_prepend: t.List[nodes.Node] = [
                    nodes.ConstantDeclaration(
                        elif_condition.line, elif_condition.name, elif_condition.type,
                        nodes.OptionalSomeValue(tmp_right)
                    )
                ]
                elif_body = elif_to_prepend + elif_body
                elif_condition = nodes.BinaryExpression(
                    tmp_right, nodes.Operator.neq, nodes.OptionalTypeConstructor.none
                )
            if self.repl_eval_expression(elif_condition):
                return self.repl_eval_ast(elif_body)
        return self.repl_eval_ast(node.else_)

    def create_repl_tmp(self, value: nodes.Expression) -> nodes.Name:
        name = nodes.Name("__repl_tmp" + str(self.repl_tmp_count))
        self.repl_tmp_count += 1
        self.env.add_constant(
            self.current_line, name, self.infer_type(value), value,
            analyzed_value=self.analyzer_eval_expression(value), computed_value=self.repl_eval_expression(value)
        )
        return name

    def repl_eval_optional_type_constructor(self, value: nodes.OptionalTypeConstructor) -> t.Any:
        if value.value == nodes.OptionalTypeConstructor.none.value:
            return OptionalNoneEvaluated()
        raise errors.AngelNotImplemented

    def repl_eval_optional_some_call(self, value: nodes.OptionalSomeCall) -> t.Any:
        return OptionalSomeEvaluated(self.repl_eval_expression(value.value))

    def repl_eval_optional_some_value(self, value: nodes.OptionalSomeValue) -> t.Any:
        optional_some = self.repl_eval_expression(value.value)
        assert isinstance(optional_some, OptionalSomeEvaluated)
        return optional_some.value

    def analyzer_eval_optional_type_constructor(self, value: nodes.OptionalTypeConstructor) -> t.Any:
        if value.value == nodes.OptionalTypeConstructor.none.value:
            return OptionalNoneEvaluated()
        raise errors.AngelNotImplemented

    def analyzer_eval_optional_some_call(self, value: nodes.OptionalSomeCall) -> t.Any:
        return OptionalSomeEvaluated(self.analyzer_eval_expression(value.value))

    def analyzer_eval_optional_some_value(self, value: nodes.OptionalSomeValue) -> t.Any:
        optional = self.analyzer_eval_expression(value.value)
        assert isinstance(optional, OptionalSomeEvaluated)
        return optional.value

    def repl_eval_function_as_name_call(self, path: nodes.Name, args: t.List[nodes.Expression]) -> t.Any:
        entry = self.env[path.member]
        if entry is None:
            raise errors.AngelNameError(path, self.get_code(self.current_line))
        if isinstance(entry, entries.FunctionEntry):
            self.env.inc_nesting()
            for value, declared_arg in zip_longest(args, entry.args):
                if value is None or declared_arg is None:
                    raise errors.AngelWrongArguments(
                        "(" + ", ".join([arg.to_code() for arg in entry.args]) + ")",
                        self.get_code(self.current_line), args
                    )
                self.env.add_constant(
                    entry.line, declared_arg.name, declared_arg.type, value,
                    computed_value=self.repl_eval_expression(value)
                )
            result = self.repl_eval_ast(entry.body)
            self.env.inc_nesting()
            return result
        else:
            raise errors.AngelNoncallableCall(path, self.get_code(self.current_line))

    def analyzer_eval_function_as_name_call(self, path: nodes.Name, args: t.List[nodes.Expression]) -> t.Any:
        entry = self.env[path.member]
        if entry is None:
            raise errors.AngelNameError(path, self.get_code(self.current_line))
        if isinstance(entry, entries.FunctionEntry):
            self.env.inc_nesting()
            for value, declared_arg in zip_longest(args, entry.args):
                if value is None or declared_arg is None:
                    raise errors.AngelWrongArguments(
                        "(" + ", ".join([arg.to_code() for arg in entry.args]) + ")",
                        self.get_code(self.current_line), args
                    )
                self.env.add_constant(
                    entry.line, declared_arg.name, declared_arg.type, value,
                    analyzed_value=self.analyzer_eval_expression(value)
                )
            result = self.analyze(entry.body)
            self.env.inc_nesting()
            return result
        else:
            raise errors.AngelNoncallableCall(path, self.get_code(self.current_line))

    def eval_binary_expression(self, eval_expression_func, value: nodes.BinaryExpression) -> t.Any:
        left = eval_expression_func(value.left)
        right = eval_expression_func(value.right)
        result = OPERATOR_TO_EVAL_FUNC[value.operator.value](left, right)
        if isinstance(left, int) and value.operator.value == nodes.Operator.div.value:
            return int(result)
        return result

    def repl_eval_name(self, value: nodes.Name) -> t.Any:
        entry = self.env[value.member]
        if isinstance(entry, (entries.ConstantEntry, entries.VariableEntry)):
            return entry.computed_value
        else:
            raise errors.AngelNameError(value, self.get_code(self.current_line))

    def analyzer_eval_name(self, value: nodes.Name) -> t.Any:
        entry = self.env[value.member]
        if isinstance(entry, (entries.ConstantEntry, entries.VariableEntry)):
            return entry.analyzed_value
        else:
            raise errors.AngelNameError(value, self.get_code(self.current_line))

    def repl_tweak_for_printing(self, value: t.Any) -> t.Any:
        if isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, dict):
            return self.change_dict_braces(value)
        return value

    def tweak_for_printing(self, value: nodes.Expression, value_type: nodes.Type) -> nodes.Expression:
        if isinstance(value_type, nodes.BuiltinType):
            if value_type.value == nodes.BuiltinType.i8.value:
                return nodes.Cast(value, nodes.BuiltinType.i16)
            elif value_type.value == nodes.BuiltinType.u8.value:
                return nodes.Cast(value, nodes.BuiltinType.u16)
        return value

    def change_dict_braces(self, d):
        new_d = {}
        for key, value in d.items():
            if isinstance(value, dict):
                value = self.change_dict_braces(value)
            new_d[key] = value
        # For double quotes.
        s = json.dumps(new_d)
        return "[" + s[1:-1] + "]"

    def repl_eval_read_function_call(self, args: t.List[nodes.Expression]) -> t.Any:
        return input(self.repl_eval_expression(args[0]))

    def analyzer_eval_read_function_call(self, _: t.List[nodes.Expression]) -> t.Any:
        return nodes.DynValue(nodes.BuiltinType.string)

    # Type checking
    def infer_type(self, value: nodes.Expression, supertype: t.Optional[nodes.Type] = None) -> nodes.Type:
        """Wrapper around TypeChecker.infer_type that helps to keep Environment up to date."""
        self.type_checker.update_context(self.env, self.get_code(self.current_line))
        return self.type_checker.infer_type(value, supertype)

    def unify_types(self, subtype: nodes.Type, supertype: t.Optional[nodes.Type]) -> nodes.Type:
        """Wrapper around TypeChecker.unify_types that helps to keep Environment up to date."""
        self.type_checker.update_context(self.env, self.get_code(self.current_line))
        return self.type_checker.unify_types(subtype, supertype)
