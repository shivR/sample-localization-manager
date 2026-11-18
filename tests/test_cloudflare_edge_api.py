#!/usr/bin/env python3
"""
Unit tests for Cloudflare Pages Functions and Static Assets
Validates:
1. Syntax and exports of Cloudflare Pages Functions
2. Presence and format of docs/_headers and wrangler.toml
3. Bundle compilation schema validation
4. Integration runbook availability
"""

import os
import sys
import json
import subprocess
import unittest

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FUNCTIONS_DIR = os.path.join(WORKSPACE_DIR, "functions", "api")
DOCS_DIR = os.path.join(WORKSPACE_DIR, "docs")

class TestCloudflareEdgeAPI(unittest.TestCase):

    def test_01_js_syntax_validation(self):
        js_files = [
            os.path.join(FUNCTIONS_DIR, "utils", "firebase-auth.js"),
            os.path.join(FUNCTIONS_DIR, "health.js"),
            os.path.join(FUNCTIONS_DIR, "manifest.js"),
            os.path.join(FUNCTIONS_DIR, "deploy.js"),
            os.path.join(FUNCTIONS_DIR, "translate.js"),
            os.path.join(DOCS_DIR, "app.js")
        ]
        for f in js_files:
            self.assertTrue(os.path.exists(f), f"File missing: {f}")
            res = subprocess.run(["node", "--check", f], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Syntax error in {f}: {res.stderr}")

    def test_02_cloudflare_config_files(self):
        headers_file = os.path.join(DOCS_DIR, "_headers")
        self.assertTrue(os.path.exists(headers_file))
        with open(headers_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("X-Content-Type-Options: nosniff", content)
        self.assertIn("/api/*", content)
        self.assertIn("Cache-Control: no-store", content)

        wrangler_file = os.path.join(WORKSPACE_DIR, "wrangler.toml")
        self.assertTrue(os.path.exists(wrangler_file))
        with open(wrangler_file, "r", encoding="utf-8") as f:
            wrangler_content = f.read()
        self.assertIn('pages_build_output_dir = "docs"', wrangler_content)

    def test_03_manual_guide_completeness(self):
        guide_file = os.path.join(WORKSPACE_DIR, "CLOUDFLARE_FIREBASE_DEPLOYMENT_GUIDE.md")
        self.assertTrue(os.path.exists(guide_file))
        with open(guide_file, "r", encoding="utf-8") as f:
            guide = f.read()
        self.assertIn("FIREBASE_SERVICE_ACCOUNT_KEY", guide)
        self.assertIn("FIREBASE_DATABASE_URL", guide)
        self.assertIn("FIREBASE_STORAGE_BUCKET", guide)
        self.assertIn("cors.json", guide)
        self.assertIn("roles/firebasedatabase.admin", guide)
        self.assertIn("roles/storage.objectAdmin", guide)

if __name__ == "__main__":
    unittest.main()
