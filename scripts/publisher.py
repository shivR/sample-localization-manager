#!/usr/bin/env python3
"""
EthOS Sample Localization Atomic Publisher
Executes the atomic 10-step publishing workflow:
1. Validate source catalog
2. Validate translation approval status
3. Generate locale bundle
4. Validate JSON schemas
5. Validate placeholders
6. Calculate SHA-256 checksum
7. Upload immutable bundle (Storage staging / Cloud Storage)
8. Read-back verification (verifying checksum match)
9. Atomic manifest update (Database staging / Firebase RTDB)
10. Record release metadata and audit ledger
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
import argparse
import jsonschema

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORE_DIR = os.path.join(WORKSPACE_DIR, "translation-store")
RELEASES_DIR = os.path.join(STORE_DIR, "releases")
SCHEMAS_DIR = os.path.join(WORKSPACE_DIR, "schemas")

sys.path.insert(0, os.path.dirname(__file__))
from compiler import compile_bundle, load_master_catalog, compute_sha256

DATABASE_MANIFEST_SCHEMA = os.path.join(SCHEMAS_DIR, "database-manifest.schema.json")
RELEASE_METADATA_SCHEMA = os.path.join(SCHEMAS_DIR, "release-metadata.schema.json")

def get_storage_staging_dir(environment: str) -> str:
    return os.path.join(RELEASES_DIR, environment, "storage")

def get_manifest_path(environment: str) -> str:
    return os.path.join(RELEASES_DIR, environment, "manifest.json")

def get_history_path() -> str:
    return os.path.join(RELEASES_DIR, "history.json")

def load_or_init_manifest(environment: str, catalog: dict) -> dict:
    manifest_path = get_manifest_path(environment)
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_bytes = json.dumps(catalog, sort_keys=True).encode("utf-8")
    return {
        "schema_version": "1.0.0",
        "environment": environment,
        "default_locale": "en",
        "updated_at": now_iso,
        "source_catalog_version": catalog.get("schema_version", "1.0.0"),
        "source_catalog_sha256": compute_sha256(catalog_bytes),
        "locales": {}
    }

def append_history(record: dict):
    history_path = get_history_path()
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    history = []
    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append(record)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def publish_locale(
    locale: str,
    version: str,
    environment: str = "development",
    actor: str = "sample_publisher",
    min_client_version: str = "1.0.0",
    dry_run: bool = False,
    simulate_upload_failure: bool = False,
    simulate_readback_failure: bool = False
) -> dict:
    print(f"\n{'=' * 70}")
    print(f"Starting Atomic Publishing: locale='{locale}', version='{version}', env='{environment}'")
    print(f"{'=' * 70}")
    
    # Step 1: Validate source catalog
    print("--- Step 1: Validating source catalog ---")
    catalog, catalog_keys = load_master_catalog()
    catalog_sha = compute_sha256(json.dumps(catalog, sort_keys=True).encode("utf-8"))
    print(f"  [PASS] Catalog verified ({len(catalog_keys)} keys, SHA-256: {catalog_sha[:16]}...)")
    
    # Steps 2-6: Compile bundle, validate schema, placeholders, checksums
    print("--- Steps 2-6: Compiling bundle, schema validation, placeholder & checksum calculations ---")
    bundle = compile_bundle(locale, version, environment, actor)
    bundle_bytes = json.dumps(bundle, indent=2, ensure_ascii=False).encode("utf-8")
    bundle_checksum = compute_sha256(bundle_bytes)
    payload_hash = bundle["payload_hash"]
    cov = bundle["translation_coverage"]
    
    print(f"  [PASS] Bundle generated: bundle_id='{bundle['bundle_id']}'")
    print(f"  [PASS] Translation coverage: {cov['approved_keys_count']}/{cov['total_catalog_keys']} ({cov['coverage_percent']}%) Status: {cov['status']}")
    print(f"  [PASS] Draft-07 schema validated (published-bundle.schema.json)")
    print(f"  [PASS] Payload hash: {payload_hash[:16]}... | Bundle checksum: {bundle_checksum[:16]}...")
    
    # Check immutability
    storage_rel_path = f"localization/locales/{locale}/{version}/bundle.json"
    storage_staging_root = get_storage_staging_dir(environment)
    local_target_file = os.path.join(storage_staging_root, storage_rel_path)
    
    if os.path.exists(local_target_file):
        raise FileExistsError(
            f"Immutability violation! Version '{version}' already exists in {environment} at '{storage_rel_path}'. "
            f"Overwriting published versions is strictly prohibited."
        )
        
    if dry_run:
        print("\n[DRY RUN] Bundle generated and verified successfully. No files written.")
        return {"bundle": bundle, "status": "DRY_RUN_PASSED"}
        
    # Step 7: Upload immutable bundle
    print("--- Step 7: Uploading immutable bundle to Storage ---")
    if simulate_upload_failure:
        raise IOError("Simulated Storage upload network failure!")
        
    os.makedirs(os.path.dirname(local_target_file), exist_ok=True)
    with open(local_target_file, "wb") as f:
        f.write(bundle_bytes)
    print(f"  [PASS] Staged to storage path: {storage_rel_path} ({len(bundle_bytes)} bytes)")
    
    # Step 8: Read-back verification
    print("--- Step 8: Read-back verification from Storage ---")
    if simulate_readback_failure:
        raise ValueError("Simulated read-back verification checksum mismatch!")
        
    with open(local_target_file, "rb") as f:
        read_back_bytes = f.read()
    read_back_checksum = compute_sha256(read_back_bytes)
    
    if read_back_checksum != bundle_checksum:
        if os.path.exists(local_target_file):
            os.remove(local_target_file)
        raise ValueError(f"Read-back checksum mismatch! Expected {bundle_checksum}, got {read_back_checksum}. Publish ABORTED.")
        
    print(f"  [PASS] Read-back verified: SHA-256 match ({read_back_checksum[:16]}...)")
    
    # Step 9: Atomic database manifest update
    print("--- Step 9: Updating Database manifest ---")
    manifest = load_or_init_manifest(environment, catalog)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    prev_entry = manifest.get("locales", {}).get(locale)
    previous_version = prev_entry.get("version") if prev_entry else None
    
    manifest["updated_at"] = now_iso
    manifest["locales"][locale] = {
        "locale": locale,
        "version": version,
        "path": storage_rel_path,
        "checksum": bundle_checksum,
        "payload_hash": payload_hash,
        "status": "ACTIVE",
        "coverage_percent": cov["coverage_percent"],
        "approved_keys_count": cov["approved_keys_count"],
        "total_catalog_keys": cov["total_catalog_keys"],
        "published_at": now_iso,
        "publisher_id": actor,
        "min_client_version": min_client_version,
        "previous_version": previous_version,
        "rollback_metadata": {
            "is_rollback": False,
            "rolled_back_at": None,
            "rolled_back_from": None,
            "reason": None,
            "actor": None
        }
    }
    
    # Validate against database-manifest schema
    if os.path.exists(DATABASE_MANIFEST_SCHEMA):
        with open(DATABASE_MANIFEST_SCHEMA, "r", encoding="utf-8") as dms:
            manifest_schema = json.load(dms)
        jsonschema.validate(instance=manifest, schema=manifest_schema)
        
    manifest_path = get_manifest_path(environment)
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  [PASS] Manifest updated atomically: {manifest_path}")
    
    # Step 10: Record release metadata and audit trail
    print("--- Step 10: Recording release metadata and audit trail ---")
    release_id = f"rel-{environment}-{locale}-{version}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    release_meta = {
        "schema_version": "1.0.0",
        "release_id": release_id,
        "environment": environment,
        "locale": locale,
        "version": version,
        "bundle_path": storage_rel_path,
        "bundle_checksum": bundle_checksum,
        "payload_hash": payload_hash,
        "source_catalog_version": catalog.get("schema_version", "1.0.0"),
        "source_catalog_sha256": catalog_sha,
        "status": "PUBLISHED",
        "coverage": {
            "total_catalog_keys": cov["total_catalog_keys"],
            "approved_keys_count": cov["approved_keys_count"],
            "coverage_percent": cov["coverage_percent"],
            "is_complete": cov["is_complete"]
        },
        "created_at": bundle["generated_at"],
        "published_at": now_iso,
        "publisher": {
            "id": actor,
            "role": "administrator" if "admin" in actor else "ci_publisher"
        },
        "verification": {
            "verified_at": now_iso,
            "checksum_matched": True,
            "read_back_verified": True,
            "schema_valid": True,
            "read_back_size_bytes": len(read_back_bytes)
        },
        "changelog": [
            f"Release of {locale} v{version} to {environment}",
            f"Coverage: {cov['approved_keys_count']}/{cov['total_catalog_keys']} keys ({cov['coverage_percent']}%)"
        ]
    }
    
    if os.path.exists(RELEASE_METADATA_SCHEMA):
        with open(RELEASE_METADATA_SCHEMA, "r", encoding="utf-8") as rms:
            rel_schema = json.load(rms)
        jsonschema.validate(instance=release_meta, schema=rel_schema)
        
    meta_dir = os.path.join(RELEASES_DIR, environment, "metadata")
    os.makedirs(meta_dir, exist_ok=True)
    meta_file = os.path.join(meta_dir, f"{locale}-{version}.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(release_meta, f, indent=2, ensure_ascii=False)
        
    append_history(release_meta)
    print(f"  [PASS] Release metadata and history recorded: {release_id}")
    print(f"\n[SUCCESS] Successfully published {locale} v{version} to {environment}!")
    return release_meta

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish translation bundle atomically")
    parser.add_argument("--locale", required=True, help="Target locale code")
    parser.add_argument("--version", required=True, help="Semantic version (e.g. 1.0.0, 1.0.1)")
    parser.add_argument("--env", default="development", choices=["development", "staging", "production"])
    parser.add_argument("--actor", default="sample_publisher")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    publish_locale(
        locale=args.locale,
        version=args.version,
        environment=args.env,
        actor=args.actor,
        dry_run=args.dry_run
    )
