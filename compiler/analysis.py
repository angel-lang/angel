import typing as t
from itertools import zip_longest

from . import (
    nodes, estimation, type_checking, environment, estimation_nodes as enodes, errors, environment_entries as entries
)
from .enums import DeclType
from .context import Context
from .constants import builtin_interfaces
from .utils import submangle, dispatch, NODES, ASSIGNMENTS
from .testutils import CompilerStageTestCase


class Analyzer(CompilerStageTestCase):

    def __init__(self, context: Context, env: t.Optional[environment.Environment] = None):
        super().__init__()
        self.env = env or environment.Environment()
        self.context = context

        self.line = 0
        self.function_return_types: t.List[nodes.Type] = []

        self.type_checker = type_checking.TypeChecker(context)
        self.estimator = estimation.Estimator(context)
        self.type_checker.estimator = self.estimator

        self.assignment_dispatcher = {
            nodes.Name: self.check_name_reassignment,
            nodes.Field: self.check_field_reassignment,
            nodes.Subscript: self.check_subscript_reassignment,
        }

        self.change_type_dispatcher = {
            nodes.Name: self.change_type_of_name,
            nodes.Field: self.change_type_of_field,
            nodes.Subscript: self.change_type_of_subscript,
        }

        self.node_dispatcher = {
            nodes.Decl: self.analyze_declaration,
            nodes.FunctionDeclaration: self.analyze_function_declaration,
            nodes.StructDeclaration: self.analyze_struct_declaration,
            nodes.ExtensionDeclaration: self.analyze_extension_declaration,
            nodes.AlgebraicDeclaration: self.analyze_algebraic_declaration,
            nodes.InterfaceDeclaration: self.analyze_interface_declaration,
            nodes.FieldDeclaration: self.analyze_field_declaration,
            nodes.MethodDeclaration: self.analyze_method_declaration,
            nodes.InitDeclaration: self.analyze_init_declaration,

            nodes.Assignment: self.analyze_assignment,
            nodes.If: self.analyze_if_statement,
            nodes.While: self.analyze_while_statement,
            nodes.For: self.analyze_for_statement,
            nodes.Return: self.analyze_return,
            nodes.Break: self.analyze_break,
            nodes.FunctionCall: self.analyze_function_call,
            nodes.InitCall: self.analyze_init_call,
            nodes.MethodCall: self.analyze_method_call,
        }

        self.check_interface_implementation_dispatcher = {
            entries.StructEntry: self.check_struct_interface_implementation
        }

        self.builtin_function_dispatcher = {
            nodes.BuiltinFunc.print.value: self.analyze_print_function_call,
        }

        self._apply_clause_to_env_dispatcher_binary_expression = {
            nodes.Operator.is_.value: self.apply_is_check_to_env,

            # TODO: apply to estimated_value
            nodes.Operator.lt.value: lambda _: None,
            nodes.Operator.gt.value: lambda _: None,
        }

    def analyze_ast(self, ast: nodes.AST) -> nodes.AST:
        return [self.analyze_node(node) for node in ast]

    def analyze_node(self, node: nodes.Node) -> nodes.Node:
        self.line = node.line
        return dispatch(self.node_dispatcher, type(node), node)

    def analyze_declaration(self, node: nodes.Decl) -> nodes.Decl:
        """
        1. Value (if presented) is checked in infer_type function
        2. Type is checked in infer_type function (if value presented) or in check_type function
        3. Value estimation is based on current environment, no need to create a new one
        """
        if node.value:
            type_ = self.infer_type(node.value, supertype=node.type)
            estimated = self.estimate_value(node.value)
        else:
            assert node.type
            type_ = self.check_type(node.type)
            estimated = enodes.DynamicValue(type_)
        self.env.add_declaration(node, estimated_value=estimated, type=type_)
        return nodes.Decl(node.line, node.decl_type, node.name, type_, node.value)

    def analyze_function_declaration(self, declaration: nodes.FunctionDeclaration) -> nodes.FunctionDeclaration:
        arguments = [nodes.Argument(arg.name, self.check_type(arg.type)) for arg in declaration.arguments]
        return_type = self.check_type(declaration.return_type)
        self.env.add_function(
            declaration.line, declaration.name, declaration.parameters, arguments, return_type, declaration.where_clause
        )
        # TODO: backup env, because apply_clause can modify variables
        self.env.inc_nesting()
        self.env.add_parameters(declaration.line, declaration.parameters)
        self.function_return_types.append(return_type)
        for arg in arguments:
            self.env.add_declaration(nodes.Decl(declaration.line, DeclType.constant, arg.name, arg.type))

        # The clause can use parameters and arguments.
        if declaration.where_clause:
            # Nothing except Bool is subtype of Bool.
            self.infer_type(declaration.where_clause, nodes.BuiltinType.bool)
            self.apply_clause_to_env(declaration.where_clause)

        body = self.analyze_ast(declaration.body)
        self.function_return_types.pop()
        self.env.dec_nesting()
        self.env.update_function_body(declaration.name, body)
        return nodes.FunctionDeclaration(
            declaration.line, declaration.name, declaration.parameters, arguments, return_type,
            declaration.where_clause, body
        )

    def _analyze_struct_methods(self, methods: nodes.DeclaredMethods) -> nodes.DeclaredMethods:
        return nodes.DeclaredMethods(
            private=t.cast(t.List[nodes.MethodDeclaration], self.analyze_ast(list(methods.private))),
            public=t.cast(t.List[nodes.MethodDeclaration], self.analyze_ast(list(methods.public))),
            special=t.cast(t.List[nodes.MethodDeclaration], self.analyze_ast(list(methods.special))),
        )

    def _analyze_struct_fields(self, fields: nodes.DeclaredFields) -> nodes.DeclaredFields:
        return nodes.DeclaredFields(
            private=t.cast(t.List[nodes.FieldDeclaration], self.analyze_ast(list(fields.private))),
            public=t.cast(t.List[nodes.FieldDeclaration], self.analyze_ast(list(fields.public))),
        )

    def analyze_struct_declaration(self, declaration: nodes.StructDeclaration) -> nodes.StructDeclaration:
        self.env.add_struct(declaration.line, declaration.name, declaration.parameters, declaration.interfaces)
        self.env.inc_nesting(declaration.name)
        self.env.add_parameters(declaration.line, declaration.parameters)
        fields = self._analyze_struct_fields(declaration.fields)
        init_declarations = self.generate_default_init(
            declaration.line, fields, list(declaration.init_declarations)
        )
        init_declarations = t.cast(t.List[nodes.InitDeclaration], self.analyze_ast(init_declarations))
        methods = self._analyze_struct_methods(declaration.methods)
        self.check_interface_implementations(declaration.interfaces, declaration.name)
        self.env.dec_nesting(declaration.name)
        return nodes.StructDeclaration(
            declaration.line, declaration.name, declaration.parameters, declaration.interfaces, fields,
            init_declarations, methods
        )

    def analyze_extension_declaration(self, declaration: nodes.ExtensionDeclaration) -> nodes.ExtensionDeclaration:
        entry = self.env.get(declaration.name)
        assert isinstance(entry, entries.StructEntry)
        entry.implemented_interfaces += declaration.interfaces
        self.env.inc_nesting(declaration.name)
        if declaration.where_clause:
            self.env.add_where_clause(declaration.where_clause)
        self.env.add_parameters(declaration.line, declaration.parameters)
        # list(...) for mypy
        methods = self._analyze_struct_methods(declaration.methods)
        self.check_interface_implementations(declaration.interfaces, declaration.name)
        if declaration.where_clause:
            self.env.remove_where_clause()
        self.env.dec_nesting(declaration.name)
        where_clause = declaration.where_clause
        return nodes.ExtensionDeclaration(
            declaration.line, declaration.name, declaration.parameters, declaration.interfaces, where_clause, methods
        )

    def analyze_algebraic_declaration(self, declaration: nodes.AlgebraicDeclaration) -> nodes.AlgebraicDeclaration:
        self.env.add_algebraic(declaration.line, declaration.name, declaration.parameters)
        self.env.inc_nesting(declaration.name)
        self.env.add_parameters(declaration.line, declaration.parameters)
        # list(...) for mypy
        constructors = t.cast(t.List[nodes.StructDeclaration], self.analyze_ast(list(declaration.constructors)))
        methods = self._analyze_struct_methods(declaration.methods)
        self.env.dec_nesting(declaration.name)
        return nodes.AlgebraicDeclaration(
            declaration.line, declaration.name, declaration.parameters, constructors, methods,
        )

    def analyze_interface_declaration(self, declaration: nodes.InterfaceDeclaration) -> nodes.InterfaceDeclaration:
        self.env.add_interface(
            declaration.line, declaration.name, declaration.parameters, declaration.implemented_interfaces
        )
        self.env.inc_nesting(declaration.name)
        self.env.add_parameters(declaration.line, declaration.parameters)
        # list(...) for mypy
        fields = t.cast(t.List[nodes.FieldDeclaration], self.analyze_ast(list(declaration.fields)))
        methods = t.cast(t.List[nodes.MethodDeclaration], self.analyze_ast(list(declaration.methods)))
        self.env.dec_nesting(declaration.name)
        return nodes.InterfaceDeclaration(
            declaration.line, declaration.name, declaration.parameters, declaration.implemented_interfaces, fields, methods
        )

    def generate_default_init(
        self, struct_declaration_line: int, fields: nodes.DeclaredFields, init_declarations: t.List[nodes.InitDeclaration]
    ):
        if not init_declarations:
            init_declaration_body: nodes.AST = []
            arguments = []
            for field in fields.public:
                arguments.append(nodes.Argument(field.name, field.type, field.value))
                init_declaration_body.append(
                    nodes.Assignment(
                        field.line, nodes.Field(field.line, nodes.SpecialName.self, field.name), nodes.Operator.eq, field.name
                    )
                )
            for field in fields.private:
                if field.value is None:
                    raise errors.AngelPrivateFieldsNotInitializedAndNoInit(field.name, self.get_code(field.line))
                init_declaration_body.append(
                    nodes.Assignment(
                        field.line, nodes.Field(field.line, nodes.SpecialName.self, field.name), nodes.Operator.eq, field.value
                    )
                )
            default_init_declaration = nodes.InitDeclaration(struct_declaration_line, arguments, init_declaration_body)
            return [default_init_declaration] + init_declarations
        return init_declarations

    def analyze_field_declaration(self, declaration: nodes.FieldDeclaration) -> nodes.FieldDeclaration:
        if declaration.value:
            field_type = self.infer_type(declaration.value, declaration.type)
        else:
            field_type = self.check_type(declaration.type)
        self.env.add_field(declaration.line, declaration.name, field_type)
        return nodes.FieldDeclaration(declaration.line, declaration.name, field_type, declaration.value)

    def _analyze_declared_arguments(self, arguments: nodes.Arguments) -> nodes.Arguments:
        result = []
        for arg in arguments:
            if arg.value is not None:
                argument = nodes.Argument(arg.name, self.infer_type(arg.value, arg.type), arg.value)
            else:
                argument = nodes.Argument(arg.name, self.check_type(arg.type), arg.value)
            result.append(argument)
        return result

    def analyze_method_declaration(self, declaration: nodes.MethodDeclaration) -> nodes.MethodDeclaration:
        arguments = self._analyze_declared_arguments(declaration.arguments)
        return_type = self.check_type(declaration.return_type)
        self.env.add_method(declaration.line, declaration.name, arguments, return_type)
        self.env.inc_nesting()
        self.env.add_parameters(declaration.line, declaration.parameters)
        self.function_return_types.append(return_type)
        self.env.add_self(declaration.line)
        for arg in arguments:
            self.env.add_declaration(nodes.Decl(declaration.line, DeclType.constant, arg.name, arg.type))
        body = self.analyze_ast(declaration.body)
        self.function_return_types.pop()
        self.env.dec_nesting()
        self.env.update_method_body(declaration.name, body)
        return nodes.MethodDeclaration(
            declaration.line, declaration.name, declaration.parameters, arguments, return_type, body
        )

    def analyze_init_declaration(self, declaration: nodes.InitDeclaration) -> nodes.InitDeclaration:
        arguments = self._analyze_declared_arguments(declaration.arguments)
        self.env.add_init_declaration(declaration.line, arguments)
        self.env.inc_nesting()
        self.env.add_self(declaration.line, is_variable=True)
        for arg in arguments:
            self.env.add_declaration(nodes.Decl(declaration.line, DeclType.constant, arg.name, arg.type))
        body = self.analyze_ast(declaration.body)
        self.env.dec_nesting()
        self.env.update_init_declaration_body(arguments, body)
        return nodes.InitDeclaration(declaration.line, arguments, body)

    def analyze_assignment(self, statement: nodes.Assignment) -> nodes.Assignment:
        if statement.operator.value != nodes.Operator.eq.value:
            right: nodes.Expression = nodes.BinaryExpression(
                statement.left, statement.operator.to_arithmetic_operator(), statement.right
            )
        else:
            right = statement.right
        self.change_type(statement.left, self.infer_type(right, supertype=self.infer_type(statement.left)))
        dispatch(self.assignment_dispatcher, type(statement.left), statement.left)
        return nodes.Assignment(statement.line, statement.left, nodes.Operator.eq, right)

    def _analyze_conditional(self, condition: nodes.Expression, body: nodes.AST) -> t.Tuple[nodes.Expression, nodes.AST]:
        if isinstance(condition, nodes.Decl) and condition.is_constant:
            result_condition: nodes.Expression = self.analyze_declaration(condition)
        else:
            result_condition = condition
            self.infer_type(condition, supertype=nodes.BuiltinType.bool)
        self.env.inc_nesting()
        result_body = self.analyze_ast(body)
        self.env.dec_nesting()
        return result_condition, result_body

    def analyze_if_statement(self, statement: nodes.If) -> nodes.If:
        condition, body = self._analyze_conditional(statement.condition, statement.body)
        elifs = [self._analyze_conditional(elif_condition, elif_body) for elif_condition, elif_body in statement.elifs]
        self.env.inc_nesting()
        else_ = self.analyze_ast(statement.else_)
        self.env.dec_nesting()
        return nodes.If(statement.line, condition, body, elifs, else_)

    def analyze_for_statement(self, statement: nodes.For) -> nodes.For:
        element_type = self.create_template_type()
        iterable_type = nodes.GenericType(nodes.BuiltinType.iterable, [element_type])
        container_type = self.infer_type(statement.container)
        self.unify_types(container_type, iterable_type)
        self.env.inc_nesting()
        self.env.add_declaration(
            nodes.Decl(statement.line, DeclType.variable, statement.element, self.resolve_template_type(element_type))
        )
        body = self.analyze_ast(statement.body)
        self.env.dec_nesting()
        statement.container_type = container_type
        statement.body = body
        return statement

    def analyze_while_statement(self, statement: nodes.While) -> nodes.While:
        condition, body = self._analyze_conditional(statement.condition, statement.body)
        return nodes.While(statement.line, condition, body)

    def analyze_return(self, statement: nodes.Return) -> nodes.Return:
        assert self.function_return_types
        self.infer_type(statement.value, supertype=self.function_return_types[-1])
        return statement

    def analyze_break(self, statement: nodes.Break) -> nodes.Break:
        return statement

    def analyze_builtin_function_call(self, function_call: nodes.FunctionCall) -> nodes.FunctionCall:
        assert isinstance(function_call.function_path, nodes.BuiltinFunc)
        return dispatch(self.builtin_function_dispatcher, function_call.function_path.value, function_call)

    def analyze_print_function_call(self, function_call: nodes.FunctionCall) -> nodes.FunctionCall:
        self.infer_type(function_call)
        value = function_call.arguments[0]
        value_type = self.infer_type(value)
        if value_type == nodes.BuiltinType.i8:
            value = nodes.Cast(value, nodes.BuiltinType.i16)
        elif isinstance(value_type, nodes.VectorType):
            element_type = value_type.subtype
            if element_type == nodes.BuiltinType.i8:
                element_type = nodes.BuiltinType.i16
            value = nodes.FunctionCall(0, nodes.PrivateBuiltinFunc.vector_to_string, [value], [element_type])
        return nodes.FunctionCall(function_call.line, function_call.function_path, [value])

    def analyze_function_call(self, function_call: nodes.FunctionCall) -> nodes.FunctionCall:
        if isinstance(function_call.function_path, nodes.BuiltinFunc):
            return self.analyze_builtin_function_call(function_call)
        self.infer_type(function_call)
        return function_call

    def analyze_init_call(self, init_call: nodes.InitCall) -> nodes.InitCall:
        # TODO: analyze init call
        return init_call

    def analyze_method_call(self, method_call: nodes.MethodCall) -> nodes.MethodCall:
        self.infer_type(method_call)
        return method_call

    def check_interface_implementations(self, interfaces: nodes.Interfaces, name: nodes.Name) -> None:
        if len(self.env.parents) > 1:
            entry: entries.Entry = self.env.get_algebraic(nodes.AlgebraicType(self.env.parents[-2], [], name))
        else:
            entry = self.env.get(name)
        for interface in interfaces:
            if isinstance(interface, nodes.GenericType):
                # TODO: support builtin interfaces
                assert isinstance(interface.name, nodes.Name)
                interface_entry = self.env.get(interface.name)
            elif isinstance(interface, nodes.BuiltinType):
                interface_entry = self.get_builtin_interface_entry(interface)
            else:
                interface_entry = self.env.get(interface)

            dispatch(self.check_interface_implementation_dispatcher, type(entry), entry, interface_entry)

    def check_struct_interface_implementation(
        self, struct_entry: entries.StructEntry, interface_entry: entries.InterfaceEntry
    ) -> None:
        for field_name, field_entry in interface_entry.fields.items():
            assert isinstance(field_entry, entries.DeclEntry)
            found = struct_entry.fields.get(
                field_name,
                struct_entry.fields.get(submangle(nodes.Name(field_name), self.context).member)
            )
            if not found:
                raise errors.AngelMissingInterfaceMember(
                    struct_entry.name, interface_entry.name, self.get_code(struct_entry.line), field_entry.name
                )
            assert isinstance(found, entries.DeclEntry)
            if found.type != field_entry.type:
                raise errors.AngelInterfaceFieldError(
                    struct_entry.name, interface_entry.name, self.get_code(found.line),
                    field_entry.name, found.type, field_entry.type
                )

        for field_name, (inherited_from, field_entry) in interface_entry.inherited_fields.items():
            assert isinstance(field_entry, entries.DeclEntry)
            found = struct_entry.fields.get(
                field_name,
                struct_entry.fields.get(
                    submangle(nodes.Name(field_name), self.context).member
                )
            )
            if not found:
                raise errors.AngelMissingInterfaceMember(
                    struct_entry.name, interface_entry.name, self.get_code(struct_entry.line), field_entry.name,
                    inherited_from=inherited_from
                )
            assert isinstance(found, entries.DeclEntry)
            if found.type != field_entry.type:
                raise errors.AngelInterfaceFieldError(
                    struct_entry.name, interface_entry.name, self.get_code(found.line),
                    field_entry.name, found.type, field_entry.type, inherited_from=inherited_from
                )

        for method_name, method_entry in interface_entry.methods.items():
            found_method: t.Optional[entries.FunctionEntry] = struct_entry.methods.get(
                method_name,
                struct_entry.methods.get(
                    submangle(nodes.Name(method_name), self.context).member
                )
            )
            if not found_method:
                raise errors.AngelMissingInterfaceMember(
                    struct_entry.name, interface_entry.name, self.get_code(struct_entry.line), method_entry.name
                )
            self.match_method_implementation(interface_entry.name, struct_entry.name, method_entry, found_method)

        for method_name, (inherited_from, method_entry) in interface_entry.inherited_methods.items():
            found_method = struct_entry.methods.get(
                method_name,
                struct_entry.methods.get(
                    submangle(nodes.Name(method_name), self.context).member
                )
            )
            if not found_method:
                raise errors.AngelMissingInterfaceMember(
                    struct_entry.name, interface_entry.name, self.get_code(struct_entry.line), method_entry.name,
                    inherited_from=inherited_from
                )
            self.match_method_implementation(
                interface_entry.name, struct_entry.name, method_entry, found_method, inherited_from
            )

    def match_method_implementation(
        self, interface: nodes.Name, subject: nodes.Name, interface_method: entries.FunctionEntry,
        subject_method: entries.FunctionEntry, inherited_from: t.Optional[nodes.Type] = None
    ) -> None:
        try:
            self.unify_types(subject_method.return_type, interface_method.return_type)
        except errors.AngelTypeError:
            raise errors.AngelInterfaceMethodError(
                subject, interface, self.get_code(subject_method.line), interface_method.name, subject_method.arguments,
                subject_method.return_type, interface_method.arguments, interface_method.return_type, inherited_from
            )
        for interface_arg, subject_arg in zip_longest(interface_method.arguments, subject_method.arguments):
            if interface_arg is None or subject_arg is None:
                raise errors.AngelInterfaceMethodError(
                    subject, interface, self.get_code(subject_method.line), interface_method.name, subject_method.arguments,
                    subject_method.return_type, interface_method.arguments, interface_method.return_type, inherited_from
                )
            try:
                self.unify_types(subject_arg.type, interface_arg.type)
            except errors.AngelTypeError:
                raise errors.AngelInterfaceMethodError(
                    subject, interface, self.get_code(subject_method.line), interface_method.name, subject_method.arguments,
                    subject_method.return_type, interface_method.arguments, interface_method.return_type, inherited_from
                )

    def check_name_reassignment(self, left: nodes.Name) -> None:
        if left.module:
            assert 0, "Module system is not supported"
        entry = self.env[left.member]
        # We assume that name checking was performed.
        assert entry is not None
        if isinstance(entry, entries.DeclEntry) and entry.is_constant:
            if entry.has_value:
                raise errors.AngelConstantReassignment(left, self.get_code(), self.get_code(entry.line))
            entry.has_value = True
        elif isinstance(entry, entries.DeclEntry) and entry.is_variable:
            pass
        else:
            raise errors.AngelConstantReassignment(left, self.get_code(), self.get_code(entry.line))

    def check_field_reassignment(self, left: nodes.Field) -> None:
        # TODO
        pass

    def check_subscript_reassignment(self, left: nodes.Subscript) -> None:
        # TODO
        pass

    def change_type_of_name(self, left: nodes.Name, typ: nodes.Type) -> None:
        entry = self.env.get(left)
        assert isinstance(entry, entries.DeclEntry)
        entry.type = typ

    def change_type_of_field(self, left: nodes.Field, typ: nodes.Type) -> None:
        # TODO
        pass

    def change_type_of_subscript(self, left: nodes.Subscript, typ: nodes.Type) -> None:
        # TODO
        pass

    def create_template_type(self) -> nodes.TemplateType:
        self.type_checker.update_context(self.env, self.get_code())
        return self.type_checker.create_template_type()

    def resolve_template_type(self, template_type: nodes.TemplateType) -> nodes.Type:
        self.type_checker.update_context(self.env, self.get_code())
        return self.type_checker.replace_template_types(template_type)

    def infer_type(self, value: nodes.Expression, supertype: t.Optional[nodes.Type] = None) -> nodes.Type:
        self.type_checker.update_context(self.env, self.get_code())
        result = self.type_checker.infer_type(value, supertype)
        return result.type

    def unify_types(self, subtype: nodes.Type, supertype: nodes.Type) -> nodes.Type:
        self.type_checker.update_context(self.env, self.get_code())
        result = self.type_checker.unify_types(subtype, supertype, mapping={})
        return result.type

    def check_type(self, type_: nodes.Type) -> nodes.Type:
        self.type_checker.update_context(self.env, self.get_code())
        result = self.type_checker.unify_types(type_, type_, mapping={})
        return result.type

    def change_type(self, left: nodes.AssignmentLeft, typ: nodes.Type):
        return dispatch(self.change_type_dispatcher, type(left), left, typ)

    def estimate_value(self, value: nodes.Expression) -> enodes.Expression:
        self.estimator.update_context(self.env, self.get_code())
        return self.estimator.estimate_expression(value)

    def get_code(self, line: int = 0):
        if not line:
            return errors.Code(self.context.lines[self.line - 1], self.line)
        return errors.Code(self.context.lines[line - 1], line)

    def get_builtin_interface_entry(self, interface: nodes.BuiltinType) -> entries.InterfaceEntry:
        entry = builtin_interfaces[interface.value]
        inherited_fields: t.Dict[str, t.Tuple[nodes.Interface, entries.Entry]] = {}
        inherited_methods: t.Dict[str, t.Tuple[nodes.Interface, entries.FunctionEntry]] = {}
        for parent_interface in entry.implemented_interfaces:
            assert isinstance(parent_interface, nodes.BuiltinType)
            parent_entry = self.get_builtin_interface_entry(parent_interface)
            inherited_fields.update({
                name: (parent_interface, field_entry) for name, field_entry in parent_entry.fields.items()
            })
            inherited_fields.update(parent_entry.inherited_fields)
            inherited_methods.update({
                name: (parent_interface, method_entry) for name, method_entry in parent_entry.methods.items()
            })
            inherited_methods.update(parent_entry.inherited_methods)
        entry.inherited_fields = inherited_fields
        entry.inherited_methods = inherited_methods
        return entry

    def apply_clause_to_env(self, clause: nodes.Expression):
        assert isinstance(clause, nodes.BinaryExpression)
        return dispatch(self._apply_clause_to_env_dispatcher_binary_expression, clause.operator.value, clause)

    def apply_is_check_to_env(self, clause: nodes.BinaryExpression):
        assert isinstance(clause.left, nodes.Name)
        assert isinstance(clause.right, (nodes.Name, nodes.BuiltinType, nodes.GenericType))
        entry = self.env.get(clause.left)
        assert isinstance(entry, entries.ParameterEntry)
        entry.implemented_interfaces.append(clause.right)

    def test(self):
        self.check_completeness(NODES, self.node_dispatcher)
        self.check_completeness(ASSIGNMENTS, (self.assignment_dispatcher, self.change_type_dispatcher))
