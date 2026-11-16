#!/usr/bin/env python3
"""
Unit tests for EthOS Post-Merge Key Ingestion Pipeline (dispatch_merged_keys.py & ingest_keys.py)
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts", "linter")
sys.path.insert(0, SCRIPTS_DIR)

from dispatch_merged_keys import extract_merged_keys_ios, extract_merged_keys_android
import ingest_keys as ingest_module

class TestPostMergePipeline(unittest.TestCase):

    def test_01_extract_merged_keys_ios(self):
        diff = [
            '--- a/ContentView.swift',
            '+++ b/ContentView.swift',
            '+ Text(manager.string(for: "ethos.welcome.new", default: "Welcome to our upgraded app!"))',
            '+ Text("Hardcoded string without manager")',
            '+ Button(manager.string(for: "ethos.btn.start"))',
            '+ "legacy.key.name" = "Legacy Value";',
            '+ // Text("commented out")'
        ]
        extracted = extract_merged_keys_ios(diff)
        self.assertEqual(extracted.get("ethos.welcome.new"), "Welcome to our upgraded app!")
        self.assertEqual(extracted.get("Hardcoded string without manager"), "Hardcoded string without manager")
        self.assertEqual(extracted.get("ethos.btn.start"), "ethos.btn.start")
        self.assertEqual(extracted.get("legacy.key.name"), "Legacy Value")
        self.assertNotIn("commented out", extracted)

    def test_02_extract_merged_keys_android(self):
        diff = [
            '--- a/strings.xml',
            '+++ b/strings.xml',
            '+    <string name="ethos_welcome_new">Welcome to our upgraded app!</string>',
            '+    Text("Hardcoded compose string")',
            '+    Text(EthOSLocalizationManager.string("ethos_btn_start", "Start Experience"))',
            '+    // Text("commented out")'
        ]
        extracted = extract_merged_keys_android(diff)
        self.assertEqual(extracted.get("ethos_welcome_new"), "Welcome to our upgraded app!")
        self.assertEqual(extracted.get("Hardcoded compose string"), "Hardcoded compose string")
        self.assertEqual(extracted.get("ethos_btn_start"), "Start Experience")
        self.assertNotIn("commented out", extracted)

    def test_03_ingest_keys(self):
        temp_dir = tempfile.mkdtemp()
        try:
            temp_catalog = os.path.join(temp_dir, "master-catalog.json")
            with open(temp_catalog, "w", encoding="utf-8") as f:
                json.dump({"catalog_version": "1.0.0", "keys": {}}, f)

            temp_locales = os.path.join(temp_dir, "locales")
            os.makedirs(os.path.join(temp_locales, "en"), exist_ok=True)
            with open(os.path.join(temp_locales, "en", "bundle.json"), "w", encoding="utf-8") as f:
                json.dump({"locale": "en", "translations": {}}, f)

            # Override module paths
            orig_catalog = ingest_module.CATALOG_PATH
            orig_locales = ingest_module.LOCALES_DIR
            ingest_module.CATALOG_PATH = temp_catalog
            ingest_module.LOCALES_DIR = temp_locales

            payload = {
                "source_repo": "sample-localization-ios",
                "commit_sha": "a1b2c3d4e5",
                "keys": [
                    {"key": "test.new.key", "default_text": "Hello World"}
                ]
            }

            added = ingest_module.ingest_keys(payload, auto_translate=False)
            self.assertEqual(len(added), 1)
            self.assertEqual(added[0], ("test.new.key", "Hello World"))

            with open(temp_catalog, "r", encoding="utf-8") as f:
                cat = json.load(f)
            self.assertIn("test.new.key", cat["keys"])
            self.assertEqual(cat["keys"]["test.new.key"]["source_text"], "Hello World")
            self.assertIn("a1b2c3d", cat["keys"]["test.new.key"]["description"])

            with open(os.path.join(temp_locales, "en", "bundle.json"), "r", encoding="utf-8") as f:
                en_b = json.load(f)
            self.assertIn("test.new.key", en_b["translations"])
            self.assertEqual(en_b["translations"]["test.new.key"]["translation_status"], "APPROVED")

            # Restore module paths
            ingest_module.CATALOG_PATH = orig_catalog
            ingest_module.LOCALES_DIR = orig_locales
        finally:
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    unittest.main()
