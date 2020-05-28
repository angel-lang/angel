import unittest

from compiler import type_checking, estimation, repl_evaluation, analysis, translators, utils
from compiler.context import Context


class TestCompleteness(unittest.TestCase):
    def setUp(self) -> None:
        context = Context(lines=[], main_hash='', mangle_names=False)
        self.analyzer = analysis.Analyzer(context)
        self.type_checker = type_checking.TypeChecker(context)
        self.estimator: estimation.Evaluator = estimation.Estimator(context)
        self.repl_evaluator: estimation.Evaluator = repl_evaluation.REPLEvaluator(context)
        self.translator = translators.Translator(context)

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
