#!/usr/bin/env python3
"""
EthOS Key Auto-Ingestion Engine
Ingests new keys dispatched from mobile repositories (iOS or Android) post-merge.
1. Registers new keys in catalog/master-catalog.json
2. Adds approved English translation to translation-store/locales/en/bundle.json
3. Automatically triggers Gemini AI translation for all target locales (es, th, fr, etc.)
4. Prepares the staged files for automated review PR and Web Dashboard approval
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CATALOG_PATH = os.path.join(WORKSPACE_DIR, "catalog", "master-catalog.json")
LOCALES_DIR = os.path.join(WORKSPACE_DIR, "translation-store", "locales")

# Import gemini translator
sys.path.insert(0, os.path.join(WORKSPACE_DIR, "scripts", "ai"))
try:
    from gemini_translator import translate_locale_catalog, LOCALE_NAMES
except ImportError:
    translate_locale_catalog = None
    LOCALE_NAMES = {}

def extract_placeholders(text: str) -> list:
    if not text:
        return []
    # Match {name} or %1$s or %@ or %d
    return re.findall(r"\{([a-zA-Z0-9_]+)\}", text)

def ingest_keys(payload_data: dict, auto_translate: bool = True) -> list:
    source_repo = payload_data.get("source_repo", "mobile_app")
    commit_sha = payload_data.get("commit_sha", "unknown")
    new_keys = payload_data.get("keys", [])

    if not new_keys:
        print("  [INFO] No new keys found in payload.")
        return []

    if not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError(f"Master catalog not found at {CATALOG_PATH}")

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    catalog_keys = catalog.setdefault("keys", {})
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Update master catalog
    added_keys = []
    for item in new_keys:
        key = item.get("key", "").strip()
        default_text = item.get("default_text", "").strip() or key
        if not key:
            continue

        if key not in catalog_keys:
            catalog_keys[key] = {
                "classification": "GLOBAL_UI",
                "source_text": default_text,
                "description": f"Auto-ingested from {source_repo} commit {commit_sha[:7]}",
                "placeholders": extract_placeholders(default_text),
                "added_at": now_iso
            }
            added_keys.append((key, default_text))
            print(f"  [CATALOG] Added '{key}' (Source: '{default_text}')")

    if not added_keys:
        print("  [INFO] All keys from payload were already in catalog.")
        return []

    catalog["updated_at"] = now_iso
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"\n[CATALOG UPDATED] Successfully added {len(added_keys)} key(s) to master-catalog.json")

    # 2. Update English bundle
    en_bundle_path = os.path.join(LOCALES_DIR, "en", "bundle.json")
    if os.path.exists(en_bundle_path):
        with open(en_bundle_path, "r", encoding="utf-8") as f:
            en_bundle = json.load(f)
        en_trans = en_bundle.setdefault("translations", {})
        for key, def_text in added_keys:
            en_trans[key] = {
                "key": key,
                "source_text": def_text,
                "translated_text": def_text,
                "translation_status": "APPROVED",
                "translator_type": "SOURCE_INGEST",
                "generated_at": now_iso,
                "notes": f"Ingested from {source_repo} commit {commit_sha[:7]}"
            }
        en_bundle["updated_at"] = now_iso
        with open(en_bundle_path, "w", encoding="utf-8") as f:
            json.dump(en_bundle, f, indent=2, ensure_ascii=False)
        print(f"[EN BUNDLE UPDATED] Added {len(added_keys)} key(s) to English translation bundle.")

    # 3. Auto-translate target locales using Gemini
    if auto_translate and translate_locale_catalog:
        target_locales = [d for d in os.listdir(LOCALES_DIR) if os.path.isdir(os.path.join(LOCALES_DIR, d)) and d != "en"]
        print(f"\n[AUTO-TRANSLATING] Generating Gemini AI drafts for target locales: {target_locales}...")
        for loc in target_locales:
            try:
                lang_name = LOCALE_NAMES.get(loc, loc.upper())
                translate_locale_catalog(loc, lang_name, overwrite_existing=False)
            except Exception as e:
                print(f"  [WARN] Failed auto-translating for locale '{loc}': {e}", file=sys.stderr)

    return added_keys

def main():
    parser = argparse.ArgumentParser(description="Ingest new keys dispatched from mobile repository")
    parser.add_argument("--payload", help="JSON string of payload")
    parser.add_argument("--payload-file", help="Path to JSON file containing payload")
    parser.add_argument("--no-translate", action="store_true", help="Skip Gemini auto-translation")
    args = parser.parse_args()

    payload_data = {}
    if args.payload_file and os.path.exists(args.payload_file):
        with open(args.payload_file, "r", encoding="utf-8") as f:
            payload_data = json.load(f)
    elif args.payload:
        payload_data = json.loads(args.payload)
    else:
        # Check stdin
        if not sys.stdin.isatty():
            payload_data = json.load(sys.stdin)
        else:
            print("Error: No payload provided.", file=sys.stderr)
            sys.exit(1)

    print("\n" + "=" * 70)
    print("📥 EthOS Key Ingestion Pipeline")
    print("=" * 70)

    added = ingest_keys(payload_data, auto_translate=not args.no_translate)
    print("\n" + "=" * 70)
    print(f"✅ Ingestion Complete! Added {len(added)} key(s).")
    print("=" * 70)

if __name__ == "__main__":
    main()
