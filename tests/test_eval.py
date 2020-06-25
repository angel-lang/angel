import typing as t
import unittest

from compiler import parsers, analysis, environment, clarification, repl_evaluation
from compiler.context import Context


class TestEval(unittest.TestCase):
    def get_env(self, lines: t.List[str]) -> environment.Environment:
        context = Context(lines, main_hash='', mangle_names=False)
        parser = parsers.Parser()
        clarifier = clarification.Clarifier(context)
        analyzer = analysis.Analyzer(context)
        repl_evaluator = repl_evaluation.REPLEvaluator(context)
        clarified_ast = clarifier.clarify_ast(parser.parse('\n'.join(lines)))
        for module_name, module_content in context.imported_lines.items():
            module_hash = context.module_hashs[module_name]
            context.main_hash = module_hash
            clarified_ast = clarifier.clarify_ast(parser.parse(module_content)) + clarified_ast
        repl_evaluator.estimate_ast(analyzer.analyze_ast(clarified_ast))
        return repl_evaluator.env

    def eval(
        self, lines: t.List[str], inp: t.Optional[str] = None, env: t.Optional[environment.Environment] = None
    ) -> t.Tuple[t.Any, t.List[str]]:
        output = []

        def print_test(value, *arguments):
            output.append(value)
            output.extend(arguments)

        def input_test(_):
            return inp

        context = Context(lines, main_hash='', mangle_names=False)
        parser = parsers.Parser()
        clarifier = clarification.Clarifier(context)
        analyzer = analysis.Analyzer(context, env=env)
        repl_evaluator = repl_evaluation.REPLEvaluator(context, env=env)
        repl_evaluation.print = print_test
        repl_evaluation.input = input_test
        clarified_ast = clarifier.clarify_ast(parser.parse('\n'.join(lines)))
        for module_name, module_content in context.imported_lines.items():
            module_hash = context.module_hashs[module_name]
            context.main_hash = module_hash
            clarified_ast = clarifier.clarify_ast(parser.parse(module_content)) + clarified_ast
        result = repl_evaluator.estimate_ast(analyzer.analyze_ast(clarified_ast))
        return result, output

    def test_integer_literal(self):
        result, output = self.eval([
            "print(123)",
        ])
        self.assertEqual(output, ['123'])

    def test_string_literal(self):
        result, output = self.eval([
            'print("Hello, world!")',
        ])
        self.assertEqual(output, ["Hello, world!"])

    def test_string_add(self):
        result, output = self.eval([
            'let name = "John"',
            'print("Hello, " + name)'
        ])
        self.assertEqual(output, ["Hello, John"])

    def test_string_subscript(self):
        result, output = self.eval([
            'let name = "John"',
            'print(name[0])'
        ])
        self.assertEqual(output, ["J"])

    def test_false_literal(self):
        result, output = self.eval([
            'print(False)',
        ])
        self.assertEqual(output, ["False"])

    def test_true_literal(self):
        result, output = self.eval([
            'print(True)',
        ])
        self.assertEqual(output, ["True"])

    def test_bool_expression_literal(self):
        result, output = self.eval([
            'print(2 == 2 and I8 is Object)',
        ])
        self.assertEqual(output, ["True"])

    def test_name(self):
        env = self.get_env(['let a = "lol"'])
        result, output = self.eval([
            'print(a)',
        ], env=env)
        self.assertEqual(output, ["lol"])

    def test_while(self):
        result, output = self.eval([
            'while i < 10:',
            '    print(i)',
            '    i += 1'
        ], env=self.get_env(['var i: I8 = 0']))
        self.assertEqual(output, ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])

    def test_if(self):
        code = [
            'let name = read("Name: ")',
            'if name == "John":',
            '    print("J")',
            'elif name == "Mike":',
            '    print("M")',
            'else:',
            '    print("Some other")'
        ]
        result1, output1 = self.eval(code, inp='John')
        result2, output2 = self.eval(code, inp='Mike')
        result3, output3 = self.eval(code, inp='Kale')
        self.assertEqual(output1, ['J'])
        self.assertEqual(output2, ['M'])
        self.assertEqual(output3, ['Some other'])

    def test_func(self):
        code = [
            'fun printName(name: String):',
            '    print(name)',

            'printName(read(""))',
        ]
        result, output = self.eval(code, inp='John')
        self.assertEqual(output, ['John'])

    def test_char(self):
        code = ["print('a')"]
        result, output = self.eval(code)
        self.assertEqual(output, ['a'])

    def test_f32_and_f64(self):
        code = ["print(10.2)"]
        result, output = self.eval(code)
        self.assertEqual(output, ["10.2"])

    def test_vector(self):
        code = ["print([1, 2, 3])"]
        result, output = self.eval(code)
        self.assertEqual(output, ['[1, 2, 3]'])

    def test_vector_subscript(self):
        result, output = self.eval([
            'let names = ["John"]',
            'print(names[0])'
        ])
        self.assertEqual(output, ["John"])

    def test_dict_subscript(self):
        result, output = self.eval([
            'let names = ["John": 1, "Mike": 34]',
            'print(names["Mike"])'
        ])
        self.assertEqual(output, ["34"])

    def test_dict(self):
        code = ['print(["a": 1, "c": 0, "b": 3])']
        result, output = self.eval(code)
        self.assertEqual(output, ['["a": 1, "c": 0, "b": 3]'])

    def test_optional_eq(self):
        code = ['print(Optional.None == Optional.None)']
        result, output = self.eval(code)
        self.assertEqual(output, ['True'])

    def test_if_let_1(self):
        code = [
            'if let name = Optional.None:',
            '    print("No")',
            'else:',
            '    print("Yes")',
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ["Yes"])

    def test_if_let_2(self):
        code = [
            'if let name = Optional.Some("John"):',
            '    print(name)',
            'else:',
            '    print("NO")',
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ["John"])

    def test_while_let(self):
        code = [
            'fun getN(i: I8) -> I8?:',
            '    if i <= 3:',
            '        return Optional.Some(i)',
            '    return Optional.None',
            'var i: I8 = 0',
            'while let n = getN(i):',
            '    print(n)',
            '    i += 1'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['0', '1', '2', '3'])

    def test_for_element_in_vector(self):
        code = [
            'for element in [1, 2, 3]:',
            '    print(element)'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['1', '2', '3'])

    def test_for_element_in_string(self):
        code = [
            'for element in "123":',
            '    print(element)'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['1', '2', '3'])

    def test_string_split(self):
        code = [
            'let names = "John,Mike,Kale".split(\',\')',
            'print(names)'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['["John", "Mike", "Kale"]'])

    def test_string_length(self):
        code = [
            'let name = "John"',
            'print(name.length)'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['4'])

    def test_vector_length(self):
        code = [
            'let names = ["John"]',
            'print(names.length)'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['1'])

    def test_vector_add(self):
        code = [
            'let l = [1, 2, 3] + [4]',
            'print(l[3])',
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['4'])

    def test_dict_length(self):
        code = [
            'let letters = ["a": 1, "b": 2]',
            'print(letters.length)'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['2'])

    def test_email_struct(self):
        code = [
            'struct Email:',
            '    userName: String',
            '    domain: String',

            '    init(userName: String, domain: String):',
            '        self.userName = userName',
            '        self.domain = domain',

            '    init():',
            '        self.userName = "test"',
            '        self.domain = "mail.com"',

            '    fun changeDomain(domain: String):',
            '        self.domain = domain',

            'let basicEmail = Email()',
            'print(basicEmail.userName)',
            'print(basicEmail.domain)',

            'var advancedEmail = Email("john", "mail.com")',
            'print(advancedEmail.userName)',
            'print(advancedEmail.domain)',

            'advancedEmail.changeDomain("domain.org")',
            'print(advancedEmail.domain)',
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['test', 'mail.com', 'john', 'mail.com', 'domain.org'])

    def test_stack_struct(self):
        code = [
            'struct Stack<A>:',
            '    data: [A]',

            '    init(data: [A]):',
            '        self.data = data',

            '    fun push(element: A) -> A:',
            '        self.data.append(element)',
            '        return element',

            '    fun depth -> U64:',
            '        return self.data.length',

            'let stack = Stack([1, 2, 3])',
            'print(stack.data[1])',
            'let same = stack.push(4)',
            'print(same)',
            'print(stack.data.length)',
            'print(stack.depth())',
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ["2", "4", "4", "4"])

    def test_addable_impl(self):
        code = [
            'struct V is ArithmeticObject:',
            '    first: I8',
            '    second: I8',

            '    fun __add__(other: V) -> V:',
            '        return V(self.first + other.first, self.second + other.second)',

            '    fun __sub__(other: V) -> V:',
            '        return V(self.first - other.first, self.second - other.second)',

            '    fun __mul__(other: V) -> V:',
            '        return V(self.first * other.first, self.second * other.second)',

            '    fun __div__(other: V) -> V:',
            '        return V(self.first / other.first, self.second / other.second)',

            '    fun report():',
            '        print(self.first as String + " " + self.second as String)',

            'let v1 = V(1, 2)',
            'let v2 = V(2, 2)',
            'let v3 = v1 + v2',
            'let v4 = v1 - v2',
            'let v5 = v1 * v2',
            'let v6 = v1 / v2',
            'v3.report()',
            'v4.report()',
            'v5.report()',
            'v6.report()',
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ["3 4", "-1 0", "2 4", "0 1"])

    def test_convertible_to_string_impl(self):
        code = [
            'struct Vec is ConvertibleToString:',
            '    x: I8',
            '    y: I8',

            '    fun as -> String:',
            '        return "(" + self.x as String + ", " + self.y as String + ")"',

            'print(Vec(1, 2))',
            'print(Vec(1, 2) as String)',
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['(1, 2)', '(1, 2)'])

    def test_color_algebraic(self):
        code = [
            'algebraic Color:',
            '    struct Red:',
            '        data: I8',
            '        fun getEstimation() -> String:',
            '            if self.data < 10:',
            '                return "Small"',
            '            return "Big"',
            '    struct Blue:',
            '        data: I8',
            '    struct Green:',
            '        data: I8',
            '    fun word() -> String:',
            '        return "word"',
            'var color = Color.Red(12)',
            'print(color.data)',
            'print(color.getEstimation())',
            'color = Color.Blue(5)',
            'print(color.data)',
            'print(color.word())'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['12', 'Big', '5', 'word'])

    def test_ref(self):
        code = [
            'var p = ref 1',
            'var r = p',
            'print(p.value)',
            'print(r.value)',
            'p.value = 2',
            'print(p.value)',
            'print(r.value)',
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['1', '1', '2', '2'])


if __name__ == '__main__':
    unittest.main()
