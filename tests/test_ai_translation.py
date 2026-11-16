#!/usr/bin/env python3
"""
Unit tests for AI Translation Engine (gemini_translator.py)
Validates:
1. Placeholder token extraction and preservation
2. Offline fallback translation formatting
3. Translation bundle structure and metadata
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "ai"))

from gemini_translator import extract_placeholders, mock_translate, translate_locale_catalog

class TestAITranslation(unittest.TestCase):

    def test_01_placeholder_extraction(self):
        text1 = "{completed} of {total} activities completed"
        self.assertEqual(extract_placeholders(text1), {"completed", "total"})

        text2 = "Welcome to EthOS"
        self.assertEqual(extract_placeholders(text2), set())

        text3 = "User {name} completed task {id} on {date}"
        self.assertEqual(extract_placeholders(text3), {"name", "id", "date"})

    def test_02_mock_translation_preserves_brand_and_tokens(self):
        source = "{completed} of {total} activities completed"
        es_trans = mock_translate(source, "es")
        self.assertIn("{completed}", es_trans)
        self.assertIn("{total}", es_trans)

        th_trans = mock_translate(source, "th")
        self.assertIn("{completed}", th_trans)
        self.assertIn("{total}", th_trans)

        brand_text = "Welcome to EthOS Research Study"
        brand_es = mock_translate(brand_text, "es")
        self.assertIn("EthOS", brand_es)

    def test_03_translate_locale_generates_valid_bundle(self):
        bundle = translate_locale_catalog("fr", "French")
        self.assertEqual(bundle["locale"], "fr")
        self.assertEqual(bundle["name"], "French")
        self.assertIn("translations", bundle)
        self.assertGreaterEqual(len(bundle["translations"]), 15)

        for key, item in bundle["translations"].items():
            self.assertEqual(item["translation_status"], "AI_GENERATED")
            self.assertIn("translated_text", item)
            self.assertTrue(len(item["translated_text"]) > 0)

if __name__ == "__main__":
    unittest.main()
