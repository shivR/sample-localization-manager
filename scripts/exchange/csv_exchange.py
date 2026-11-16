#!/usr/bin/env python3
"""
EthOS CSV Exchange Engine for Google Sheets Translation Round-Trip
Supports:
1. Exporting English source strings + existing target translations to CSV
2. Importing translated CSV from Google Sheets / Excel
3. Parity cross-checking against master-catalog.json
4. Breaking-change detection with explicit user override protection
"""

import os
import sys
import csv
import json
import re
import argparse
from datetime import datetime, timezone

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CATALOG_PATH = os.path.join(WORKSPACE_DIR, "catalog", "master-catalog.json")
LOCALES_DIR = os.path.join(WORKSPACE_DIR, "translation-store", "locales")
EXCHANGE_DIR = os.path.join(WORKSPACE_DIR, "translation-store", "exchange")

def extract_placeholders(text: str) -> set:
    if not text:
        return set()
    return set(re.findall(r"\{([a-zA-Z0-9_]+)\}", text))

def export_locale_csv(locale: str, output_path: str = None) -> str:
    """Exports master catalog strings and existing locale translations to RFC 4180 CSV."""
    if not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError(f"Master catalog not found at {CATALOG_PATH}")

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    catalog_keys = catalog.get("keys", {})
    bundle_path = os.path.join(LOCALES_DIR, locale, "bundle.json")
    existing_translations = {}
    lang_name = locale.upper()

    if os.path.exists(bundle_path):
        with open(bundle_path, "r", encoding="utf-8") as f:
            try:
                bundle = json.load(f)
                existing_translations = bundle.get("translations", {})
                lang_name = bundle.get("name", lang_name)
            except Exception:
                pass

    if not output_path:
        os.makedirs(EXCHANGE_DIR, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(EXCHANGE_DIR, f"{locale}_translations_{timestamp}.csv")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["key", "source_english", f"translation_{locale}", "description", "category", "status"])

        for key, item in sorted(catalog_keys.items()):
            source = item.get("source_text", "")
            desc = item.get("description", "")
            cat = item.get("category", "GLOBAL_UI")

            trans_item = existing_translations.get(key, {})
            trans_text = trans_item.get("translated_text", "")
            status = trans_item.get("translation_status", "PENDING_TRANSLATION")

            writer.writerow([key, source, trans_text, desc, cat, status])

    print(f"[EXPORT SUCCESS] Exported {len(catalog_keys)} keys for '{locale}' ({lang_name}) to:")
    print(f"  {output_path}")
    return output_path

