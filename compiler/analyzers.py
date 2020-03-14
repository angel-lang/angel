import typing as t
from itertools import zip_longest
from functools import partial
from decimal import Decimal

from . import nodes, errors, environment, environment_entries as entries
from .utils import dispatch


def get_possible_unsigned_int_types_based_on_value(value: int) -> t.List[nodes.Type]:
    if value < 0:
        return []
    elif value <= 255:
        return [nodes.BuiltinType.u8, nodes.BuiltinType.u16, nodes.BuiltinType.u32, nodes.BuiltinType.u64]
    elif value <= 65535:
        return [nodes.BuiltinType.u16, nodes.BuiltinType.u32, nodes.BuiltinType.u64]
    elif value <= 4294967295:
        return [nodes.BuiltinType.u32, nodes.BuiltinType.u64]
    elif value <= 18446744073709551615:
        return [nodes.BuiltinType.u64]
    return []


def get_possible_signed_int_types_based_on_value(value: int) -> t.List[nodes.Type]:
    if -128 <= value <= 127:
        return [nodes.BuiltinType.i8, nodes.BuiltinType.i16, nodes.BuiltinType.i32, nodes.BuiltinType.i64]
    elif -32768 <= value <= 32767:
        return [nodes.BuiltinType.i16, nodes.BuiltinType.i32, nodes.BuiltinType.i64]
    elif -2147483648 <= value <= 2147483647:
        return [nodes.BuiltinType.i32, nodes.BuiltinType.i64]
    elif -9223372036854775808 <= value <= 9223372036854775807:
        return [nodes.BuiltinType.i64]
    return []


def get_possible_int_types_based_on_value(value: int) -> t.List[nodes.Type]:
    return get_possible_signed_int_types_based_on_value(value) + get_possible_unsigned_int_types_based_on_value(value)


MAX_FLOAT32 = Decimal('3.402823700000000000000000000E+38')
MIN_FLOAT32 = Decimal('1.17549400000000000000000000E-38')
MAX_FLOAT64 = Decimal('1.79769313486231570000000000E308')
MIN_FLOAT64 = Decimal('2.22507385850720140000000000E-308')

OPERATOR_TO_METHOD_NAME = {
    nodes.Operator.eq_eq.value: nodes.SpecialMethods.eq.value,
    nodes.Operator.lt.value: nodes.SpecialMethods.lt.value,
    nodes.Operator.gt.value: nodes.SpecialMethods.gt.value,

    nodes.Operator.add.value: nodes.SpecialMethods.add.value,
    nodes.Operator.sub.value: nodes.SpecialMethods.sub.value,
    nodes.Operator.mul.value: nodes.SpecialMethods.mul.value,
    nodes.Operator.div.value: nodes.SpecialMethods.div.value,
}


def get_possible_float_types_base_on_value(value: str) -> t.List[nodes.Type]:
    decimal = Decimal(value)
    if MIN_FLOAT32 <= decimal <= MAX_FLOAT32 or -MAX_FLOAT32 <= decimal <= -MIN_FLOAT32 or decimal == 0:
        return [nodes.BuiltinType.f32, nodes.BuiltinType.f64]
    elif MIN_FLOAT64 <= decimal <= MAX_FLOAT64 or -MAX_FLOAT64 <= decimal <= -MIN_FLOAT64:
        return [nodes.BuiltinType.f64]
    return []


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


