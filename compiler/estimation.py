import typing as t
import unittest
from collections import namedtuple
from decimal import Decimal
from functools import partial
from itertools import zip_longest

from . import estimation_nodes as enodes, nodes, environment, errors, type_checking, environment_entries as entries
from .utils import dispatch, NODES, EXPRS, ASSIGNMENTS
from .constants import builtin_funcs, string_fields, vector_fields, dict_fields


EstimatedObjects = namedtuple("EstimatedObjects", ['builtin_funcs', 'string_fields', 'vector_fields', 'dict_fields'])
EstimatedFields = t.Dict[str, t.Union[t.Callable[..., enodes.Expression], enodes.Expression]]


class Evaluator(unittest.TestCase):
    def __init__(self, estimated_objs: EstimatedObjects, env: t.Optional[environment.Environment] = None) -> None:
        super().__init__()
        self.env = env or environment.Environment()
        self.code = errors.Code()
        self.repl_tmp_count = 0
        self.type_checker = type_checking.TypeChecker()

        self.estimated_objs = estimated_objs

        self.expression_dispatcher = {
            nodes.Name: self.estimate_name,
            nodes.SpecialName: self.estimate_special_name,
            nodes.Field: self.estimate_field,
            nodes.Subscript: self.estimate_subscript,
            nodes.BinaryExpression: self.estimate_binary_expression,
            nodes.Cast: self.estimate_cast,
            nodes.FunctionCall: self.estimate_function_call,
            nodes.MethodCall: self.estimate_method_call,
            nodes.BuiltinFunc: lambda func: self.estimated_objs.builtin_funcs[func.value],
            nodes.ConstantDeclaration: self.estimate_constant_declaration,

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
            (enodes.String, enodes.String): self.estimate_add_strings,
            (enodes.Vector, enodes.Vector): self.estimate_add_vectors,
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

        self.estimate_field_dispatcher = {
            enodes.String: lambda base, f: self.estimate_builtin_field(self.estimated_objs.string_fields, base, f),
            enodes.Vector: lambda base, f: self.estimate_builtin_field(self.estimated_objs.vector_fields, base, f),
            enodes.Dict: lambda base, f: self.estimate_builtin_field(self.estimated_objs.dict_fields, base, f),
            enodes.Instance: self.estimate_instance_field,
            enodes.Algebraic: self.estimate_algebraic_field,
            enodes.AlgebraicConstructorInstance: self.estimate_algebraic_constructor_instance_field,
        }

        self.assignment_dispatcher = {
            nodes.Name: self.estimate_name_assignment,
            nodes.Field: self.estimate_field_assignment,
            nodes.Subscript: self.estimate_subscript_assignment,
        }

        self.node_dispatcher = {
            nodes.ConstantDeclaration: self.estimate_constant_declaration,
            nodes.VariableDeclaration: self.estimate_variable_declaration,
            nodes.FunctionDeclaration: self.estimate_function_declaration,
            nodes.FieldDeclaration: self.estimate_field_declaration,
            nodes.InitDeclaration: self.estimate_init_declaration,
            nodes.MethodDeclaration: self.estimate_method_declaration,
            nodes.StructDeclaration: self.estimate_struct_declaration,
            nodes.AlgebraicDeclaration: self.estimate_algebraic_declaration,
            nodes.InterfaceDeclaration: self.estimate_interface_declaration,
            nodes.FunctionCall: self.estimate_expression,
            nodes.MethodCall: self.estimate_expression,

            nodes.Return: self.estimate_return,
            nodes.Break: self.estimate_break,
            nodes.Assignment: lambda statement: dispatch(
                self.assignment_dispatcher, type(statement.left), statement.left, statement.right
            ),
            nodes.While: self.estimate_while_statement,
            nodes.For: self.estimate_for_statement,
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
        self.env.add_struct(declaration.line, declaration.name, declaration.parameters)
        self.env.inc_nesting(declaration.name)
        self.estimate_ast(list(declaration.private_fields))
        self.estimate_ast(list(declaration.public_fields))
        self.estimate_ast(list(declaration.init_declarations))
        self.estimate_ast(list(declaration.private_methods))
        self.estimate_ast(list(declaration.public_methods))
        self.env.dec_nesting(declaration.name)

    def estimate_algebraic_declaration(self, declaration: nodes.AlgebraicDeclaration) -> None:
        self.env.add_algebraic(declaration.line, declaration.name, declaration.parameters)
        self.env.inc_nesting(declaration.name)
        self.estimate_ast(list(declaration.constructors))
        self.estimate_ast(list(declaration.private_methods))
        self.estimate_ast(list(declaration.public_methods))
        self.env.dec_nesting(declaration.name)

    def estimate_interface_declaration(self, declaration: nodes.InterfaceDeclaration) -> None:
        self.env.add_interface(
            declaration.line, declaration.name, declaration.parameters, declaration.parent_interfaces
        )
        self.env.inc_nesting(declaration.name)
        self.estimate_ast(list(declaration.fields))
        self.estimate_ast(list(declaration.methods))
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

    def estimate_field_assignment(self, field: nodes.Field, value: nodes.Expression) -> None:
        estimated_value = self.estimate_expression(value)
        # @Cleanup: Move to dispatcher
        if isinstance(field.base, nodes.Name):
            assert not field.base.module
            base_entry = self.env[field.base.member]
            assert isinstance(base_entry, entries.VariableEntry)
            assert isinstance(base_entry.estimated_value, enodes.Instance)
            base_entry.estimated_value.fields[field.field] = estimated_value
        elif isinstance(field.base, nodes.SpecialName):
            base_entry = self.env[field.base.value]
            assert isinstance(base_entry, entries.VariableEntry)
            assert isinstance(base_entry.estimated_value, enodes.Instance)
            base_entry.estimated_value.fields[field.field] = estimated_value
        else:
            assert 0, f"Cannot estimate field assignment with base '{field.base}'"

    def estimate_subscript_assignment(self, subscript: nodes.Subscript, value: nodes.Expression) -> None:
        estimated_value = self.estimate_expression(value)
        estimated_index = self.estimate_expression(subscript.index)
        assert isinstance(estimated_index, enodes.Int)
        assert isinstance(estimated_value, enodes.Char)
        # @Cleanup: Move to dispatcher
        if isinstance(subscript.base, nodes.Name):
            assert not subscript.base.module
            base_entry = self.env[subscript.base.member]
            # @Cleanup: separate this functionality to a function and use it in estimation of subscript
            assert isinstance(base_entry, entries.VariableEntry)
            assert isinstance(base_entry.estimated_value, enodes.String)
            new_value = list(base_entry.estimated_value.value)
            new_value[estimated_index.value] = estimated_value.value
            base_entry.estimated_value.value = "".join(new_value)
        else:
            assert 0, f"Cannot estimate subscript with base '{subscript.base}'"

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

    def estimate_for_statement(self, statement: nodes.For) -> t.Optional[enodes.Expression]:
        container = self.estimate_expression(statement.container)
        assert isinstance(container, enodes.Vector)
        self.env.inc_nesting()
        for element in container.elements:
            self.env.add_constant(
                statement.line, statement.element, container.element_type, value=None, estimated_value=element
            )
            result = self.estimate_ast(statement.body)
            if isinstance(result, enodes.Break):
                break
            elif result is not None and not isinstance(result, enodes.Void):
                self.env.dec_nesting()
                return result
        self.env.dec_nesting()
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

    def estimate_add_strings(self, x: enodes.String, y: enodes.String) -> enodes.String:
        return enodes.String(x.value + y.value)

    def estimate_add_vectors(self, x: enodes.Vector, y: enodes.Vector) -> enodes.Vector:
        element_type = x.element_type
        if not x.elements:
            element_type = y.element_type
        return enodes.Vector(x.elements + y.elements, element_type)

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
        elif isinstance(entry, entries.StructEntry):
            return enodes.Struct(entry.name)
        elif isinstance(entry, entries.AlgebraicEntry):
            return enodes.Algebraic(entry.name, entry)
        else:
            # @Completeness: must have branches for all entry types
            assert 0, f"{self.estimate_name} cannot dispatch entry type {type(entry)}"

    def estimate_builtin_field(self, fields: EstimatedFields, base: enodes.Expression, field: str) -> enodes.Expression:
        estimated = fields[field]
        if callable(estimated):
            return estimated(base)
        return estimated

    def estimate_algebraic_field(self, base: enodes.Algebraic, field: str) -> enodes.Expression:
        return enodes.AlgebraicConstructor(base.name, nodes.Name(field), entry=base.entry.constructors[field])

    def estimate_algebraic_constructor_instance_field(
        self, base: enodes.AlgebraicConstructorInstance, field: str
    ) -> enodes.Expression:
        found = base.fields.get(field)
        if found is not None:
            return found
        constructor_entry = self.env.get_algebraic(
            nodes.AlgebraicType(base.type.name, params=[], constructor=base.type.constructor)
        )
        assert isinstance(constructor_entry, entries.StructEntry)
        method_entry = constructor_entry.methods.get(field)
        if method_entry is None:
            algebraic_entry = self.env.get(base.type.name)
            assert isinstance(algebraic_entry, entries.AlgebraicEntry)
            method_entry = algebraic_entry.methods[field]
        return enodes.Function(method_entry.args, method_entry.return_type, specification=method_entry.body)

    def estimate_instance_field(self, base: enodes.Instance, field: str) -> enodes.Expression:
        found = base.fields.get(field)
        if found is not None:
            return found
        struct_entry = self.env[base.type.member]
        assert isinstance(struct_entry, entries.StructEntry)
        method_entry = struct_entry.methods[field]
        return enodes.Function(method_entry.args, method_entry.return_type, specification=method_entry.body)

    def estimate_field(self, field: nodes.Field) -> enodes.Expression:
        base = self.estimate_expression(field.base)
        return dispatch(self.estimate_field_dispatcher, type(base), base, field.field)

    def estimate_subscript(self, subscript: nodes.Subscript) -> enodes.Expression:
        base = self.estimate_expression(subscript.base)
        # @Cleanup: Move to dispatcher
        if isinstance(base, enodes.String):
            index = self.estimate_expression(subscript.index)
            assert isinstance(index, enodes.Int)
            return enodes.Char(base.value[index.value])
        elif isinstance(base, enodes.Vector):
            index = self.estimate_expression(subscript.index)
            assert isinstance(index, enodes.Int)
            return base.elements[index.value]
        elif isinstance(base, enodes.Dict):
            index = self.estimate_expression(subscript.index)
            return base.values[base.keys.index(index)]
        else:
            assert 0, f"Cannot estimate subscript from '{base}'"

    def estimate_special_name(self, special_name: nodes.SpecialName) -> enodes.Expression:
        return self.estimate_name(nodes.Name(special_name.value))

    def estimate_function_call(self, call: nodes.FunctionCall) -> t.Optional[enodes.Expression]:
        function = self.estimate_expression(call.function_path)
        if isinstance(function, enodes.Struct):
            if function.name.module:
                assert 0, "Module system is not supported"
            struct_entry = self.env[function.name.member]
            assert isinstance(struct_entry, entries.StructEntry)
            return self.match_init_declaration(function, list(struct_entry.init_declarations.values()), call.args)
        assert isinstance(function, enodes.Function)
        return self.match_function_body(function, call.args)

    def match_algebraic_constructor_init(
        self, algebraic_constructor: enodes.AlgebraicConstructor, init_declarations: t.List[entries.InitEntry],
        args: t.List[nodes.Expression]
    ) -> enodes.AlgebraicConstructorInstance:
        result = self.match_init_declaration(enodes.Struct(algebraic_constructor.constructor), init_declarations, args)
        return enodes.AlgebraicConstructorInstance(algebraic_constructor, result.fields)

    def match_init_declaration(
            self, struct: enodes.Struct, init_declarations: t.List[entries.InitEntry], args: t.List[nodes.Expression]
    ) -> enodes.Instance:
        arguments = [self.estimate_expression(argument) for argument in args]
        matched = True
        expected_major = []
        for init_entry in init_declarations:
            for arg, value in zip_longest(init_entry.args, args):
                if value is None:
                    value = arg.value
                if arg is None or value is None:
                    matched = False
                    break
                try:
                    self.infer_type(value, arg.type)
                except errors.AngelTypeError:
                    matched = False
                    break
            if not matched:
                matched = True
                expected_major.append([arg.type for arg in init_entry.args])
                continue
            self.env.inc_nesting()
            self.env.add_variable(
                0, nodes.Name(nodes.SpecialName.self.value), struct.name, value=None,
                estimated_value=enodes.Instance(struct.name)
            )
            for arg, value, estimated in zip_longest(init_entry.args, args, arguments):
                if value is None:
                    value = arg.value
                    estimated = self.estimate_expression(value)
                assert estimated is not None and value is not None
                self.env.add_constant(0, arg.name, arg.type, value, estimated)
            self.estimate_ast(init_entry.body)
            self_entry = self.env[nodes.SpecialName.self.value]
            assert isinstance(self_entry, entries.VariableEntry)
            self_value = self_entry.estimated_value
            assert isinstance(self_value, enodes.Instance)
            self.env.dec_nesting()
            return self_value
        expected = " or ".join(
            ("(" + ", ".join(type_.to_code() for type_ in type_list) + ")" for type_list in expected_major)
        )
        raise errors.AngelWrongArguments(expected, self.code, args)

    def match_function_body(
            self, function: enodes.Function, args: t.List[nodes.Expression],
            self_arg: t.Optional[nodes.Expression] = None,
            self_type: t.Optional[nodes.Type] = None,
    ) -> t.Optional[enodes.Expression]:
        arguments = [self.estimate_expression(argument) for argument in args]
        if isinstance(function.specification, list):
            self.env.inc_nesting()
            if self_arg and self_type:
                self.env.add_variable(
                    0, nodes.Name(nodes.SpecialName.self.value), self_type, value=self_arg,
                    estimated_value=self.estimate_expression(self_arg)
                )
            for arg, value, estimated in zip(function.args, args, arguments):
                self.env.add_constant(0, arg.name, arg.type, value, estimated)
            result = self.estimate_ast(function.specification)
            self.env.dec_nesting()
            return result
        if self_arg:
            return function.specification(self.estimate_expression(self_arg), *arguments)
        return function.specification(*arguments)

    def estimate_method_call(self, call: nodes.MethodCall) -> t.Optional[enodes.Expression]:
        method = self.estimate_expression(nodes.Field(call.line, call.instance_path, call.method))
        if isinstance(method, enodes.Function):
            return self.match_function_body(
                method, call.args, self_arg=call.instance_path, self_type=call.instance_type
            )
        elif isinstance(method, enodes.AlgebraicConstructor):
            algebraic_entry = self.env.get(method.name)
            assert isinstance(algebraic_entry, entries.AlgebraicEntry)
            constructor_entry = algebraic_entry.constructors[method.constructor.member]
            return self.match_algebraic_constructor_init(
                method, list(constructor_entry.init_declarations.values()), call.args
            )
        else:
            assert 0, f"Cannot estimate method call with estimated method {method}"

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
        result = self.type_checker.infer_type(expression, supertype)
        return result.type

    def update_context(self, env: environment.Environment, code: errors.Code = None):
        self.env = env
        self.code = code or self.code

    def entry(self, name: nodes.Name) -> entries.Entry:
        if name.module:
            assert 0, "Module system is not supported"
        entry = self.env[name.member]
        assert entry is not None
        return entry

    def test(self):
        self.assertEqual(NODES, set(subclass.__name__ for subclass in self.node_dispatcher.keys()))
        self.assertEqual(EXPRS, set(subclass.__name__ for subclass in self.expression_dispatcher.keys()))
        self.assertEqual(ASSIGNMENTS, set(subclass.__name__ for subclass in self.assignment_dispatcher.keys()))


Estimator = partial(
    Evaluator,
    EstimatedObjects(
        builtin_funcs=builtin_funcs, string_fields=string_fields, vector_fields=vector_fields, dict_fields=dict_fields
    )
)
