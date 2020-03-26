import unittest

from compiler import type_checking, estimation, repl_evaluation, analysis, translators, utils


class TestCompleteness(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = analysis.Analyzer([])
        self.type_checker = type_checking.TypeChecker()
        self.estimator: estimation.Evaluator = estimation.Estimator()
        self.repl_evaluator: estimation.Evaluator = repl_evaluation.REPLEvaluator()
        self.translator = translators.Translator()

    def test_all(self):
        self.analyzer.test()
        self.type_checker.test()
        self.estimator.test()
        self.repl_evaluator.test()
        self.translator.test()
        self.test_utils()

    def test_utils(self):
        self.assertEqual(utils.TYPES, set(subclass.__name__ for subclass in utils.apply_mapping_dispatcher.keys()))


if __name__ == '__main__':
    unittest.main()
