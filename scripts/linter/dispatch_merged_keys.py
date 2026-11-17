#!/usr/bin/env python3
"""
EthOS Post-Merge Localization Key Dispatcher
Scans git diff after a merge commit on main. If unregistered localization keys
are detected, dispatches a 'ingest_new_keys' repository_dispatch event to
the central sample-localization-manager repository to trigger automated
catalog registration and Gemini AI translations.
"""

import os
import sys
import re
import json
import difflib
import subprocess
import urllib.request
import urllib.error
import argparse
from datetime import datetime, timezone

def load_catalog_keys(catalog_path_or_url: str) -> set:
    if catalog_path_or_url.startswith("http://") or catalog_path_or_url.startswith("https://"):
        req = urllib.request.urlopen(catalog_path_or_url, timeout=10)
        catalog = json.loads(req.read().decode("utf-8"))
    else:
        if not os.path.exists(catalog_path_or_url):
            raise FileNotFoundError(f"Catalog file not found at {catalog_path_or_url}")
        with open(catalog_path_or_url, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    return set(catalog.get("keys", {}).keys())

def get_git_diff_added_lines(diff_range: str = "HEAD~1...HEAD") -> list:
    try:
        cmd = ["git", "diff", diff_range]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] git diff failed for range '{diff_range}': {e.stderr.strip()}", file=sys.stderr)
        return []

def extract_merged_keys_ios(diff_lines: list) -> dict:
    """Returns mapping: { key_name: default_english_text }"""
    key_map = {}
    for line in diff_lines:
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:].strip()
        if content.startswith("//") or content.startswith("/*") or content.startswith("*"):
            continue

        # 1. string(for: "key", default: "default text")
        for m in re.finditer(r'string\(\s*for:\s*"([^"]+)"(?:\s*,\s*default:\s*"([^"]*)")?', content):
            k = m.group(1).strip()
            def_text = m.group(2).strip() if m.group(2) is not None else k
            if k and k not in key_map:
                key_map[k] = def_text

        # 2. "key" = "value";
        strings_match = re.search(r'^"([^"]+)"\s*=\s*"([^"]*)"', content)
        if strings_match:
            k = strings_match.group(1).strip()
            def_text = strings_match.group(2).strip()
            if k and k not in key_map:
                key_map[k] = def_text

        # 3. Text("literal"), Button("literal"), Label("literal")
        for m in re.finditer(r'\b(?:Text|Button|Label)\(\s*(?:verbatim:\s*)?"([^"]+)"', content):
            k = m.group(1).strip()
            if k and k not in key_map:
                key_map[k] = k

    return key_map

def extract_merged_keys_android(diff_lines: list) -> dict:
    """Returns mapping: { key_name: default_english_text }"""
    key_map = {}
    for line in diff_lines:
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:].strip()
        if content.startswith("//") or content.startswith("/*") or content.startswith("*") or content.startswith("<!--"):
            continue

        # 1. string(key = "key", default = "default text") or string("key", "default text")
        for m in re.finditer(r'string\(\s*(?:key\s*=\s*)?"([^"]+)"(?:\s*,\s*(?:default\s*=\s*)?"([^"]*)")?', content):
            k = m.group(1).strip()
            def_text = m.group(2).strip() if m.group(2) is not None else k
            if k and k not in key_map:
                key_map[k] = def_text

        # 2. <string name="key">default text</string>
        xml_match = re.search(r'<string\s+[^>]*name="([^"]+)"[^>]*>(.*?)</string>', content)
        if xml_match:
            k = xml_match.group(1).strip()
            def_text = xml_match.group(2).strip()
            if k and k not in key_map:
                key_map[k] = def_text

        # 3. Text("literal"), Text(text = "literal")
        for m in re.finditer(r'\bText\(\s*(?:text\s*=\s*)?"([^"]+)"', content):
            k = m.group(1).strip()
            if k and k not in key_map:
                key_map[k] = k

    return key_map

def send_github_dispatch(url: str, payload: dict, token: str) -> tuple:
    data = json.dumps(payload).encode("utf-8")
    auth_schemes = ["Bearer", "token"] if token.startswith("github_pat_") else ["token", "Bearer"]
    
    last_status = 0
    last_body = ""
    for scheme in auth_schemes:
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"{scheme} {token}",
                "User-Agent": "EthOS-Localization-Dispatcher/1.0",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 204):
                    return resp.status, ""
                last_status = resp.status
        except urllib.error.HTTPError as e:
            last_status = e.code
            last_body = e.read().decode("utf-8", errors="replace")
            if e.code != 401:
                break
        except Exception as e:
            last_status = 0
            last_body = str(e)
            break
            
    return last_status, last_body

