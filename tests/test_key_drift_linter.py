#!/usr/bin/env python3
"""
Unit tests for Key Drift Sentinel (check_key_drift.py)
Validates:
1. Loading catalog keys and metadata
2. Matching valid keys
3. Catching keys with spaces, hardcoded UI literals like Text("hi"), and finding fuzzy matches
4. Override detection (label or description flag)
"""

import os
import sys
import unittest

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "linter"))

from check_key_drift import (
    load_catalog,
    load_catalog_keys,
    find_closest_matches,
    check_override_present,
    extract_added_keys_ios,
    extract_added_keys_android,
    CATALOG_PATH
)

class TestKeyDriftLinter(unittest.TestCase):

    def test_01_load_catalog(self):
        catalog = load_catalog(CATALOG_PATH)
        keys = load_catalog_keys(CATALOG_PATH)
        self.assertGreaterEqual(len(keys), 15)
        self.assertIn("ethos.sample.title", keys)
        self.assertIn("ethos.sample.counter.completed_tasks", keys)
        self.assertIn("ethos.sample.welcome", catalog)

    def test_02_fuzzy_matcher_key_and_source(self):
        catalog = load_catalog(CATALOG_PATH)
        # Fuzzy match on key name
        matches_key = find_closest_matches("ethos.sample.btn.sub", catalog)
        self.assertTrue(any("ethos.sample.btn.submit" in m for m in matches_key))

        # Fuzzy match on source English text
        matches_source = find_closest_matches("Welcome to our app", catalog)
        self.assertTrue(any("ethos.sample.welcome" in m for m in matches_source))

    def test_03_ios_diff_parser_keys_and_hardcoded_text(self):
        diff = [
            '--- a/ContentView.swift',
            '+++ b/ContentView.swift',
            '+ "auth.login.title" = "Sign In";',
            '+ Text("hi")',
            '+ Text(manager.string(for: "Welcome to our app", default: "Welcome to our app"))',
            '+ Button("Click Me")',
            '+ // Text("commented out")',
            '- "deleted.key" = "Bye";'
        ]
        extracted = extract_added_keys_ios(diff)
        self.assertIn("auth.login.title", extracted)
        self.assertIn("hi", extracted)
        self.assertIn("Welcome to our app", extracted)
        self.assertIn("Click Me", extracted)
        self.assertNotIn("commented out", extracted)

    def test_04_android_diff_parser_keys_and_hardcoded_text(self):
        diff = [
            '--- a/res/values/strings.xml',
            '+++ b/res/values/strings.xml',
            '+    <string name="auth_login_title">Sign In</string>',
            '+    Text("hi")',
            '+    Text(text = "Hardcoded text")',
            '+    Text(EthOSLocalizationManager.string("Welcome to our app"))',
            '+    // Text("commented out")',
            '-    <string name="old_key">Old</string>'
        ]
        extracted = extract_added_keys_android(diff)
        self.assertIn("auth_login_title", extracted)
        self.assertIn("hi", extracted)
        self.assertIn("Hardcoded text", extracted)
        self.assertIn("Welcome to our app", extracted)
        self.assertNotIn("commented out", extracted)

    def test_05_override_detection(self):
        self.assertTrue(check_override_present(["localization-override"], ""))
        self.assertTrue(check_override_present([], "Fixes bug [override-localization] urgent"))
        self.assertFalse(check_override_present(["bug", "ios"], "Regular pull request"))

if __name__ == "__main__":
    unittest.main()
