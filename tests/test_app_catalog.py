import unittest

from z3ro.app_catalog import (
    enabled_apps,
    find_app,
    load_catalog,
)


class AppCatalogTests(unittest.TestCase):

    def test_catalog_has_entries(self):
        self.assertGreater(len(load_catalog()), 0)
        self.assertGreater(len(enabled_apps()), 0)

    def test_common_aliases_resolve(self):
        self.assertEqual(find_app("chrome").name, "Google Chrome")
        self.assertEqual(find_app("vscode").name, "Visual Studio Code")
        self.assertEqual(find_app("calc").name, "Calculator")

    def test_sensitive_tools_are_enabled_with_full_permissions(self):
        self.assertEqual(find_app("terminal").status, "enabled")
        self.assertEqual(find_app("powershell").status, "enabled")


if __name__ == "__main__":
    unittest.main()