class Analyzer:

    def __init__(self, lines: t.List[str], env: t.Optional[environment.Environment] = None):
        self.env = env or environment.Environment()
        self.lines = lines
        self.current_line = 1
        self.function_return_types: t.List[nodes.Type] = []
        self.parents: t.List[nodes.Name] = []
        self.template_type_id = -1
        self.template_types: t.List[t.Optional[nodes.Type]] = []

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

        infer_type_from_builtin_func_call_dispatcher = {
            nodes.BuiltinFunc.read.value: self.infer_type_from_read_function_call,
        }
        infer_type_from_function_call_dispatcher = {
            nodes.BuiltinFunc: lambda value, supertype: dispatch(
                infer_type_from_builtin_func_call_dispatcher, value.function_path.value, value.args, supertype
            ),
        }

        infer_type_dispatcher = {
            nodes.IntegerLiteral: self.infer_type_from_integer_literal,
            nodes.DecimalLiteral: self.infer_type_from_decimal_literal,
            nodes.StringLiteral: lambda _, supertype: self.unify_types(nodes.BuiltinType.string, supertype),
            nodes.VectorLiteral: self.infer_type_from_vector_literal,
            nodes.CharLiteral: lambda _, supertype: self.unify_types(nodes.BuiltinType.char, supertype),
            nodes.BoolLiteral: lambda _, supertype: self.unify_types(nodes.BuiltinType.bool, supertype),
            nodes.BinaryExpression: lambda value, supertype: self.infer_type_from_binary_expression(
                value.left, value.operator, value.right, supertype),
            nodes.Name: self.infer_type_from_name,
            nodes.FunctionCall: lambda value, supertype: dispatch(
                infer_type_from_function_call_dispatcher, type(value.function_path), value, supertype
            ),
            nodes.Cast: lambda value, supertype: self.unify_types(value.to_type, supertype)
        }
        self.infer_type = lambda value, supertype=None: dispatch(infer_type_dispatcher, type(value), value, supertype)

        self.unify_types_dispatcher = {
            (nodes.BuiltinType, nodes.BuiltinType): self.unify_builtin_types,
            (nodes.VectorType, nodes.VectorType): self.unify_vector_types,
            (nodes.TemplateType, nodes.TemplateType): self.unify_template_types,

            (nodes.BuiltinType, nodes.VectorType): self.unification_failed,
            (nodes.BuiltinType, nodes.TemplateType): self.unify_builtin_type_with_template_type,

            (nodes.VectorType, nodes.BuiltinType): lambda subtype, supertype: (
                supertype if supertype.value == nodes.BuiltinType.convertible_to_string.value
                else self.unification_failed(subtype, supertype)
            ),
            (nodes.VectorType, nodes.TemplateType): self.unify_vector_type_with_template_type,

            (nodes.TemplateType, nodes.BuiltinType): self.unification_template_subtype_success,
            (nodes.TemplateType, nodes.VectorType): self.unification_template_subtype_success,
        }

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
        value = self.clarify_expression(node.value)
        clarified_type = self.clarify_type(node.type)
        if value:
            type_ = self.infer_type(value, supertype=clarified_type)
        else:
            assert clarified_type is not None
            type_ = self.unify_types(clarified_type, clarified_type)
        self.env.add_constant(node.line, node.name, type_, value, analyzed_value=self.analyzer_eval_expression(value))
        return nodes.ConstantDeclaration(node.line, node.name, type_, value)

    def analyze_variable_declaration(self, node: nodes.VariableDeclaration) -> nodes.VariableDeclaration:
        self.current_line = node.line
        value = self.clarify_expression(node.value)
        clarified_type = self.clarify_type(node.type)
        if value:
            type_ = self.infer_type(value, supertype=clarified_type)
        else:
            assert clarified_type is not None
            type_ = self.unify_types(clarified_type, clarified_type)
        self.env.add_variable(node.line, node.name, type_, analyzed_value=self.analyzer_eval_expression(value))
        return nodes.VariableDeclaration(node.line, node.name, type_, value)

    def analyze_function_declaration(self, node: nodes.FunctionDeclaration) -> nodes.FunctionDeclaration:
        self.current_line = node.line
        args = []
        for arg in node.args:
            clarified_type = self.clarify_type(arg.type)
            args.append(nodes.Argument(arg.name, self.unify_types(clarified_type, clarified_type)))
        clarified_return_type = self.clarify_type(node.return_type)
        return_type = self.unify_types(clarified_return_type, clarified_return_type)
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
        type_ = self.clarify_type(node.type)
        self.env.add_field(self.parents[-1], node.line, node.name, type_)
        return nodes.FieldDeclaration(node.line, node.name, type_)

    def analyze_assignment(self, node: nodes.Assignment) -> nodes.Assignment:
        self.current_line = node.line
        left = self.clarify_expression(node.left)
        if not self.can_assign(left):
            raise errors.AngelConstantReassignment(left, self.get_code(node.line), self.get_definition_code(left))
        if node.operator.value != nodes.Operator.eq.value:
            right: nodes.Expression = nodes.BinaryExpression(
                node.left, node.operator.to_arithmetic_operator(), node.right
            )
        else:
            right = node.right
        right = self.clarify_expression(right)
        # Type checking
        self.infer_type(right, supertype=self.infer_type(left))
        result = nodes.Assignment(node.line, left, nodes.Operator.eq, right)
        self.analyzer_reassign(result)
        return result

    def repl_eval_assignment(self, node: nodes.Assignment) -> None:
        self.repl_reassign(node)

    def analyze_function_call(self, node: nodes.FunctionCall) -> nodes.FunctionCall:
        self.current_line = node.line
        function_path = self.clarify_expression(node.function_path)
        args = [self.clarify_expression(arg) for arg in node.args]
        return self.checked_function_call(node.line, function_path, args)

    def analyze_while_statement(self, node: nodes.While) -> nodes.While:
        self.current_line = node.line
        condition = self.clarify_expression(node.condition)
        self.infer_type(condition, supertype=nodes.BuiltinType.bool)
        self.env.inc_nesting()
        body = self.analyze(node.body)
        self.env.dec_nesting()
        return nodes.While(node.line, condition, body)

    def analyze_if_statement(self, node: nodes.If) -> nodes.If:
        self.current_line = node.line
        condition = self.clarify_expression(node.condition)
        self.infer_type(condition, supertype=nodes.BuiltinType.bool)
        self.env.inc_nesting()
        body = self.analyze(node.body)
        self.env.dec_nesting()
        elifs = []
        for elif_condition, elif_body in node.elifs:
            elif_condition_clarified = self.clarify_expression(elif_condition)
            self.infer_type(elif_condition_clarified, supertype=nodes.BuiltinType.bool)
            self.env.inc_nesting()
            elif_body_clarified = self.analyze(elif_body)
            self.env.dec_nesting()
            elifs.append((elif_condition_clarified, elif_body_clarified))
        self.env.inc_nesting()
        else_ = self.analyze(node.else_)
        self.env.dec_nesting()
        return nodes.If(node.line, condition, body, elifs, else_)

    def analyze_return_statement(self, node: nodes.Return) -> nodes.Return:
        self.current_line = node.line
        value = self.clarify_expression(node.value)
        self.infer_type(value, supertype=self.function_return_types[-1])
        return nodes.Return(node.line, value)

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

    @t.overload
    def clarify_expression(self, value: None) -> None:
        ...

    @t.overload
    def clarify_expression(self, value: nodes.Expression) -> nodes.Expression:
        ...

    def clarify_expression(self, value):
        if isinstance(value, nodes.Name):
            for cls in (nodes.BuiltinFunc, nodes.BoolLiteral):
                try:
                    clarified = cls(value.member)
                except ValueError:
                    continue
                else:
                    return clarified
            return value
        elif isinstance(value, nodes.BinaryExpression):
            return self.clarify_binary_expression(
                self.clarify_expression(value.left), value.operator, self.clarify_expression(value.right))
        elif isinstance(value, nodes.FunctionCall):
            return self.analyze_function_call(value)
        elif isinstance(value, nodes.VectorLiteral):
            return nodes.VectorLiteral([self.clarify_expression(element) for element in value.elements])
        return value

    def clarify_binary_expression(
            self, left: nodes.Expression, operator: nodes.Operator, right: nodes.Expression
    ) -> nodes.Expression:
        left_type = self.infer_type(left)
        if isinstance(left_type, nodes.BuiltinType):
            # It is easier to translate.
            return nodes.BinaryExpression(left, operator, right)
        raise errors.AngelNotImplemented

    @t.overload
    def clarify_type(self, type_: None) -> None:
        ...

    @t.overload
    def clarify_type(self, type_: nodes.Type) -> nodes.Type:
        ...

    def clarify_type(self, type_: t.Optional[nodes.Type]) -> t.Optional[nodes.Type]:
        if isinstance(type_, nodes.Name):
            try:
                builtin_type = nodes.BuiltinType(type_.member)
            except ValueError:
                return type_
            else:
                return builtin_type
        elif isinstance(type_, nodes.VectorType):
            return nodes.VectorType(self.clarify_type(type_.subtype))
        return type_

    def can_assign_name(self, value: nodes.Name) -> bool:
        entry = self.env[value.member]
        if isinstance(entry, entries.VariableEntry):
            return True
        elif isinstance(entry, entries.ConstantEntry):
            return not entry.has_value
        return False

    def infer_type_from_integer_literal(
            self, value: nodes.IntegerLiteral, supertype: t.Optional[nodes.Type]) -> nodes.Type:
        possible_types = get_possible_int_types_based_on_value(int(value.value))
        try:
            result = self.unify_list_types(possible_types, supertype)
        except errors.AngelTypeError:
            if supertype is None:
                if int(value.value) > 0:
                    message = f"{value.value} is too big"
                else:
                    message = f"{value.value} is too small"
            elif isinstance(supertype, nodes.BuiltinType) and supertype.is_finite_int_type:
                message = f"{value.value} is not in range {supertype.get_range()}"
            else:
                message = f"'{supertype.to_code()}' is not a possible type for {value.value}"
            raise errors.AngelTypeError(message, self.get_code(self.current_line), possible_types)
        else:
            return result

    def infer_type_from_decimal_literal(
            self, value: nodes.DecimalLiteral, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        possible_types = get_possible_float_types_base_on_value(value.value)
        try:
            result = self.unify_list_types(possible_types, supertype)
        except errors.AngelTypeError:
            if supertype is None:
                if int(value.value) > 0:
                    message = f"{value.value} is too big"
                else:
                    message = f"{value.value} is too small"
            elif isinstance(supertype, nodes.BuiltinType) and supertype.is_finite_float_type:
                message = f"{value.value} is not in range {supertype.get_range()}"
            else:
                message = f"'{supertype.to_code()}' is not a possible type for {value.value}"
            raise errors.AngelTypeError(message, self.get_code(self.current_line), possible_types)
        else:
            return result

    def infer_type_from_vector_literal(
            self, value: nodes.VectorLiteral, supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        element_type: nodes.Type = self.create_template_type()
        for element in value.elements:
            current_element_type = self.infer_type(element)
            try:
                element_type = self.unify_types(element_type, current_element_type)
            except errors.AngelTypeError:
                element_type = self.unify_types(current_element_type, element_type)
        return self.unify_types(nodes.VectorType(element_type), supertype)

    def infer_type_from_name(self, value: nodes.Name, supertype: t.Optional[nodes.Type]) -> nodes.Type:
        entry = self.env[value.member]
        if entry is None:
            raise errors.AngelNameError(value, self.get_code(self.current_line))
        elif isinstance(entry, (entries.ConstantEntry, entries.VariableEntry)):
            return self.unify_types(entry.type, supertype)
        else:
            raise errors.AngelNotImplemented

    def infer_type_from_binary_expression(
            self, left: nodes.Expression, operator: nodes.Operator, right: nodes.Expression,
            supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        result = self.analyzer_eval_expression(nodes.BinaryExpression(left, operator, right))
        if isinstance(result, bool):
            return self.unify_types(nodes.BuiltinType.bool, supertype)
        elif isinstance(result, (int, float)):
            return self.infer_type_from_integer_literal(nodes.IntegerLiteral(str(int(result))), supertype)
        elif isinstance(result, Decimal):
            return self.infer_type_from_decimal_literal(nodes.DecimalLiteral(str(result)), supertype)
        elif isinstance(result, nodes.DynValue):
            return self.unify_types(result.type, supertype)
        else:
            raise errors.AngelNotImplemented

    def infer_type_from_read_function_call(
            self, _: t.List[nodes.Expression], supertype: t.Optional[nodes.Type]
    ) -> nodes.Type:
        return self.unify_types(nodes.BuiltinType.string, supertype)

    def unify_types(self, subtype: nodes.Type, supertype: t.Optional[nodes.Type]) -> nodes.Type:
        if supertype is None:
            return subtype
        return dispatch(self.unify_types_dispatcher, (type(subtype), type(supertype)), subtype, supertype)

    def unify_builtin_types(self, subtype: nodes.BuiltinType, supertype: nodes.BuiltinType) -> nodes.Type:
        if supertype.value in subtype.get_builtin_supertypes():
            return supertype
        raise errors.AngelTypeError(
            f"{supertype.to_code()} is not a supertype of {subtype.to_code()}", self.get_code(self.current_line),
            [subtype]
        )

    def unify_builtin_type_with_template_type(
            self, subtype: nodes.BuiltinType, supertype: nodes.TemplateType
    ) -> nodes.Type:
        assert self.template_types[supertype.id] is None
        self.template_types[supertype.id] = subtype
        return subtype

    def unify_vector_type_with_template_type(
            self, subtype: nodes.VectorType, supertype: nodes.TemplateType
    ) -> nodes.Type:
        assert self.template_types[supertype.id] is None
        self.template_types[supertype.id] = subtype
        return subtype

    def unification_template_subtype_success(self, subtype: nodes.TemplateType, supertype: nodes.Type) -> nodes.Type:
        assert self.template_types[subtype.id] is None
        self.template_types[subtype.id] = supertype
        return supertype

    def unify_vector_types(self, subtype: nodes.VectorType, supertype: nodes.VectorType) -> nodes.Type:
        # TODO: improve error message
        return nodes.VectorType(self.unify_types(subtype.subtype, supertype.subtype))

    def unification_failed(self, subtype: nodes.Type, supertype: nodes.Type) -> nodes.Type:
        raise errors.AngelTypeError(
            f"{supertype.to_code()} is not a supertype of {subtype.to_code()}", self.get_code(self.current_line),
            [subtype]
        )

    def unify_template_types(self, subtype: nodes.TemplateType, supertype: nodes.TemplateType) -> nodes.Type:
        real_type = self.template_types[subtype.id] or self.template_types[supertype.id]
        self.template_types[subtype.id] = real_type
        self.template_types[supertype.id] = real_type
        return real_type or subtype

    def unify_list_types(self, subtypes: t.Sequence[nodes.Type], supertype: t.Optional[nodes.Type]) -> nodes.Type:
        fail = None
        for subtype in subtypes:
            try:
                result = self.unify_types(subtype, supertype)
            except errors.AngelTypeError as e:
                fail = e
            else:
                return result
        if fail is not None:
            raise errors.AngelTypeError(fail.message, self.get_code(self.current_line), list(subtypes))
        raise errors.AngelTypeError("no subtypes to unify", self.get_code(self.current_line), list(subtypes))

    def tweak_for_printing(self, value: nodes.Expression, value_type: nodes.Type) -> nodes.Expression:
        if isinstance(value_type, nodes.BuiltinType):
            if value_type.value == nodes.BuiltinType.i8.value:
                return nodes.Cast(value, nodes.BuiltinType.i16)
            elif value_type.value == nodes.BuiltinType.u8.value:
                return nodes.Cast(value, nodes.BuiltinType.u16)
        return value

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
        if self.repl_eval_expression(node.condition):
            return self.repl_eval_ast(node.body)
        for elif_condition, elif_body in node.elifs:
            if self.repl_eval_expression(elif_condition):
                return self.repl_eval_ast(elif_body)
        return self.repl_eval_ast(node.else_)

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
        return value

    def repl_eval_read_function_call(self, args: t.List[nodes.Expression]) -> t.Any:
        return input(self.repl_eval_expression(args[0]))

    def analyzer_eval_read_function_call(self, _: t.List[nodes.Expression]) -> t.Any:
        return nodes.DynValue(nodes.BuiltinType.string)

    def create_template_type(self) -> nodes.TemplateType:
        self.template_types.append(None)
        self.template_type_id += 1
        return nodes.TemplateType(self.template_type_id)
