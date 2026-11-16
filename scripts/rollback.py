#!/usr/bin/env python3
"""
EthOS Sample Localization Rollback Engine
Performs atomic pointer rollback of a locale to a previously verified release.
"""

import os
import sys
import json
from datetime import datetime, timezone
import argparse
import jsonschema

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORE_DIR = os.path.join(WORKSPACE_DIR, "translation-store")
RELEASES_DIR = os.path.join(STORE_DIR, "releases")
SCHEMAS_DIR = os.path.join(WORKSPACE_DIR, "schemas")
DATABASE_MANIFEST_SCHEMA = os.path.join(SCHEMAS_DIR, "database-manifest.schema.json")

sys.path.insert(0, os.path.dirname(__file__))
from compiler import compute_sha256

def rollback_locale(
    locale: str,
    target_version: str,
    environment: str = "development",
    actor: str = "sample_admin",
    reason: str = "Linguistic quality review revert"
) -> dict:
    manifest_path = os.path.join(RELEASES_DIR, environment, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found for environment '{environment}' at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    locales_map = manifest.get("locales", {})
    if locale not in locales_map:
        raise ValueError(f"Locale '{locale}' has never been published in {environment}!")

    current_entry = locales_map[locale]
    current_version = current_entry["version"]
    if current_version == target_version:
        raise ValueError(f"Locale '{locale}' is already at target version '{target_version}'!")

    storage_staging_root = os.path.join(RELEASES_DIR, environment, "storage")
    target_rel_path = f"localization/locales/{locale}/{target_version}/bundle.json"
    target_file = os.path.join(storage_staging_root, target_rel_path)

    if not os.path.exists(target_file):
        raise FileNotFoundError(
            f"Target version '{target_version}' not found in storage at '{target_rel_path}'. "
            f"Rollback can only target previously verified and existing versions."
        )

    with open(target_file, "rb") as f:
        target_bytes = f.read()

    target_bundle = json.loads(target_bytes.decode("utf-8"))
    verified_checksum = compute_sha256(target_bytes)
    payload_hash = target_bundle.get("payload_hash")
    cov = target_bundle.get("translation_coverage", {})

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest["updated_at"] = now_iso
    manifest["locales"][locale] = {
        "locale": locale,
        "version": target_version,
        "path": target_rel_path,
        "checksum": verified_checksum,
        "payload_hash": payload_hash,
        "status": "ACTIVE",
        "coverage_percent": cov.get("coverage_percent", 0.0),
        "approved_keys_count": cov.get("approved_keys_count", 0),
        "total_catalog_keys": cov.get("total_catalog_keys", 0),
        "published_at": now_iso,
        "publisher_id": actor,
        "min_client_version": current_entry.get("min_client_version", "1.0.0"),
        "previous_version": current_version,
        "rollback_metadata": {
            "is_rollback": True,
            "rolled_back_at": now_iso,
            "rolled_back_from": current_version,
            "reason": reason,
            "actor": actor
        }
    }

    if os.path.exists(DATABASE_MANIFEST_SCHEMA):
        with open(DATABASE_MANIFEST_SCHEMA, "r", encoding="utf-8") as dms:
            manifest_schema = json.load(dms)
        jsonschema.validate(instance=manifest, schema=manifest_schema)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    history_path = os.path.join(RELEASES_DIR, "history.json")
    history = []
    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)

    rollback_event = {
        "event": "ROLLBACK",
        "locale": locale,
        "from_version": current_version,
        "to_version": target_version,
        "environment": environment,
        "timestamp": now_iso,
        "actor": actor,
        "reason": reason
    }
    history.append(rollback_event)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] Rolled back {locale} in {environment}: {current_version} -> {target_version}")
    return manifest["locales"][locale]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roll back locale to a previous version")
    parser.add_argument("--locale", required=True)
    parser.add_argument("--target-version", required=True)
    parser.add_argument("--env", default="development")
    parser.add_argument("--actor", default="sample_admin")
    parser.add_argument("--reason", default="Manual admin rollback")
    args = parser.parse_args()

    rollback_locale(
        locale=args.locale,
        target_version=args.target_version,
        environment=args.env,
        actor=args.actor,
        reason=args.reason
    )