def import_locale_csv(
    csv_file: str,
    locale: str,
    allow_deletions: bool = False
) -> dict:
    """
    Imports translated CSV, cross-checks against master-catalog.json,
    detects breaking changes (missing keys, corrupted placeholders),
    and stages into translation-store.
    """
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    if not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError(f"Master catalog not found: {CATALOG_PATH}")

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    catalog_keys = catalog.get("keys", {})
    all_catalog_key_set = set(catalog_keys.keys())

    imported_rows = {}
    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        
        # Locate translation column (either translation_{locale} or translation or translated_text)
        trans_col = None
        for col in headers:
            if col.lower().startswith("translation") or col.lower() in ("target", "translated_text"):
                trans_col = col
                break
        
        if not trans_col:
            raise ValueError(f"Could not find a translation column in CSV. Found columns: {headers}")

        for row_num, row in enumerate(reader, start=2):
            key = row.get("key", "").strip()
            if not key:
                continue
            imported_rows[key] = {
                "key": key,
                "source_english": row.get("source_english", "").strip(),
                "translation": row.get(trans_col, "").strip(),
                "status": row.get("status", "IMPORTED_DRAFT").strip(),
                "line": row_num
            }

    imported_key_set = set(imported_rows.keys())

    # Check 1: Missing existing keys from catalog
    missing_catalog_keys = sorted(list(all_catalog_key_set - imported_key_set))
    
    # Check 2: Unregistered keys in CSV not in catalog
    unregistered_keys = sorted(list(imported_key_set - all_catalog_key_set))

    # Check 3: Placeholder verification
    placeholder_errors = []
    for key, data in imported_rows.items():
        if key in catalog_keys:
            cat_source = catalog_keys[key].get("source_text", "")
            cat_ph = extract_placeholders(cat_source)
            trans_ph = extract_placeholders(data["translation"])
            if data["translation"] and cat_ph != trans_ph:
                placeholder_errors.append({
                    "key": key,
                    "expected_placeholders": sorted(list(cat_ph)),
                    "found_placeholders": sorted(list(trans_ph)),
                    "translation": data["translation"]
                })

    # Parity Evaluation
    print(f"\n{'=' * 65}")
    print(f"CSV Import Parity Cross-Check: locale='{locale}', file='{os.path.basename(csv_file)}'")
    print(f"{'=' * 65}")
    print(f"  Catalog Keys Total:  {len(all_catalog_key_set)}")
    print(f"  Imported Rows:       {len(imported_rows)}")
    print(f"  Missing Keys:        {len(missing_catalog_keys)}")
    print(f"  Unregistered Keys:   {len(unregistered_keys)}")
    print(f"  Placeholder Errors:  {len(placeholder_errors)}")

    if placeholder_errors:
        err_msg = "\n".join([f"  - Key '{e['key']}': Expected {e['expected_placeholders']}, got {e['found_placeholders']}" for e in placeholder_errors[:5]])
        raise ValueError(f"Placeholder corruption in CSV:\n{err_msg}")

    if missing_catalog_keys and not allow_deletions:
        print("\n" + "!" * 65)
        print("⚠️  BREAKING CHANGE DETECTED: MISSING CATALOG KEYS")
        print("!" * 65)
        print(f"The imported CSV is missing {len(missing_catalog_keys)} keys present in the master catalog:")
        for mk in missing_catalog_keys[:10]:
            print(f"  - {mk} (English: '{catalog_keys[mk].get('source_text', '')}')")
        if len(missing_catalog_keys) > 10:
            print(f"  ... and {len(missing_catalog_keys) - 10} more.")
        print("\n[BLOCKED] Import rejected to prevent client-side string loss in production.")
        print("If you intentionally want to remove/unpublish these keys, re-run with:")
        print("  --allow-deletions")
        print("!" * 65 + "\n")
        raise ValueError(f"Missing {len(missing_catalog_keys)} catalog keys in imported CSV. User confirmation required (--allow-deletions).")

    if missing_catalog_keys and allow_deletions:
        print(f"\n[USER OVERRIDE ACKNOWLEDGED] Proceeding despite {len(missing_catalog_keys)} missing catalog keys.")

    # Load existing bundle
    bundle_file = os.path.join(LOCALES_DIR, locale, "bundle.json")
    os.makedirs(os.path.dirname(bundle_file), exist_ok=True)
    existing_bundle = {
        "locale": locale,
        "name": locale.upper(),
        "translations": {}
    }
    if os.path.exists(bundle_file):
        with open(bundle_file, "r", encoding="utf-8") as f:
            try:
                existing_bundle = json.load(f)
            except Exception:
                pass

    translations = existing_bundle.get("translations", {})
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    updated_count = 0
    retained_count = 0

    for key, item in catalog_keys.items():
        if key in imported_rows:
            imp_val = imported_rows[key]["translation"]
            imp_status = imported_rows[key]["status"]
            # If translation was provided in CSV:
            if imp_val:
                current = translations.get(key, {})
                prev_text = current.get("translated_text", "")
                
                # Determine status: if text changed, set to IMPORTED_DRAFT unless explicitly APPROVED in CSV
                new_status = imp_status if imp_status in ("APPROVED", "AI_GENERATED") else "IMPORTED_DRAFT"
                if prev_text == imp_val and current.get("translation_status") == "APPROVED":
                    new_status = "APPROVED"

                translations[key] = {
                    "key": key,
                    "source_text": item.get("source_text", ""),
                    "translated_text": imp_val,
                    "translation_status": new_status,
                    "translator_type": "GOOGLE_SHEETS_CSV",
                    "updated_at": now_iso
                }
                updated_count += 1
            else:
                retained_count += 1
        elif allow_deletions:
            # If missing and user allowed deletions, key is omitted or marked pending
            if key in translations:
                del translations[key]

    existing_bundle["locale"] = locale
    existing_bundle["updated_at"] = now_iso
    existing_bundle["translations"] = translations

    with open(bundle_file, "w", encoding="utf-8") as f:
        json.dump(existing_bundle, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] Imported {updated_count} translations into '{locale}' bundle.")
    print(f"  Staged at: {bundle_file}")
    
    return {
        "status": "SUCCESS",
        "locale": locale,
        "updated_keys": updated_count,
        "missing_keys_count": len(missing_catalog_keys),
        "unregistered_keys_count": len(unregistered_keys),
        "allowed_deletions": allow_deletions
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CSV Exchange for Google Sheets translation round-trip")
    parser.add_argument("--export", action="store_true", help="Export locale catalog to CSV")
    parser.add_argument("--import-file", dest="import_file", help="Path to translated CSV file to import")
    parser.add_argument("--locale", required=True, help="Target locale code (e.g. es, th, fr)")
    parser.add_argument("--output", help="Optional output path for exported CSV")
    parser.add_argument("--allow-deletions", action="store_true", help="Acknowledge and proceed if catalog keys are missing in CSV")

    args = parser.parse_args()

    if args.export:
        export_locale_csv(args.locale, args.output)
    elif args.import_file:
        import_locale_csv(args.import_file, args.locale, args.allow_deletions)
    else:
        parser.print_help()