def dispatch_ingest_event(manager_repo: str, repo: str, commit_sha: str, commit_msg: str, new_keys: list, token: str):
    if not token:
        print("\n  [INFO] No LOCALIZATION_DISPATCH_TOKEN set.")
        print("  To enable automated key ingestion into sample-localization-manager,")
        print("  set the LOCALIZATION_DISPATCH_TOKEN repository secret.")
        return

    url = f"https://api.github.com/repos/{manager_repo}/dispatches"
    payload = {
        "event_type": "ingest_new_keys",
        "client_payload": {
            "source_repo": repo,
            "commit_sha": commit_sha,
            "commit_message": commit_msg,
            "keys": new_keys,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    status, body = send_github_dispatch(url, payload, token)
    if status in (200, 204):
        print(f"\n  [SUCCESS] Dispatched {len(new_keys)} new key(s) to '{manager_repo}' for automated ingestion!")
    elif status == 403:
        print(f"\n  [WARN] Failed to dispatch ingest event to {manager_repo}: HTTP 403 Forbidden", file=sys.stderr)
        if body:
            print(f"  GitHub API Response: {body.strip()}", file=sys.stderr)
        print("\n  💡 How to resolve GitHub HTTP 403 Forbidden for LOCALIZATION_DISPATCH_TOKEN:", file=sys.stderr)
        print(f"  1. If using a Fine-Grained Personal Access Token (starts with 'github_pat_'):", file=sys.stderr)
        print(f"     - Under 'Repository access', select 'Only select repositories' and add '{manager_repo}'.", file=sys.stderr)
        print(f"     - Under 'Permissions' -> 'Repository permissions', set 'Contents' to 'Read and write'.", file=sys.stderr)
        print(f"  2. If using a Classic Personal Access Token (starts with 'ghp_'):", file=sys.stderr)
        print(f"     - Ensure the 'repo' scope checkbox is selected (full control of repositories).", file=sys.stderr)
        print(f"  3. Note: The automatic GitHub Actions '${{{{ secrets.GITHUB_TOKEN }}}}' cannot be used across repositories.", file=sys.stderr)
    else:
        print(f"\n  [WARN] Failed to dispatch ingest event to {manager_repo} (HTTP {status}): {body}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Dispatch newly merged localization keys to manager repo")
    parser.add_argument("--repo", required=True, choices=["ios", "android"], help="Source repository type")
    parser.add_argument("--catalog", default=None, help="Path to master-catalog.json")
    parser.add_argument("--diff-range", default="HEAD~1...HEAD", help="Git diff range for merge commit")
    parser.add_argument("--manager-repo", default="shivR/sample-localization-manager", help="Manager GitHub repo")
    parser.add_argument("--commit-sha", default=None, help="Current commit SHA")
    parser.add_argument("--commit-message", default=None, help="Merge commit message")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(f"🚀 Post-Merge Localization Key Sync: repo='{args.repo}'")
    print("=" * 70)

    # 1. Locate catalog
    catalog_path = args.catalog
    if not catalog_path:
        candidates = [
            ".manager/catalog/master-catalog.json",
            "catalog/master-catalog.json",
            "../sample-localization-manager/catalog/master-catalog.json"
        ]
        for c in candidates:
            if os.path.exists(c):
                catalog_path = c
                break

    if not catalog_path or not os.path.exists(catalog_path):
        print(f"  [WARN] Master catalog could not be located. Proceeding without catalog filter.")
        catalog_keys = set()
    else:
        catalog_keys = load_catalog_keys(catalog_path)
        print(f"  Loaded {len(catalog_keys)} canonical keys from catalog.")

    # 2. Extract merged keys
    diff_lines = get_git_diff_added_lines(args.diff_range)
    if args.repo == "ios":
        merged_keys = extract_merged_keys_ios(diff_lines)
    else:
        merged_keys = extract_merged_keys_android(diff_lines)

    print(f"  Extracted {len(merged_keys)} total referenced string(s) from diff range '{args.diff_range}'.")

    # 3. Filter for unregistered keys
    unregistered_items = []
    for k, def_text in merged_keys.items():
        if k not in catalog_keys:
            unregistered_items.append({
                "key": k,
                "default_text": def_text
            })

    if not unregistered_items:
        print("  ✅ All merged strings are already registered in master catalog. No action needed.")
        return

    print(f"\n  ⚠️  Found {len(unregistered_items)} unregistered string(s) merged into main:")
    for item in unregistered_items:
        print(f"     - Key: '{item['key']}' (Default text: '{item['default_text']}')")

    # 4. Resolve commit metadata
    commit_sha = args.commit_sha
    if not commit_sha:
        try:
            commit_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        except Exception:
            commit_sha = "unknown"

    commit_msg = args.commit_message
    if not commit_msg:
        try:
            commit_msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True).strip()
        except Exception:
            commit_msg = "Merged commit"

    # 5. Dispatch to manager repository
    token = os.environ.get("LOCALIZATION_DISPATCH_TOKEN", "").strip()
    dispatch_ingest_event(
        manager_repo=args.manager_repo,
        repo=f"sample-localization-{args.repo}",
        commit_sha=commit_sha,
        commit_msg=commit_msg,
        new_keys=unregistered_items,
        token=token
    )

if __name__ == "__main__":
    main()
