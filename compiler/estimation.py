import typing as t
import unittest
from copy import copy
from collections import namedtuple
from decimal import Decimal
from functools import partial
from itertools import zip_longest

from . import estimation_nodes as enodes, nodes, environment, errors, type_checking, environment_entries as entries
from .enums import DeclType
from .utils import submangle, dispatch, NODES, EXPRESSIONS, ASSIGNMENTS, apply_mapping
from .constants import (
    builtin_funcs, private_builtin_funcs, string_fields, vector_fields, dict_fields, SELF_NAME, SPEC_LINE
)
from .context import Context


EstimatedObjects = namedtuple(
    "EstimatedObjects", [
        'builtin_funcs', 'private_builtin_funcs', 'string_fields', 'vector_fields', 'dict_fields'
    ]
)
EstimatedFields = t.Dict[str, t.Union[t.Callable[..., enodes.Expression], enodes.Expression]]


class Evaluator(unittest.TestCase):
    def __init__(
        self, estimated_objs: EstimatedObjects, context: Context, env: t.Optional[environment.Environment] = None
    ) -> None:
        super().__init__()
        self.env = env or environment.Environment()
        self.code = errors.Code()
        self.repl_tmp_count = 0
        self.context = context
        self.type_checker = type_checking.TypeChecker(context)
        self.type_checker.estimator = self

        self.estimated_objs = estimated_objs

        self.expression_dispatcher = {
            nodes.Name: self.estimate_name,
            nodes.SpecialName: self.estimate_special_name,
            nodes.Field: self.estimate_field,
            nodes.Subscript: self.estimate_subscript,
            nodes.BinaryExpression: self.estimate_binary_expression,
            nodes.Cast: self.estimate_cast,
            nodes.Ref: self.estimate_ref,
            nodes.Parentheses: lambda expr: self.estimate_expression(expr.value),
            nodes.FunctionCall: self.estimate_function_call,
            nodes.MethodCall: self.estimate_method_call,
            nodes.BuiltinFunc: lambda func: self.estimated_objs.builtin_funcs[func.value],
            nodes.PrivateBuiltinFunc: lambda func: self.estimated_objs.private_builtin_funcs[func.value],
            nodes.Decl: self.estimate_decl,
            nodes.NamedArgument: lambda argument: self.estimate_expression(argument.value),

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
            (enodes.DynamicValue, enodes.DynamicValue): self.estimate_add_dyn_values,
            (enodes.Int, enodes.Int): self.estimate_add_ints,
            (enodes.String, enodes.String): self.estimate_add_strings,
            (enodes.Vector, enodes.Vector): self.estimate_add_vectors,
            (enodes.Instance, enodes.Instance): partial(
                self.estimate_arithmetic_operation_instances, nodes.SpecialMethods.add
            ),
            (enodes.DynamicValue, enodes.String): self.estimate_add_dyn_value_and_string,
        }

        sub_dispatcher = {
            (enodes.Int, enodes.Int): self.estimate_sub_ints,
            (enodes.Instance, enodes.Instance): partial(
                self.estimate_arithmetic_operation_instances, nodes.SpecialMethods.sub
            ),
        }

        mul_dispatcher = {
            (enodes.Int, enodes.Int): self.estimate_mul_ints,
            (enodes.Instance, enodes.Instance): partial(
                self.estimate_arithmetic_operation_instances, nodes.SpecialMethods.mul
            ),
        }

        div_dispatcher = {
            (enodes.Int, enodes.Int): self.estimate_div_ints,
            (enodes.Instance, enodes.Instance): partial(
                self.estimate_arithmetic_operation_instances, nodes.SpecialMethods.div
            ),
        }

        eq_dispatcher: t.Dict[t.Tuple[type, type], t.Callable] = {
            (enodes.Int, enodes.Int): lambda x, y, xe, ye: enodes.Bool(xe.value == ye.value),
            (enodes.String, enodes.String): lambda x, y, xe, ye: enodes.Bool(xe.value == ye.value),
            (enodes.Char, enodes.Char): lambda x, y, xe, ye: enodes.Bool(xe.value == ye.value),
            (enodes.Bool, enodes.Bool): lambda x, y, xe, ye: enodes.Bool(xe.value == ye.value),
            (enodes.OptionalConstructor, enodes.OptionalConstructor): lambda x, y, xe, ye: enodes.Bool(xe.value == ye.value),
            (enodes.Instance, enodes.Instance): self.estimate_eq_instances,

            (enodes.OptionalSomeCall, enodes.OptionalConstructor): lambda x, y, xe, ye: enodes.Bool(False),
        }

        lt_dispatcher = {
            (enodes.Int, enodes.Int): lambda x, y, xe, ye: enodes.Bool(xe.value < ye.value),
        }

        gt_dispatcher = {
            (enodes.Int, enodes.Int): lambda x, y, xe, ye: enodes.Bool(xe.value > ye.value),
        }

        self.binary_operator_dispatcher = {
            nodes.Operator.add.value: lambda x, y, xe, ye: dispatch(
                add_dispatcher, (type(xe), type(ye)), x, y, xe, ye
            ),
            nodes.Operator.sub.value: lambda x, y, xe, ye: dispatch(
                sub_dispatcher, (type(xe), type(ye)), x, y, xe, ye
            ),
            nodes.Operator.mul.value: lambda x, y, xe, ye: dispatch(
                mul_dispatcher, (type(xe), type(ye)), x, y, xe, ye
            ),
            nodes.Operator.div.value: lambda x, y, xe, ye: dispatch(
                div_dispatcher, (type(xe), type(ye)), x, y, xe, ye
            ),

            nodes.Operator.eq_eq.value: lambda x, y, xe, ye: dispatch(
                eq_dispatcher, (type(xe), type(ye)), x, y, xe, ye
            ),
            nodes.Operator.lt.value: lambda x, y, xe, ye: dispatch(
                lt_dispatcher, (type(xe), type(ye)), x, y, xe, ye
            ),
            nodes.Operator.gt.value: lambda x, y, xe, ye: dispatch(
                gt_dispatcher, (type(xe), type(ye)), x, y, xe, ye
            ),

            nodes.Operator.and_.value: self.estimate_binary_expression_and,
            nodes.Operator.or_.value: self.estimate_binary_expression_or,
        }

        self.estimate_field_dispatcher = {
            enodes.String: lambda base, f: self.estimate_builtin_field(self.estimated_objs.string_fields, base, f),
            enodes.Vector: lambda base, f: self.estimate_builtin_field(self.estimated_objs.vector_fields, base, f),
            enodes.Dict: lambda base, f: self.estimate_builtin_field(self.estimated_objs.dict_fields, base, f),
            enodes.Instance: self.estimate_instance_field,
            enodes.Algebraic: self.estimate_algebraic_field,
            enodes.AlgebraicConstructorInstance: self.estimate_algebraic_constructor_instance_field,
            enodes.Ref: self.estimate_ref_field,
            enodes.DynamicValue: self.estimate_dyn_field,
        }

        self.assignment_dispatcher = {
            nodes.Name: self.estimate_name_assignment,
            nodes.Field: self.estimate_field_assignment,
            nodes.Subscript: self.estimate_subscript_assignment,
        }

        self.node_dispatcher = {
            nodes.Decl: self.estimate_decl,
            nodes.FunctionDeclaration: self.estimate_function_declaration,
            nodes.FieldDeclaration: self.estimate_field_declaration,
            nodes.InitDeclaration: self.estimate_init_declaration,
            nodes.MethodDeclaration: self.estimate_method_declaration,
            nodes.StructDeclaration: self.estimate_struct_declaration,
            nodes.ExtensionDeclaration: self.estimate_extension_declaration,
            nodes.AlgebraicDeclaration: self.estimate_algebraic_declaration,
            nodes.InterfaceDeclaration: self.estimate_interface_declaration,
            nodes.FunctionCall: self.estimate_expression,
            nodes.InitCall: self.estimate_init_call,
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

    def estimate_decl(self, node: nodes.Decl) -> None:
        assert node.type is not None
        estimated = None
        if node.value is not None:
            estimated = self.estimate_expression(node.value)
        self.env.add_declaration(node, estimated_value=estimated)

    def estimate_function_declaration(self, declaration: nodes.FunctionDeclaration) -> None:
        self.env.add_function(
            declaration.line, declaration.name, declaration.parameters, declaration.arguments, declaration.return_type,
            declaration.where_clause
        )
        self.env.update_function_body(declaration.name, declaration.body)

    def estimate_method_declaration(self, declaration: nodes.MethodDeclaration) -> None:
        self.env.add_method(declaration.line, declaration.name, declaration.arguments, declaration.return_type)
        self.env.update_method_body(declaration.name, declaration.body)

    def estimate_init_declaration(self, declaration: nodes.InitDeclaration) -> None:
        self.env.add_init_declaration(declaration.line, declaration.arguments)
        self.env.update_init_declaration_body(declaration.arguments, declaration.body)

    def estimate_init_call(self, call: nodes.InitCall) -> None:
        pass

    def estimate_struct_declaration(self, declaration: nodes.StructDeclaration) -> None:
        # list(...) for mypy
        self.env.add_struct(declaration.line, declaration.name, declaration.parameters, declaration.interfaces)
        self.env.inc_nesting(declaration.name)
        self.estimate_ast(list(declaration.fields.all))
        self.estimate_ast(list(declaration.init_declarations))
        self.estimate_ast(list(declaration.methods.all))
        self.env.dec_nesting(declaration.name)

    def estimate_extension_declaration(self, declaration: nodes.ExtensionDeclaration) -> None:
        # list(...) for mypy
        self.env.inc_nesting(declaration.name)
        self.estimate_ast(list(declaration.methods.all))
        self.env.dec_nesting(declaration.name)

    def estimate_algebraic_declaration(self, declaration: nodes.AlgebraicDeclaration) -> None:
        self.env.add_algebraic(declaration.line, declaration.name, declaration.parameters)
        self.env.inc_nesting(declaration.name)
        self.estimate_ast(list(declaration.constructors))
        self.estimate_ast(list(declaration.methods.all))
        self.env.dec_nesting(declaration.name)

    def estimate_interface_declaration(self, declaration: nodes.InterfaceDeclaration) -> None:
        self.env.add_interface(
            declaration.line, declaration.name, declaration.parameters, declaration.implemented_interfaces
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
        if isinstance(entry, entries.DeclEntry) and entry.is_constant:
            assert not entry.has_value
            entry.estimated_value = right
            entry.has_value = True
        elif isinstance(entry, entries.DeclEntry) and entry.is_variable:
            entry.estimated_value = right
        else:
            assert 0, f"REPL cannot reassign {type(entry)}"

    def estimate_field_assignment(self, field: nodes.Field, value: nodes.Expression) -> None:
        estimated_value = self.estimate_expression(value)
        # @Cleanup: Move to dispatcher
        if isinstance(field.base, nodes.Name):
            assert not field.base.module
            base_entry = self.env[field.base.member]
            assert isinstance(base_entry, entries.DeclEntry) and base_entry.is_variable
            if isinstance(base_entry.estimated_value, enodes.Instance):
                base_entry.estimated_value.fields[field.field.member] = estimated_value
            elif isinstance(base_entry.estimated_value, enodes.Ref):
                base_entry.estimated_value.initial_expression = value
                base_entry.estimated_value.value = estimated_value
            else:
                assert 0, f"Cannot estimate field assignment {field.to_code()} = {value.to_code()}"
        elif isinstance(field.base, nodes.SpecialName):
            base_entry = self.env[field.base.value]
            assert isinstance(base_entry, entries.DeclEntry) and base_entry.is_variable
            assert isinstance(base_entry.estimated_value, enodes.Instance)
            base_entry.estimated_value.fields[field.field.member] = estimated_value
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
            assert isinstance(base_entry, entries.DeclEntry) and base_entry.is_variable
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
        if isinstance(container, enodes.Vector):
            elements: t.Iterable = container.elements
            element_type = container.element_type
        elif isinstance(container, enodes.String):
            elements = (enodes.Char(char) for char in container.value)
            element_type = nodes.BuiltinType.char
        else:
            raise NotImplementedError
        self.env.inc_nesting()
        for element in elements:
            self.env.add_declaration(
                nodes.Decl(statement.line, DeclType.constant, statement.element, element_type),
                estimated_value=element
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
        if isinstance(condition, nodes.Decl) and condition.is_constant:
            assert condition.value is not None
            tmp_right = self.create_repl_tmp(condition.value)
            to_prepend: t.List[nodes.Node] = [
                nodes.Decl(
                    condition.line, DeclType.variable, condition.name, condition.type,
                    nodes.OptionalSomeValue(tmp_right)
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
        self.env.add_declaration(
            nodes.Decl(SPEC_LINE, DeclType.variable, name, self.infer_type(value), value),
            estimated_value=self.estimate_expression(value)
        )
        return name

    def estimate_return(self, statement: nodes.Return) -> enodes.Expression:
        return self.estimate_expression(statement.value)

    def estimate_break(self, _: nodes.Break) -> enodes.Break:
        return enodes.Break()

    def estimate_eq_instances(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.Instance, ye: enodes.Instance
    ) -> enodes.Expression:
        result = self.estimate_method_call(
            nodes.MethodCall(
                SPEC_LINE, x, method=nodes.Name(nodes.SpecialMethods.eq.value), arguments=[y], instance_type=xe.type
            )
        )
        assert result
        return result

    def estimate_add_dyn_values(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.DynamicValue, ye: enodes.DynamicValue
    ) -> enodes.Expression:
        return xe

    def estimate_add_ints(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.Int, ye: enodes.Int
    ) -> enodes.Int:
        value = xe.value + ye.value
        new_type = self.infer_type(nodes.IntegerLiteral(str(value)))
        assert isinstance(new_type, nodes.BuiltinType)
        return enodes.Int(value, new_type)

    def estimate_add_strings(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.String, ye: enodes.String
    ) -> enodes.String:
        return enodes.String(xe.value + ye.value)

    def estimate_add_dyn_value_and_string(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.DynamicValue, ye: enodes.String
    ) -> enodes.Expression:
        assert isinstance(xe.type, nodes.BuiltinType) and xe.type == nodes.BuiltinType.string
        return enodes.DynamicValue(nodes.BuiltinType.string)

    def estimate_add_vectors(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.Vector, ye: enodes.Vector
    ) -> enodes.Vector:
        element_type = xe.element_type
        if not xe.elements:
            element_type = ye.element_type
        return enodes.Vector(xe.elements + ye.elements, element_type)

    def estimate_arithmetic_operation_instances(
        self, method_name: nodes.SpecialMethods, x: nodes.Expression, y: nodes.Expression,
        xe: enodes.Instance, ye: enodes.Instance
    ) -> enodes.Instance:
        assert xe.type == ye.type
        entry = self.env.get(xe.type)
        assert isinstance(entry, entries.StructEntry)
        method_entry = entry.methods[submangle(nodes.Name(method_name.value), self.context).member]
        result = self.perform_function_call(
            method_entry.to_estimated_function(), [y], nodes.Argument(SELF_NAME, xe.type, x)
        )
        assert isinstance(result, enodes.Instance)
        return result

    def estimate_sub_ints(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.Int, ye: enodes.Int
    ) -> enodes.Int:
        value = xe.value - ye.value
        new_type = self.infer_type(nodes.IntegerLiteral(str(value)))
        assert isinstance(new_type, nodes.BuiltinType)
        return enodes.Int(value, new_type)

    def estimate_mul_ints(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.Int, ye: enodes.Int
    ) -> enodes.Int:
        value = xe.value * ye.value
        new_type = self.infer_type(nodes.IntegerLiteral(str(value)))
        assert isinstance(new_type, nodes.BuiltinType)
        return enodes.Int(value, new_type)

    def estimate_div_ints(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.Int, ye: enodes.Int
    ) -> enodes.Int:
        if ye.value == 0:
            raise errors.AngelDivByZero
        value = int(Decimal(xe.value) / Decimal(ye.value))
        new_type = self.infer_type(nodes.IntegerLiteral(str(value)))
        assert isinstance(new_type, nodes.BuiltinType)
        # TODO: move to enodes.Float(value, new_type)
        return enodes.Int(int(value), new_type)

    def estimate_expression(self, expression: nodes.Expression) -> enodes.Expression:
        return dispatch(self.expression_dispatcher, type(expression), expression)

    def estimate_name(self, name: nodes.Name) -> enodes.Expression:
        if name.module:
            assert 0, "Module system is not supported"
        entry = self.env[name.member]
        # Estimation is performed after name checking.
        assert entry is not None, name.member
        if isinstance(entry, entries.DeclEntry):
            return entry.estimated_value
        elif isinstance(entry, entries.FunctionEntry):
            return entry.to_estimated_function()
        elif isinstance(entry, entries.StructEntry):
            return enodes.Struct(entry.name)
        elif isinstance(entry, entries.AlgebraicEntry):
            return enodes.Algebraic(entry.name, entry)
        else:
            # @Completeness: must have branches for all entry types
            assert 0, f"{self.estimate_name} cannot dispatch entry type {type(entry)}"

    def estimate_builtin_field(
        self, fields: EstimatedFields, base: enodes.Expression, field: nodes.Name
    ) -> enodes.Expression:
        estimated = fields[field.unmangled or field.member]
        if callable(estimated):
            return estimated(base)
        return estimated

    def estimate_algebraic_field(self, base: enodes.Algebraic, field: nodes.Name) -> enodes.Expression:
        return enodes.AlgebraicConstructor(base.name, field, entry=base.entry.constructors[field.member])

    def estimate_algebraic_constructor_instance_field(
        self, base: enodes.AlgebraicConstructorInstance, field: nodes.Name
    ) -> enodes.Expression:
        found = base.fields.get(field.member)
        if found is not None:
            return found
        constructor_entry = self.env.get_algebraic(
            nodes.AlgebraicType(base.type.name, parameters=[], constructor=base.type.constructor)
        )
        assert isinstance(constructor_entry, entries.StructEntry)
        method_entry = constructor_entry.methods.get(field.member)
        if method_entry is None:
            algebraic_entry = self.env.get(base.type.name)
            assert isinstance(algebraic_entry, entries.AlgebraicEntry)
            method_entry = algebraic_entry.methods[field.member]
        return method_entry.to_estimated_function()

    def estimate_instance_field(self, base: enodes.Instance, field: nodes.Name) -> enodes.Expression:
        found = base.fields.get(field.member)
        if found is not None:
            return found
        struct_entry = self.env[base.type.member]
        assert isinstance(struct_entry, entries.StructEntry)
        field_name = submangle(field, self.context).member
        method_entry = struct_entry.methods.get(field_name, struct_entry.methods.get(field.member))
        assert method_entry
        return method_entry.to_estimated_function()

    def estimate_ref_field(self, ref: enodes.Ref, field: nodes.Name) -> enodes.Expression:
        assert (field.unmangled or field.member) == 'value'
        return ref.value

    def estimate_dyn_field(self, dyn_value: enodes.DynamicValue, field: nodes.Name) -> enodes.Expression:
        assert isinstance(dyn_value.type, nodes.Name)
        entry = self.env.get(dyn_value.type)
        assert isinstance(entry, entries.StructEntry)
        field_entry = entry.fields[field.member]
        assert isinstance(field_entry, entries.DeclEntry)
        return enodes.DynamicValue(field_entry.type)

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
        """Estimate function or struct call.
        1. Get the function/struct estimated object
        2. Create an environment based on the environment that was available before function/struct declaration
        3. Override names with arguments
        4. Run the body
        5. Return the result if the function returns one
        """
        function = self.estimate_expression(call.function_path)
        if isinstance(function, enodes.Struct):
            if function.name.module:
                assert 0, "Module system is not supported"
            struct_entry = self.env[function.name.member]
            assert isinstance(struct_entry, entries.StructEntry)
            return self.match_init_declaration(function, list(struct_entry.init_declarations.values()), call.arguments)
        assert isinstance(function, enodes.Function)
        arguments = call.arguments
        if function.name == nodes.BuiltinFunc.print.value:
            arg_type = self.infer_type(arguments[0])
            arguments = [
                nodes.Cast(
                    call.arguments[0], nodes.BuiltinType.string, is_builtin=isinstance(arg_type, nodes.BuiltinType)
                )
            ]
        return self.perform_function_call(function, arguments)

    def match_algebraic_constructor_init(
        self, algebraic_constructor: enodes.AlgebraicConstructor, init_declarations: t.List[entries.InitEntry],
        arguments: t.List[nodes.Expression]
    ) -> enodes.AlgebraicConstructorInstance:
        result = self.match_init_declaration(enodes.Struct(algebraic_constructor.constructor), init_declarations, arguments, algebraic=algebraic_constructor.name)
        return enodes.AlgebraicConstructorInstance(algebraic_constructor, result.fields)

    def match_init_declaration(
        self, struct: enodes.Struct, init_declarations: t.List[entries.InitEntry], arguments: t.List[nodes.Expression],
        algebraic: t.Optional[nodes.Name] = None
    ) -> enodes.Instance:
        estimated_arguments = [self.estimate_expression(argument) for argument in arguments]
        matched = True
        expected_major = []
        if algebraic:
            struct_entry: entries.Entry = self.env.get_algebraic(
                nodes.AlgebraicType(algebraic, [], constructor=struct.name)
            )
        else:
            struct_entry = self.env.get(struct.name)
        assert isinstance(struct_entry, entries.StructEntry)

        for init_entry in init_declarations:
            struct_mapping: t.Dict[str, nodes.Type] = {}
            for param in struct_entry.parameters:
                struct_mapping[param.member] = self.type_checker.create_template_type()

            for arg, value in zip_longest(init_entry.arguments, arguments):
                if value is None:
                    value = arg.value
                if arg is None or value is None:
                    matched = False
                    break
                arg_type = apply_mapping(arg.type, struct_mapping)
                try:
                    self.infer_type(value, arg_type)
                except errors.AngelTypeError:
                    matched = False
                    break
                else:
                    arg_type = self.type_checker.replace_template_types(arg_type)
            if not matched:
                matched = True
                expected_major.append([arg.type for arg in init_entry.arguments])
                continue
            self.env.inc_nesting()
            self.env.add_declaration(
                nodes.Decl(0, DeclType.variable, SELF_NAME, struct.name),
                estimated_value=enodes.Instance(struct.name)
            )
            for arg, value, estimated in zip_longest(init_entry.arguments, arguments, estimated_arguments):
                if value is None:
                    value = arg.value
                    estimated = self.estimate_expression(value)
                assert estimated is not None and value is not None
                self.env.add_declaration(
                    nodes.Decl(0, DeclType.constant, arg.name, arg_type, value), estimated_value=estimated
                )
            if len(init_entry.body) == 1 and isinstance(init_entry.body[0], nodes.InitCall):
                return self.match_init_declaration(
                    struct, init_declarations, init_entry.body[0].arguments, algebraic
                )
            self.estimate_ast(init_entry.body)
            self_entry = self.env[nodes.SpecialName.self.value]
            assert isinstance(self_entry, entries.DeclEntry) and self_entry.is_variable
            self_value = self_entry.estimated_value
            assert isinstance(self_value, enodes.Instance)
            self.env.dec_nesting()
            return self_value
        expected = " or ".join(
            ("(" + ", ".join(type_.to_code() for type_ in type_list) + ")" for type_list in expected_major)
        )
        raise errors.AngelWrongArguments(expected, self.code, arguments)

    def perform_function_call(
        self, function: enodes.Function, arguments: t.List[nodes.Expression],
        self_argument: t.Optional[nodes.Argument] = None
    ) -> t.Optional[enodes.Expression]:
        """
        1. Estimate the arguments and the self_argument
        2. Create an environment based on function.saved_environment
        3. Populate that environment with the arguments and the self argument
        4. Call function's body
        """
        estimated_arguments = [self.estimate_expression(argument) for argument in arguments]
        if not isinstance(function.specification, list):
            if self_argument:
                assert self_argument.value
                estimated_arguments = [self.estimate_expression(self_argument.value)] + estimated_arguments
            return function.specification(*estimated_arguments)

        if self_argument:
            assert self_argument.value
            estimated_self: t.Optional[enodes.Expression] = self.estimate_expression(self_argument.value)
        else:
            estimated_self = None

        environment_backup = copy(self.env)
        self.env = environment.Environment(function.saved_environment)
        if self_argument:
            self.env.add_declaration(
                nodes.Decl(SPEC_LINE, DeclType.variable, SELF_NAME, self_argument.type, self_argument.value),
                estimated_value=estimated_self
            )

        for argument, expression, estimated in zip_longest(function.arguments, arguments, estimated_arguments):
            self.env.add_declaration(
                nodes.Decl(SPEC_LINE, DeclType.constant, argument.name, argument.type, expression),
                estimated_value=estimated
            )

        result = self.estimate_ast(function.specification)
        self.env = environment_backup
        return result

    def estimate_method_call(self, call: nodes.MethodCall) -> t.Optional[enodes.Expression]:
        method = self.estimate_expression(nodes.Field(call.line, call.instance_path, call.method))
        if isinstance(method, enodes.Function):
            assert call.instance_type
            return self.perform_function_call(
                method, call.arguments, nodes.Argument(SELF_NAME, call.instance_type, call.instance_path)
            )
        elif isinstance(method, enodes.AlgebraicConstructor):
            algebraic_entry = self.env.get(method.name)
            assert isinstance(algebraic_entry, entries.AlgebraicEntry)
            constructor_entry = algebraic_entry.constructors[method.constructor.member]
            return self.match_algebraic_constructor_init(
                method, list(constructor_entry.init_declarations.values()), call.arguments
            )
        else:
            assert 0, f"Cannot estimate method call with estimated method {method}"

    def estimate_binary_expression_and(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.Expression, ye: enodes.Expression
    ) -> enodes.Bool:
        assert isinstance(xe, enodes.Bool) and isinstance(ye, enodes.Bool)
        return enodes.Bool(xe.value and ye.value)

    def estimate_binary_expression_or(
        self, x: nodes.Expression, y: nodes.Expression, xe: enodes.Expression, ye: enodes.Expression
    ) -> enodes.Bool:
        assert isinstance(xe, enodes.Bool) and isinstance(ye, enodes.Bool)
        return enodes.Bool(xe.value or ye.value)

    def estimate_binary_expression(self, expression: nodes.BinaryExpression) -> enodes.Expression:
        if expression.operator.value == nodes.Operator.is_.value:
            if isinstance(expression.left, nodes.BuiltinType):
                if not isinstance(expression.right, nodes.BuiltinType):
                    return enodes.Bool(False)
                if expression.right.value in expression.left.get_builtin_supertypes():
                    return enodes.Bool(True)
                return enodes.Bool(False)
            if expression.right == nodes.BuiltinType.object_:
                return enodes.Bool(True)
            assert isinstance(expression.left, nodes.Name)
            assert isinstance(expression.right, (nodes.Name, nodes.BuiltinType, nodes.GenericType))
            entry = self.env.get(expression.left)
            assert isinstance(entry, (entries.StructEntry, entries.ParameterEntry))
            if entry.implements_interface(expression.right):
                return enodes.Bool(True)
            return enodes.Bool(False)
        left = self.estimate_expression(expression.left)
        right = self.estimate_expression(expression.right)
        if expression.operator.value == nodes.Operator.neq.value:
            result = dispatch(
                self.binary_operator_dispatcher, nodes.Operator.eq_eq.value, expression.left,
                expression.right, left, right
            )
            assert isinstance(result, enodes.Bool)
            return enodes.Bool(not result.value)
        elif expression.operator.value == nodes.Operator.lt_eq.value:
            result = dispatch(
                self.binary_operator_dispatcher, nodes.Operator.gt.value, expression.left, expression.right,
                left, right
            )
            assert isinstance(result, enodes.Bool)
            return enodes.Bool(not result.value)
        elif expression.operator.value == nodes.Operator.gt_eq.value:
            result = dispatch(
                self.binary_operator_dispatcher, nodes.Operator.lt.value, expression.left, expression.right,
                left, right
            )
            assert isinstance(result, enodes.Bool)
            return enodes.Bool(not result.value)
        return dispatch(
            self.binary_operator_dispatcher, expression.operator.value, expression.left, expression.right, left, right
        )

    def estimate_ref(self, ref: nodes.Ref) -> enodes.Expression:
        current_value = self.estimate_expression(ref.value)
        return enodes.Ref(current_value, initial_expression=ref.value)

    def estimate_cast(self, cast: nodes.Cast) -> enodes.Expression:
        value = self.estimate_expression(cast.value)
        if isinstance(cast.to_type, nodes.Name) and isinstance(value, enodes.Instance):
            assert isinstance(value.type, nodes.Name) and cast.to_type == value.type
            return value
        assert isinstance(cast.to_type, nodes.BuiltinType)
        if cast.to_type.value == nodes.BuiltinType.string.value:
            if isinstance(value, enodes.Instance):
                entry = self.env.get(value.type)
                assert isinstance(entry, entries.StructEntry)
                method_entry = entry.methods[
                    submangle(nodes.Name(nodes.SpecialMethods.as_.value), self.context).member
                ]
                result = self.perform_function_call(
                    method_entry.to_estimated_function(), arguments=[],
                    self_argument=nodes.Argument(SELF_NAME, value.type, cast.value)
                )
                assert result
                return result
            elif isinstance(value, enodes.String):
                return value
            elif isinstance(value, enodes.Char):
                return enodes.String(value.value)
            elif isinstance(value, (enodes.Bool, enodes.Dict, enodes.Vector)):
                return enodes.String(value.to_code())
            elif isinstance(value, enodes.DynamicValue):
                assert isinstance(value.type, nodes.BuiltinType) and value.type.is_finite_int_type
                return enodes.DynamicValue(nodes.BuiltinType.string)
            assert isinstance(value, (enodes.Int, enodes.Float)), type(value)
            return enodes.String(str(value.value))
        assert isinstance(value, (enodes.Int, enodes.Float)), type(value)
        return enodes.Int(int(value.value), cast.to_type)

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
        self.assertEqual(EXPRESSIONS, set(subclass.__name__ for subclass in self.expression_dispatcher.keys()))
        self.assertEqual(ASSIGNMENTS, set(subclass.__name__ for subclass in self.assignment_dispatcher.keys()))


Estimator = partial(
    Evaluator,
    EstimatedObjects(
        builtin_funcs=builtin_funcs, private_builtin_funcs=private_builtin_funcs, string_fields=string_fields, vector_fields=vector_fields, dict_fields=dict_fields
    )
)
