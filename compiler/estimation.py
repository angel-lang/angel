import typing as t
from collections import namedtuple
from decimal import Decimal
from functools import partial

from . import estimation_nodes as enodes, nodes, environment, errors, type_checking, environment_entries as entries
from .utils import dispatch
from .constants import builtin_funcs, string_fields


EstimatedObjects = namedtuple("EstimatedObjects", ['builtin_funcs', 'string_fields'])


class Evaluator:
    def __init__(self, estimated_objs: EstimatedObjects, env: t.Optional[environment.Environment] = None) -> None:
        self.env = env or environment.Environment()
        self.code = errors.Code()
        self.repl_tmp_count = 0
        self.type_checker = type_checking.TypeChecker()

        self.estimated_objs = estimated_objs

        self.expression_dispatcher = {
            nodes.Name: self.estimate_name,
            nodes.SpecialName: self.estimate_special_name,
            nodes.Field: self.estimate_field,
            nodes.BinaryExpression: self.estimate_binary_expression,
            nodes.Cast: self.estimate_cast,
            nodes.FunctionCall: self.estimate_function_call,
            nodes.MethodCall: self.estimate_method_call,
            nodes.BuiltinFunc: lambda func: self.estimated_objs.builtin_funcs[func.value],

            nodes.OptionalSomeCall: self.estimate_optional_some_call,
            nodes.OptionalSomeValue: self.estimate_optional_some_value,
            nodes.OptionalTypeConstructor: self.estimate_optional_constructor,

            nodes.IntegerLiteral: self.estimate_integer_literal,
            nodes.DecimalLiteral: self.estimate_decimal_literal,
            nodes.StringLiteral: self.estimate_string_literal,
            nodes.CharLiteral: self.estimate_char_literal,
            nodes.BoolLiteral: self.estimate_bool_literal,
            nodes.VectorLiteral: self.estimate_vector_literal,
            nodes.DictLiteral: self.estimate_dict_literal,
        }

        add_dispatcher = {
            (enodes.Int, enodes.Int): self.estimate_add_ints,
        }

        sub_dispatcher = {
            (enodes.Int, enodes.Int): self.estimate_sub_ints,
        }

        mul_dispatcher = {
            (enodes.Int, enodes.Int): self.estimate_mul_ints,
        }

        div_dispatcher = {
            (enodes.Int, enodes.Int): self.estimate_div_ints,
        }

        eq_dispatcher = {
            (enodes.Int, enodes.Int): lambda x, y: enodes.Bool(x.value == y.value),
            (enodes.String, enodes.String): lambda x, y: enodes.Bool(x.value == y.value),
            (enodes.Char, enodes.Char): lambda x, y: enodes.Bool(x.value == y.value),
            (enodes.Bool, enodes.Bool): lambda x, y: enodes.Bool(x.value == y.value),
            (enodes.OptionalConstructor, enodes.OptionalConstructor): lambda x, y: enodes.Bool(x.value == y.value),

            (enodes.OptionalSomeCall, enodes.OptionalConstructor): lambda x, y: enodes.Bool(False),
        }

        lt_dispatcher = {
            (enodes.Int, enodes.Int): lambda x, y: enodes.Bool(x.value < y.value),
        }

        gt_dispatcher = {
            (enodes.Int, enodes.Int): lambda x, y: enodes.Bool(x.value > y.value),
        }

        self.binary_operator_dispatcher = {
            nodes.Operator.add.value: lambda x, y: dispatch(add_dispatcher, (type(x), type(y)), x, y),
            nodes.Operator.sub.value: lambda x, y: dispatch(sub_dispatcher, (type(x), type(y)), x, y),
            nodes.Operator.mul.value: lambda x, y: dispatch(mul_dispatcher, (type(x), type(y)), x, y),
            nodes.Operator.div.value: lambda x, y: dispatch(div_dispatcher, (type(x), type(y)), x, y),

            nodes.Operator.eq_eq.value: lambda x, y: dispatch(eq_dispatcher, (type(x), type(y)), x, y),
            nodes.Operator.lt.value: lambda x, y: dispatch(lt_dispatcher, (type(x), type(y)), x, y),
            nodes.Operator.gt.value: lambda x, y: dispatch(gt_dispatcher, (type(x), type(y)), x, y),
        }

        self.assignment_dispatcher = {
            nodes.Name: self.estimate_name_assignment,
        }

        self.node_dispatcher = {
            nodes.ConstantDeclaration: self.estimate_constant_declaration,
            nodes.VariableDeclaration: self.estimate_variable_declaration,
            nodes.FunctionDeclaration: self.estimate_function_declaration,
            nodes.FieldDeclaration: self.estimate_field_declaration,
            nodes.InitDeclaration: self.estimate_init_declaration,
            nodes.MethodDeclaration: self.estimate_method_declaration,
            nodes.StructDeclaration: self.estimate_struct_declaration,
            nodes.FunctionCall: self.estimate_expression,
            nodes.MethodCall: self.estimate_expression,

            nodes.Return: self.estimate_return,
            nodes.Break: self.estimate_break,
            nodes.Assignment: lambda statement: dispatch(
                self.assignment_dispatcher, type(statement.left), statement.left, statement.right
            ),
            nodes.While: self.estimate_while_statement,
            nodes.If: self.estimate_if_statement,
        }

    def estimate_node(self, node: nodes.Node) -> t.Optional[enodes.Expression]:
        return dispatch(self.node_dispatcher, type(node), node)

    def estimate_ast(self, ast: nodes.AST) -> t.Optional[enodes.Expression]:
        result = None
        for node in ast:
            result = self.estimate_node(node)
            if result is not None and not isinstance(result, enodes.Void):
                return result
        return result

    def estimate_constant_declaration(self, declaration: nodes.ConstantDeclaration) -> None:
        assert declaration.type is not None
        estimated = None
        if declaration.value is not None:
            estimated = self.estimate_expression(declaration.value)
        self.env.add_constant(
            declaration.line, declaration.name, declaration.type, declaration.value, estimated
        )

    def estimate_variable_declaration(self, declaration: nodes.VariableDeclaration) -> None:
        assert declaration.type is not None
        estimated = None
        if declaration.value is not None:
            estimated = self.estimate_expression(declaration.value)
        self.env.add_variable(
            declaration.line, declaration.name, declaration.type, declaration.value, estimated
        )

    def estimate_function_declaration(self, declaration: nodes.FunctionDeclaration) -> None:
        self.env.add_function(declaration.line, declaration.name, declaration.args, declaration.return_type)
        self.env.update_function_body(declaration.name, declaration.body)

    def estimate_method_declaration(self, declaration: nodes.MethodDeclaration) -> None:
        self.env.add_method(declaration.line, declaration.name, declaration.args, declaration.return_type)
        self.env.update_method_body(declaration.name, declaration.body)

    def estimate_init_declaration(self, declaration: nodes.InitDeclaration) -> None:
        self.env.add_init_declaration(declaration.line, declaration.args)
        self.env.update_init_declaration_body(declaration.args, declaration.body)

    def estimate_struct_declaration(self, declaration: nodes.StructDeclaration) -> None:
        # list(...) for mypy
        self.env.add_struct(declaration.line, declaration.name)
        self.env.inc_nesting(declaration.name)
        self.estimate_ast(list(declaration.private_fields))
        self.estimate_ast(list(declaration.public_fields))
        self.estimate_ast(list(declaration.init_declarations))
        self.estimate_ast(list(declaration.private_methods))
        self.estimate_ast(list(declaration.public_methods))
        self.env.dec_nesting(declaration.name)

    def estimate_field_declaration(self, declaration: nodes.FieldDeclaration) -> None:
        self.env.add_field(declaration.line, declaration.name, declaration.type)

    def estimate_name_assignment(self, name: nodes.Name, value: nodes.Expression) -> None:
        if name.module:
            assert 0, "Module system is not supported"
        right = self.estimate_expression(value)
        entry = self.env[name.member]
        # Estimation is performed after name checking.
        assert entry is not None
        if isinstance(entry, entries.ConstantEntry):
            assert not entry.has_value
            entry.estimated_value = right
            entry.has_value = True
        elif isinstance(entry, entries.VariableEntry):
            entry.estimated_value = right
        else:
            assert 0, f"REPL cannot reassign {type(entry)}"

    def estimate_while_statement(self, statement: nodes.While) -> t.Optional[enodes.Expression]:
        condition, body, assignment = self.desugar_if_let(statement.condition, statement.body)
        estimated_condition = self.estimate_expression(condition)
        if assignment is not None:
            body.append(assignment)
        assert isinstance(estimated_condition, enodes.Bool)
        while estimated_condition.value:
            result = self.estimate_ast(body)
            if isinstance(result, enodes.Break):
                break
            elif result is not None:
                return result
            estimated_condition = self.estimate_expression(condition)
            assert isinstance(estimated_condition, enodes.Bool)
        return None

    def desugar_if_let(
            self, condition: nodes.Expression, body: nodes.AST
    ) -> t.Tuple[nodes.Expression, nodes.AST, t.Optional[nodes.Assignment]]:
        assignment = None
        if isinstance(condition, nodes.ConstantDeclaration):
            assert condition.value is not None
            tmp_right = self.create_repl_tmp(condition.value)
            to_prepend: t.List[nodes.Node] = [
                nodes.VariableDeclaration(
                    condition.line, condition.name, condition.type, nodes.OptionalSomeValue(tmp_right)
                )
            ]
            body = to_prepend + body
            assignment = nodes.Assignment(
                condition.line, tmp_right, nodes.Operator.eq, condition.value
            )
            condition = nodes.BinaryExpression(tmp_right, nodes.Operator.neq, nodes.OptionalTypeConstructor.none)
        return condition, body, assignment

    def estimate_if_statement(self, statement: nodes.If) -> t.Optional[enodes.Expression]:
        condition, body, _ = self.desugar_if_let(statement.condition, statement.body)
        evaluated_condition = self.estimate_expression(condition)
        assert isinstance(evaluated_condition, enodes.Bool)
        if evaluated_condition.value:
            return self.estimate_ast(body)
        for elif_condition, elif_body in statement.elifs:
            elif_condition, elif_body, _ = self.desugar_if_let(elif_condition, elif_body)
            cond = self.estimate_expression(elif_condition)
            assert isinstance(cond, enodes.Bool)
            if cond.value:
                return self.estimate_ast(elif_body)
        return self.estimate_ast(statement.else_)

    def create_repl_tmp(self, value: nodes.Expression) -> nodes.Name:
        name = nodes.Name("__repl_tmp" + str(self.repl_tmp_count))
        self.repl_tmp_count += 1
        self.env.add_variable(0, name, self.infer_type(value), value, estimated_value=self.estimate_expression(value))
        return name

    def estimate_return(self, statement: nodes.Return) -> enodes.Expression:
        return self.estimate_expression(statement.value)

    def estimate_break(self, _: nodes.Break) -> enodes.Break:
        return enodes.Break()

    def estimate_add_ints(self, x: enodes.Int, y: enodes.Int) -> enodes.Int:
        value = x.value + y.value
        new_type = self.infer_type(nodes.IntegerLiteral(str(value)))
        assert isinstance(new_type, nodes.BuiltinType)
        return enodes.Int(value, new_type)

    def estimate_sub_ints(self, x: enodes.Int, y: enodes.Int) -> enodes.Int:
        value = x.value - y.value
        new_type = self.infer_type(nodes.IntegerLiteral(str(value)))
        assert isinstance(new_type, nodes.BuiltinType)
        return enodes.Int(value, new_type)

    def estimate_mul_ints(self, x: enodes.Int, y: enodes.Int) -> enodes.Int:
        value = x.value * y.value
        new_type = self.infer_type(nodes.IntegerLiteral(str(value)))
        assert isinstance(new_type, nodes.BuiltinType)
        return enodes.Int(value, new_type)

    def estimate_div_ints(self, x: enodes.Int, y: enodes.Int) -> enodes.Float:
        if y.value == 0:
            raise errors.AngelDivByZero
        value = Decimal(x.value) / Decimal(y.value)
        new_type = self.infer_type(nodes.DecimalLiteral(str(value)))
        assert isinstance(new_type, nodes.BuiltinType)
        return enodes.Float(value, new_type)

    def estimate_expression(self, expression: nodes.Expression) -> enodes.Expression:
        return dispatch(self.expression_dispatcher, type(expression), expression)

    def estimate_name(self, name: nodes.Name) -> enodes.Expression:
        if name.module:
            assert 0, "Module system is not supported"
        entry = self.env[name.member]
        # Estimation is performed after name checking.
        assert entry is not None
        if isinstance(entry, (entries.ConstantEntry, entries.VariableEntry)):
            assert entry.estimated_value is not None
            return entry.estimated_value
        elif isinstance(entry, entries.FunctionEntry):
            return enodes.Function(entry.args, entry.return_type, specification=entry.body)
        else:
            # @Completeness: must have branches for all entry types
            assert 0, f"{self.estimate_name} cannot dispatch entry type {type(entry)}"

    def estimate_field(self, field: nodes.Field) -> enodes.Expression:
        base = self.estimate_expression(field.base)
        if isinstance(base, enodes.String):
            return self.estimated_objs.string_fields[field.field]
        else:
            assert 0, f"Cannot estimate field from '{base}'"

    def estimate_special_name(self, special_name: nodes.SpecialName) -> enodes.Expression:
        return self.estimate_name(nodes.Name(special_name.value))

    def estimate_function_call(self, call: nodes.FunctionCall) -> enodes.Expression:
        function = self.estimate_expression(call.function_path)
        assert isinstance(function, enodes.Function)
        return self.estimate_body_of_function(function, call.args)

    # @Rename
    def estimate_body_of_function(
            self, function: enodes.Function, args: t.List[nodes.Expression],
            self_arg: t.Optional[nodes.Expression] = None
    ) -> enodes.Expression:
        arguments = [self.estimate_expression(argument) for argument in args]
        if isinstance(function.specification, list):
            self.env.inc_nesting()
            for arg, value, estimated in zip(function.args, args, arguments):
                self.env.add_constant(0, arg.name, arg.type, value, estimated)
            result = self.estimate_ast(function.specification)
            assert result is not None
            self.env.dec_nesting()
            return result
        if self_arg:
            return function.specification(self.estimate_expression(self_arg), *arguments)
        return function.specification(*arguments)

    def estimate_method_call(self, call: nodes.MethodCall) -> enodes.Expression:
        method = self.estimate_expression(nodes.Field(call.line, call.instance_path, call.method))
        assert isinstance(method, enodes.Function)
        return self.estimate_body_of_function(method, call.args, self_arg=call.instance_path)

    def estimate_binary_expression(self, expression: nodes.BinaryExpression) -> enodes.Expression:
        left = self.estimate_expression(expression.left)
        right = self.estimate_expression(expression.right)
        if expression.operator.value == nodes.Operator.neq.value:
            result = dispatch(self.binary_operator_dispatcher, nodes.Operator.eq_eq.value, left, right)
            assert isinstance(result, enodes.Bool)
            return enodes.Bool(not result.value)
        elif expression.operator.value == nodes.Operator.lt_eq.value:
            result = dispatch(self.binary_operator_dispatcher, nodes.Operator.gt.value, left, right)
            assert isinstance(result, enodes.Bool)
            return enodes.Bool(not result.value)
        elif expression.operator.value == nodes.Operator.gt_eq.value:
            result = dispatch(self.binary_operator_dispatcher, nodes.Operator.lt.value, left, right)
            assert isinstance(result, enodes.Bool)
            return enodes.Bool(not result.value)
        return dispatch(self.binary_operator_dispatcher, expression.operator.value, left, right)

    def estimate_cast(self, cast: nodes.Cast) -> enodes.Expression:
        value = self.estimate_expression(cast.value)
        # Only compiler can cast (for now).
        assert isinstance(value, enodes.Int)
        assert isinstance(cast.to_type, nodes.BuiltinType) and cast.to_type.is_finite_int_type
        return enodes.Int(value.value, cast.to_type)

    def estimate_optional_some_call(self, call: nodes.OptionalSomeCall) -> enodes.Expression:
        return enodes.OptionalSomeCall(self.estimate_expression(call.value))

    def estimate_optional_some_value(self, value: nodes.OptionalSomeValue) -> enodes.Expression:
        some_call = self.estimate_expression(value.value)
        assert isinstance(some_call, enodes.OptionalSomeCall)
        return some_call.inner_value

    def estimate_optional_constructor(self, constructor: nodes.OptionalTypeConstructor) -> enodes.Expression:
        return enodes.OptionalConstructor(constructor.value)

    def estimate_integer_literal(self, literal: nodes.IntegerLiteral) -> enodes.Expression:
        int_type = self.infer_type(literal)
        assert isinstance(int_type, nodes.BuiltinType)
        return enodes.Int(int(literal.value), int_type)

    def estimate_decimal_literal(self, literal: nodes.DecimalLiteral) -> enodes.Expression:
        float_type = self.infer_type(literal)
        assert isinstance(float_type, nodes.BuiltinType)
        return enodes.Float(Decimal(literal.value), float_type)

    def estimate_string_literal(self, literal: nodes.StringLiteral) -> enodes.Expression:
        return enodes.String(literal.value)

    def estimate_char_literal(self, literal: nodes.CharLiteral) -> enodes.Expression:
        return enodes.Char(literal.value)

    def estimate_bool_literal(self, literal: nodes.BoolLiteral) -> enodes.Expression:
        return enodes.Bool(literal.value == nodes.BoolLiteral.true.value)

    def estimate_vector_literal(self, literal: nodes.VectorLiteral) -> enodes.Expression:
        vector_type = self.infer_type(literal)
        assert isinstance(vector_type, nodes.VectorType)
        return enodes.Vector([self.estimate_expression(element) for element in literal.elements], vector_type.subtype)

    def estimate_dict_literal(self, literal: nodes.DictLiteral) -> enodes.Expression:
        dict_type = self.infer_type(literal)
        assert isinstance(dict_type, nodes.DictType)
        return enodes.Dict(
            [self.estimate_expression(key) for key in literal.keys],
            [self.estimate_expression(value) for value in literal.values],
            dict_type.key_type, dict_type.value_type
        )

    def infer_type(self, expression: nodes.Expression, supertype: t.Optional[nodes.Type] = None) -> nodes.Type:
        self.type_checker.update_context(self.env, self.code)
        return self.type_checker.infer_type(expression, supertype)

    def update_context(self, env: environment.Environment, code: errors.Code = None):
        self.env = env
        self.code = code or self.code

    @property
    def supported_expression_nodes(self):
        return set(subclass.__name__ for subclass in self.expression_dispatcher.keys())

    @property
    def supported_nodes(self):
        return set(subclass.__name__ for subclass in self.node_dispatcher.keys())


Estimator = partial(Evaluator, EstimatedObjects(builtin_funcs=builtin_funcs, string_fields=string_fields))
