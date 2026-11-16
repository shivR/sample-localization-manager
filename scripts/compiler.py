#!/usr/bin/env python3
"""
EthOS Sample Localization Bundle Compiler
Compiles translation store records into client-optimized immutable bundles.
Enforces schema validation, placeholder preservation, and SHA-256 calculation.
"""

import os
import sys
import json
import re
import hashlib
from datetime import datetime, timezone
import jsonschema

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CATALOG_PATH = os.path.join(WORKSPACE_DIR, "catalog", "master-catalog.json")
LOCALES_DIR = os.path.join(WORKSPACE_DIR, "translation-store", "locales")
SCHEMAS_DIR = os.path.join(WORKSPACE_DIR, "schemas")
PUBLISHED_BUNDLE_SCHEMA = os.path.join(SCHEMAS_DIR, "published-bundle.schema.json")

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def extract_placeholders(text: str) -> set:
    if not text:
        return set()
    named = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", text))
    positional = set(re.findall(r"%([0-9]+\$)?(@|d|s|f)", text))
    return named.union({p[0] + p[1] for p in positional})

def load_master_catalog() -> tuple:
    if not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError(f"Master catalog not found at {CATALOG_PATH}")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    keys = catalog.get("keys", {})
    return catalog, keys

def compile_bundle(
    locale: str,
    version: str,
    environment: str = "development",
    actor: str = "sample_publisher"
) -> dict:
    catalog, catalog_keys = load_master_catalog()
    locale_bundle_path = os.path.join(LOCALES_DIR, locale, "bundle.json")
    if not os.path.exists(locale_bundle_path):
        raise FileNotFoundError(f"Translation bundle not found for locale '{locale}' at {locale_bundle_path}")

    with open(locale_bundle_path, "r", encoding="utf-8") as f:
        store_data = json.load(f)

    translations = store_data.get("translations", {})
    strings_map = {}
    approved_count = 0

    for key, cat_entry in catalog_keys.items():
        source_text = cat_entry["source_text"]
        cat_placeholders = extract_placeholders(source_text)

        trans_record = translations.get(key)
        if not trans_record:
            continue

        status = trans_record.get("translation_status")
        val = trans_record.get("translated_text", "")
        if locale == "en":
            val = trans_record.get("source_text", val)

        if val and (locale == "en" or status == "APPROVED"):
            val_placeholders = extract_placeholders(val)
            if cat_placeholders != val_placeholders:
                raise ValueError(
                    f"Placeholder mismatch for key '{key}' in locale '{locale}'! "
                    f"Source: {cat_placeholders}, Target: {val_placeholders}"
                )
            strings_map[key] = val
            approved_count += 1

    total_keys = len(catalog_keys)
    coverage_percent = round((approved_count / total_keys) * 100.0, 1) if total_keys > 0 else 0.0
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Canonical payload for payload_hash (sorted strings JSON)
    payload_canonical = json.dumps(strings_map, sort_keys=True, ensure_ascii=False).encode("utf-8")
    payload_hash = compute_sha256(payload_canonical)

    status_str = "COMPLETE" if approved_count == total_keys else ("PARTIAL" if approved_count > 0 else "PENDING_TRANSLATION")

    bundle_skeleton = {
        "schema_version": "1.0.0",
        "bundle_id": f"bundle-{locale}-v{version}",
        "locale": locale,
        "version": version,
        "environment": environment,
        "source_catalog_version": catalog.get("schema_version", "1.0.0"),
        "source_catalog_sha256": compute_sha256(json.dumps(catalog, sort_keys=True).encode("utf-8")),
        "generated_at": now_iso,
        "target_platform": "all",
        "fallback_locale": "en",
        "payload_hash": payload_hash,
        "bundle_checksum": "0" * 64,  # placeholder
        "translation_coverage": {
            "total_catalog_keys": total_keys,
            "approved_keys_count": approved_count,
            "coverage_percent": coverage_percent,
            "is_complete": approved_count == total_keys,
            "status": status_str
        },
        "approved_revision_metadata": {
            "bundle_revision": 1,
            "last_updated": now_iso,
            "approver": actor
        },
        "strings": strings_map,
        "plurals": {}
    }

    # Compute bundle_checksum over the canonical content
    skeleton_bytes = json.dumps(bundle_skeleton, sort_keys=True, ensure_ascii=False).encode("utf-8")
    actual_checksum = compute_sha256(skeleton_bytes)
    bundle_skeleton["bundle_checksum"] = actual_checksum

    # Validate against schema
    if os.path.exists(PUBLISHED_BUNDLE_SCHEMA):
        with open(PUBLISHED_BUNDLE_SCHEMA, "r", encoding="utf-8") as sf:
            schema = json.load(sf)
        jsonschema.validate(instance=bundle_skeleton, schema=schema)

    return bundle_skeleton

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compile translation bundle")
    parser.add_argument("--locale", required=True, help="Target locale (e.g. en, es, th)")
    parser.add_argument("--version", default="1.0.0", help="Semantic version")
    args = parser.parse_args()

    b = compile_bundle(args.locale, args.version)
    b_bytes = json.dumps(b, indent=2, ensure_ascii=False).encode("utf-8")
    print(f"Bundle successfully compiled: {b['bundle_id']}")
    print(f"Coverage: {b['translation_coverage']['approved_keys_count']}/{b['translation_coverage']['total_catalog_keys']} ({b['translation_coverage']['coverage_percent']}%) Status: {b['translation_coverage']['status']}")
    print(f"Checksum: {b['bundle_checksum']}")
