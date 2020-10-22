from unittest import TestCase


class CompilerStageTestCase(TestCase):
    """Helper for compiler stage testing."""

    def check_completeness(self, expected_classes, dispatchers):
        """Check that each dispatcher can dispatch all expected classes."""
        if isinstance(dispatchers, dict):
            dispatchers = (dispatchers,)
        for dispatcher in dispatchers:
            self.assertEqual(expected_classes, set(subclass.__name__ for subclass in dispatcher.keys()))
