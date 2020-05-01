import unittest

from compiler import nodes
from compiler.parsers import build_binary_expression


class TestEval(unittest.TestCase):
    def setUp(self):
        super().setUp()

    def build(self, binary_expression: nodes.BinaryExpression) -> nodes.Expression:
        return build_binary_expression(binary_expression.left, binary_expression.operator, binary_expression.right)

    def test_build_binary_expression_simple(self):
        inp = nodes.BinaryExpression(nodes.Name('a'), nodes.Operator.add, nodes.Name('b'))
        self.assertEqual(self.build(inp), inp)

    def test_build_binary_expression_nested_same_op(self):
        inp_l = nodes.BinaryExpression(
            nodes.BinaryExpression(nodes.Name('a'), nodes.Operator.add, nodes.Name('b')),
            nodes.Operator.add, nodes.Name('c')
        )
        self.assertEqual(self.build(inp_l), inp_l)

        inp = nodes.BinaryExpression(
            nodes.Name('a'), nodes.Operator.add,
            nodes.BinaryExpression(nodes.Name('b'), nodes.Operator.add, nodes.Name('c'))
        )
        self.assertEqual(self.build(inp), inp_l)

        inp = nodes.BinaryExpression(
            nodes.BinaryExpression(nodes.Name('a'), nodes.Operator.add, nodes.Name('b')),
            nodes.Operator.add, nodes.BinaryExpression(nodes.Name('c'), nodes.Operator.add, nodes.Name('d'))
        )
        expected = nodes.BinaryExpression(
            nodes.BinaryExpression(
                nodes.BinaryExpression(
                    nodes.Name('a'), nodes.Operator.add, nodes.Name('b')
                ), nodes.Operator.add, nodes.Name('c')
            ), nodes.Operator.add, nodes.Name('d')
        )
        self.assertEqual(self.build(inp), expected)

    def test_build_binary_expression_nested_diff_op(self):
        inp_l = nodes.BinaryExpression(
            nodes.BinaryExpression(nodes.Name('a'), nodes.Operator.mul, nodes.Name('b')),
            nodes.Operator.add, nodes.Name('c')
        )
        self.assertEqual(self.build(inp_l), inp_l)

        inp = nodes.BinaryExpression(
            nodes.Name('a'), nodes.Operator.mul,
            nodes.BinaryExpression(nodes.Name('b'), nodes.Operator.add, nodes.Name('c'))
        )
        self.assertEqual(self.build(inp), inp_l)

        inp = nodes.BinaryExpression(
            nodes.BinaryExpression(nodes.Name('a'), nodes.Operator.mul, nodes.Name('b')),
            nodes.Operator.add, nodes.BinaryExpression(nodes.Name('c'), nodes.Operator.mul, nodes.Name('d'))
        )
        self.assertEqual(self.build(inp), inp)

        inp = nodes.BinaryExpression(
            nodes.BinaryExpression(nodes.Name('a'), nodes.Operator.add, nodes.Name('b')),
            nodes.Operator.add, nodes.BinaryExpression(nodes.Name('c'), nodes.Operator.mul, nodes.Name('d'))
        )
        self.assertEqual(self.build(inp), inp)

        inp = nodes.BinaryExpression(
            nodes.BinaryExpression(nodes.Name('a'), nodes.Operator.add, nodes.Name('b')),
            nodes.Operator.mul, nodes.BinaryExpression(nodes.Name('c'), nodes.Operator.mul, nodes.Name('d'))
        )
        expected = nodes.BinaryExpression(
            nodes.Name('a'), nodes.Operator.add, nodes.BinaryExpression(
                nodes.BinaryExpression(nodes.Name('b'), nodes.Operator.mul, nodes.Name('c')),
                nodes.Operator.mul, nodes.Name('d')
            )
        )
        self.assertEqual(self.build(inp), expected)


if __name__ == '__main__':
    unittest.main()
