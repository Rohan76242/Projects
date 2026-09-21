import unittest
from unittest.mock import patch

from z3ro.tools.system import open_app


class OpenAppTests(unittest.TestCase):

    def test_launches_catalogued_app_id(self):
        result = open_app("chrome")
        self.assertTrue(result.success)
        self.assertIn("Google Chrome", result.output)

    def test_does_not_launch_unknown_name(self):
        result = open_app("my made up app")
        self.assertFalse(result.success)
        self.assertIn("was not found in apps.txt", result.output)


if __name__ == "__main__":
    unittest.main()
