import unittest

from compiler import type_checking, nodes


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
        self.type_checker = type_checking.TypeChecker()

    def test_type_inference(self):
        self.assertEqual(
            self.type_checker.supported_nodes_by_type_inference, get_all_subclasses(nodes.Expression) - set(
                subclass.__name__ for subclass in (nodes.ConstantDeclaration, nodes.Field)
            )
        )


if __name__ == '__main__':
    unittest.main()
