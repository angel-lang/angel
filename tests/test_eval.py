import typing as t
import unittest

from compiler import parsers, analyzers, environment, nodes


class TestEval(unittest.TestCase):
    def get_env(self, lines: t.List[str]) -> environment.Environment:
        parser = parsers.Parser()
        analyzer = analyzers.Analyzer(lines)
        analyzer.analyze(parser.parse("\n".join(lines)))
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
        result = analyzer.eval(parser.parse("\n".join(lines)))
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
        env = environment.Environment()
        env.add_constant(0, nodes.Name('a'), nodes.BuiltinType.string, nodes.StringLiteral("lol"), computed_value="lol")
        result, output = self.eval([
            'print(a)',
        ], env=env)
        self.assertEqual(output, ["lol"])


if __name__ == '__main__':
    unittest.main()
