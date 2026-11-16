#!/usr/bin/env python3
"""
Unit tests for CSV Exchange Engine (csv_exchange.py)
Validates:
1. Exporting catalog and translations to RFC 4180 CSV
2. Importing valid CSV
3. Detecting missing catalog keys (breaking-change detection)
4. Acknowledging user override (--allow-deletions)
5. Detecting corrupted placeholders
"""

import os
import sys
import csv
import json
import tempfile
import unittest

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "exchange"))

from csv_exchange import export_locale_csv, import_locale_csv

class TestCSVExchange(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.backup_bundle = None
        es_bundle = os.path.join(WORKSPACE_DIR, "translation-store", "locales", "es", "bundle.json")
        if os.path.exists(es_bundle):
            with open(es_bundle, "r", encoding="utf-8") as f:
                self.backup_bundle = f.read()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if self.backup_bundle:
            es_bundle = os.path.join(WORKSPACE_DIR, "translation-store", "locales", "es", "bundle.json")
            with open(es_bundle, "w", encoding="utf-8") as f:
                f.write(self.backup_bundle)

    def test_01_export_csv_format(self):
        csv_out = os.path.join(self.temp_dir, "export_es.csv")
        path = export_locale_csv("es", csv_out)
        self.assertTrue(os.path.exists(path))

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(header, ["key", "source_english", "translation_es", "description", "category", "status"])
            rows = list(reader)
            self.assertGreaterEqual(len(rows), 15)

    def test_02_import_valid_csv(self):
        csv_file = os.path.join(self.temp_dir, "import_es.csv")
        export_locale_csv("es", csv_file)
        
        result = import_locale_csv(csv_file, "es")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["missing_keys_count"], 0)

    def test_03_breaking_change_missing_keys_blocked(self):
        csv_file = os.path.join(self.temp_dir, "corrupted_es.csv")
        export_locale_csv("es", csv_file)

        # Truncate to first 3 rows to simulate missing keys
        with open(csv_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(csv_file, "w", encoding="utf-8") as f:
            f.writelines(lines[:4])

        with self.assertRaises(ValueError) as ctx:
            import_locale_csv(csv_file, "es", allow_deletions=False)
        self.assertIn("Missing", str(ctx.exception))

    def test_04_breaking_change_with_user_override(self):
        csv_file = os.path.join(self.temp_dir, "corrupted_es_override.csv")
        export_locale_csv("es", csv_file)

        # Truncate lines
        with open(csv_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(csv_file, "w", encoding="utf-8") as f:
            f.writelines(lines[:4])

        # With allow_deletions=True, must succeed
        result = import_locale_csv(csv_file, "es", allow_deletions=True)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertTrue(result["allowed_deletions"])
        self.assertGreater(result["missing_keys_count"], 0)

    def test_05_placeholder_corruption_rejected(self):
        csv_file = os.path.join(self.temp_dir, "placeholder_error.csv")
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["key", "source_english", "translation_es", "status"])
            # Corrupted placeholder: {completed} -> {hecho}
            writer.writerow([
                "ethos.sample.counter.completed_tasks",
                "{completed} of {total} activities completed",
                "{hecho} de {total} completadas",
                "IMPORTED_DRAFT"
            ])

        with self.assertRaises(ValueError) as ctx:
            import_locale_csv(csv_file, "es", allow_deletions=True)
        self.assertIn("Placeholder corruption", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
