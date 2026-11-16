#!/usr/bin/env python3
"""
EthOS Sample Localization Pipeline Unit & Integration Tests
Validates:
1. Compilation integrity
2. Placeholder validation
3. Immutability protection
4. Atomic publishing
5. Rollback execution
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from compiler import compile_bundle, load_master_catalog, compute_sha256, extract_placeholders
import publisher
import rollback

class TestSamplePipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_releases_dir = publisher.RELEASES_DIR
        publisher.RELEASES_DIR = os.path.join(self.temp_dir, "releases")
        rollback.RELEASES_DIR = os.path.join(self.temp_dir, "releases")

    def tearDown(self):
        publisher.RELEASES_DIR = self.orig_releases_dir
        rollback.RELEASES_DIR = self.orig_releases_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_catalog_and_placeholders(self):
        catalog, keys = load_master_catalog()
        self.assertGreaterEqual(len(keys), 15)
        
        ph = extract_placeholders("{completed} of {total} activities")
        self.assertEqual(ph, {"completed", "total"})

    def test_02_bundle_compilation(self):
        bundle_en = compile_bundle("en", "1.0.0")
        self.assertEqual(bundle_en["locale"], "en")
        self.assertEqual(bundle_en["translation_coverage"]["status"], "COMPLETE")
        self.assertEqual(bundle_en["translation_coverage"]["coverage_percent"], 100.0)

        bundle_es = compile_bundle("es", "1.0.0")
        self.assertEqual(bundle_es["locale"], "es")
        self.assertEqual(bundle_es["translation_coverage"]["status"], "PARTIAL")

    def test_03_atomic_publish_and_immutability(self):
        # First publish should succeed
        rel = publisher.publish_locale("en", "1.0.0", environment="development")
        self.assertEqual(rel["status"], "PUBLISHED")

        # Verify manifest was created
        manifest_path = publisher.get_manifest_path("development")
        self.assertTrue(os.path.exists(manifest_path))
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        self.assertIn("en", manifest["locales"])
        self.assertEqual(manifest["locales"]["en"]["version"], "1.0.0")

        # Attempting to re-publish 1.0.0 MUST fail due to immutability invariant
        with self.assertRaises(FileExistsError):
            publisher.publish_locale("en", "1.0.0", environment="development")

    def test_04_publish_and_rollback(self):
        # Publish v1.0.0
        publisher.publish_locale("es", "1.0.0", environment="development")
        
        # Publish v1.0.1
        publisher.publish_locale("es", "1.0.1", environment="development")
        
        manifest_path = publisher.get_manifest_path("development")
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["locales"]["es"]["version"], "1.0.1")

        # Rollback v1.0.1 -> v1.0.0
        rollback_entry = rollback.rollback_locale("es", "1.0.0", environment="development")
        self.assertEqual(rollback_entry["version"], "1.0.0")
        self.assertTrue(rollback_entry["rollback_metadata"]["is_rollback"])
        self.assertEqual(rollback_entry["rollback_metadata"]["rolled_back_from"], "1.0.1")

if __name__ == "__main__":
    unittest.main()
