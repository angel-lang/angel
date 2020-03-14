import typing as t
import unittest

from compiler import parsers, analyzers, environment


class TestEval(unittest.TestCase):
    def get_env(self, lines: t.List[str]) -> environment.Environment:
        parser = parsers.Parser()
        analyzer = analyzers.Analyzer(lines)
        analyzer.repl_eval_ast(parser.parse("\n".join(lines)))
        return analyzer.env

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
        analyzer = analyzers.Analyzer(lines, env)
        analyzer.repl = True
        analyzers.print = print_test
        analyzers.input = input_test
        result = analyzer.repl_eval_ast(parser.parse("\n".join(lines)))
        return result, output

    def test_integer_literal(self):
        result, output = self.eval([
            "print(123)",
        ])
        self.assertEqual(output, [123])

    def test_string_literal(self):
        result, output = self.eval([
            'print("Hello, world!")',
        ])
        self.assertEqual(output, ["Hello, world!"])

    def test_false_literal(self):
        result, output = self.eval([
            'print(false)',
        ])
        self.assertEqual(output, ["false"])

    def test_true_literal(self):
        result, output = self.eval([
            'print(true)',
        ])
        self.assertEqual(output, ["true"])

    def test_bool_expression_literal(self):
        result, output = self.eval([
            'print(2 == 2)',
        ])
        self.assertEqual(output, ["true"])

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
        self.assertEqual(output, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

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


if __name__ == '__main__':
    unittest.main()
