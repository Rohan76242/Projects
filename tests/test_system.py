import unittest
from unittest.mock import patch

from z3ro.tools.system import open_app


class OpenAppTests(unittest.TestCase):

    @patch("z3ro.tools.system.subprocess.Popen")
    def test_launches_catalogued_app_id(self, popen):
        result = open_app("chrome")

        self.assertTrue(result.success)
        self.assertEqual(result.output, "Opened Google Chrome.")
        popen.assert_called_once_with(
            ["explorer.exe", "shell:AppsFolder\\Chrome"],
            shell=False,
        )

    @patch("z3ro.tools.system.subprocess.Popen")
    def test_does_not_launch_blocked_app(self, popen):
        result = open_app("terminal")

        self.assertFalse(result.success)
        self.assertIn("blocked", result.output)
        popen.assert_not_called()

    @patch("z3ro.tools.system.subprocess.Popen")
    def test_does_not_launch_unknown_name(self, popen):
        result = open_app("my made up app")

        self.assertFalse(result.success)
        self.assertIn("not in Z3RO's app catalogue", result.output)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
