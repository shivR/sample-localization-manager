#!/usr/bin/env python3
"""
Unit tests for Key Drift Sentinel (check_key_drift.py)
Validates:
1. Loading catalog keys
2. Matching valid keys
3. Catching unregistered keys and finding fuzzy matches
4. Override detection (label or description flag)
"""

import os
import sys
import unittest

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "linter"))

from check_key_drift import (
    load_catalog_keys,
    find_closest_matches,
    check_override_present,
    extract_added_keys_ios,
    extract_added_keys_android,
    CATALOG_PATH
)

class TestKeyDriftLinter(unittest.TestCase):

    def test_01_load_catalog(self):
        keys = load_catalog_keys(CATALOG_PATH)
        self.assertGreaterEqual(len(keys), 15)
        self.assertIn("ethos.sample.title", keys)
        self.assertIn("ethos.sample.counter.completed_tasks", keys)

    def test_02_fuzzy_matcher(self):
        keys = load_catalog_keys(CATALOG_PATH)
        matches = find_closest_matches("ethos.sample.btn.sub", keys)
        self.assertIn("ethos.sample.btn.submit", matches)

    def test_03_ios_diff_parser(self):
        diff = [
            '--- a/Localizable.strings',
            '+++ b/Localizable.strings',
            '+ "auth.login.title" = "Sign In";',
            '+ "unregistered.key" = "Hello";',
            '- "deleted.key" = "Bye";'
        ]
        extracted = extract_added_keys_ios(diff)
        self.assertEqual(extracted, {"auth.login.title", "unregistered.key"})

    def test_04_android_diff_parser(self):
        diff = [
            '--- a/res/values/strings.xml',
            '+++ b/res/values/strings.xml',
            '+    <string name="auth_login_title">Sign In</string>',
            '+    <string name="unregistered_key">Hello</string>',
            '-    <string name="old_key">Old</string>'
        ]
        extracted = extract_added_keys_android(diff)
        self.assertEqual(extracted, {"auth_login_title", "unregistered_key"})

    def test_05_override_detection(self):
        self.assertTrue(check_override_present(["localization-override"], ""))
        self.assertTrue(check_override_present([], "Fixes bug [override-localization] urgent"))
        self.assertFalse(check_override_present(["bug", "ios"], "Regular pull request"))

if __name__ == "__main__":
    unittest.main()
