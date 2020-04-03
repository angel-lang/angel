import typing as t
import unittest

from compiler import parsers, analysis, environment, clarification, repl_evaluation


class TestEval(unittest.TestCase):
    def get_env(self, lines: t.List[str]) -> environment.Environment:
        parser = parsers.Parser()
        clarifier = clarification.Clarifier()
        analyzer = analysis.Analyzer(lines)
        repl_evaluator = repl_evaluation.REPLEvaluator()
        repl_evaluator.estimate_ast(analyzer.analyze_ast((clarifier.clarify_ast(parser.parse("\n".join(lines))))))
        return repl_evaluator.env

    def eval(
            self, lines: t.List[str], inp: t.Optional[str] = None, env: t.Optional[environment.Environment] = None
    ) -> t.Tuple[t.Any, t.List[str]]:
        output = []

        def print_test(value, *args):
            output.append(value)
            output.extend(args)

        def input_test(_):
            return inp

        env = env or environment.Environment()
        parser = parsers.Parser()
        clarifier = clarification.Clarifier()
        analyzer = analysis.Analyzer(lines, env)
        repl_evaluator = repl_evaluation.REPLEvaluator(env)
        repl_evaluation.print = print_test
        repl_evaluation.input = input_test
        result = repl_evaluator.estimate_ast(
            analyzer.analyze_ast(clarifier.clarify_ast(parser.parse("\n".join(lines))))
        )
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
            'print(2 == 2)',
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
        ], env=self.get_env(['var i = 0']))
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
            'var i = 0',
            'while let n = getN(i):',
            '    print(n)',
            '    i += 1'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, ['0', '1', '2', '3'])

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
            'struct Stack(A):',
            '    data: [A]',

            '    init(data: [A]):',
            '        self.data = data',

            '    fun push(element: A) -> A:',
            '        self.data.append(element)',
            '        return element',

            '    fun depth -> U64:',
            '        return self.data.length',

            'let stack = Stack([1, 2, 3])'
        ]
        result, output = self.eval(code)
        self.assertEqual(output, [])


if __name__ == '__main__':
    unittest.main()
