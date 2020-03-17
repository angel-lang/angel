import unittest

from compiler import type_checking, nodes, estimation, repl_evaluation, analysis


def get_all_subclasses(cls):
    result = set()
    for subclass in cls.__subclasses__():
        subclass_subclasses = get_all_subclasses(subclass)
        if subclass_subclasses:
            # Don't add subclass that has subclasses.
            result = result.union(subclass_subclasses)
        else:
            result.add(subclass.__name__)
    return result


class TestCompleteness(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = analysis.Analyzer([])
        self.type_checker = type_checking.TypeChecker()
        self.estimator = estimation.Estimator()
        self.repl_evaluator = repl_evaluation.REPLEvaluator()

    def test_type_inference(self):
        self.assertEqual(
            self.type_checker.supported_nodes_by_type_inference, get_all_subclasses(nodes.Expression) - set(
                subclass.__name__ for subclass in (nodes.ConstantDeclaration, nodes.Field)
            )
        )

    def test_type_unification(self):
        expected = set()
        not_supported = set(subclass.__name__ for subclass in (nodes.Name, nodes.FunctionType))
        type_subclasses = get_all_subclasses(nodes.Type) - not_supported
        for type1 in type_subclasses:
            for type2 in type_subclasses:
                expected.add((type1, type2))
        self.assertEqual(self.type_checker.supported_nodes_by_type_unification, expected)

    def test_expression_estimation(self):
        self.assertEqual(self.estimator.supported_expression_nodes, get_all_subclasses(nodes.Expression) - set(
            subclass.__name__ for subclass in (nodes.ConstantDeclaration, nodes.Field)
        ))

    def test_repl(self):
        self.assertEqual(self.repl_evaluator.supported_nodes, get_all_subclasses(nodes.Node))

    def test_analysis(self):
        self.assertEqual(self.analyzer.supported_nodes, get_all_subclasses(nodes.Node))


if __name__ == '__main__':
    unittest.main()
