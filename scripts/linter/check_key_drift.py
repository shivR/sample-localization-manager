#!/usr/bin/env python3
"""
EthOS Cross-Project Localization Key Drift Sentinel
Runs in iOS and Android CI workflows to detect unregistered string keys,
prevent platform divergence, and provide an emergency override escape hatch
that automatically logs technical debt issues in sample-localization-manager.
"""

import os
import sys
import re
import json
import difflib
import subprocess
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CATALOG_PATH = os.path.join(WORKSPACE_DIR, "catalog", "master-catalog.json")

def load_catalog(catalog_path_or_url: str) -> dict:
    if catalog_path_or_url.startswith("http://") or catalog_path_or_url.startswith("https://"):
        req = urllib.request.urlopen(catalog_path_or_url, timeout=10)
        catalog = json.loads(req.read().decode("utf-8"))
    else:
        if not os.path.exists(catalog_path_or_url):
            raise FileNotFoundError(f"Catalog file not found at {catalog_path_or_url}")
        with open(catalog_path_or_url, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    return catalog.get("keys", {})

def load_catalog_keys(catalog_path_or_url: str) -> set:
    return set(load_catalog(catalog_path_or_url).keys())

def get_git_diff_added_lines(diff_range: str = "origin/main...HEAD") -> list:
    try:
        res = subprocess.run(
            ["git", "diff", diff_range],
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0 and res.stdout:
            return res.stdout.splitlines()
        # Fallback to unstaged / staged diff if range fails
        res2 = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            check=False
        )
        if res2.returncode == 0 and res2.stdout:
            return res2.stdout.splitlines()
        return []
    except Exception as e:
        print(f"  [WARN] git diff extraction failed: {e}", file=sys.stderr)
        return []

def extract_added_keys_ios(diff_lines: list) -> set:
    keys = set()
    for line in diff_lines:
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:].strip()
        # Skip pure comments
        if content.startswith("//") or content.startswith("/*") or content.startswith("*"):
            continue

        # 1. manager.string(for: "key", ...) or EthOSLocalizationManager.shared.string(for: "key", ...)
        for m in re.finditer(r'string\(\s*for:\s*"([^"]+)"', content):
            k = m.group(1).strip()
            if k:
                keys.add(k)

        # 2. iOS .strings / .stringsdict format: "key" = "Value";
        strings_match = re.search(r'^"([^"]+)"\s*=', content)
        if strings_match:
            k = strings_match.group(1).strip()
            if k:
                keys.add(k)

        # 3. Hardcoded SwiftUI UI text literals: Text("literal"), Button("literal"), Label("literal")
        for m in re.finditer(r'\b(?:Text|Button|Label)\(\s*(?:verbatim:\s*)?"([^"]+)"', content):
            k = m.group(1).strip()
            if k:
                keys.add(k)

    return keys

def extract_added_keys_android(diff_lines: list) -> set:
    keys = set()
    for line in diff_lines:
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:].strip()
        # Skip pure comments
        if content.startswith("//") or content.startswith("/*") or content.startswith("*") or content.startswith("<!--"):
            continue

        # 1. EthOSLocalizationManager.string("key") or string(key = "key")
        for m in re.finditer(r'string\(\s*(?:key\s*=\s*)?"([^"]+)"', content):
            k = m.group(1).strip()
            if k:
                keys.add(k)

        # 2. strings.xml: <string name="key">
        xml_match = re.search(r'<string\s+[^>]*name="([^"]+)"', content)
        if xml_match:
            k = xml_match.group(1).strip()
            if k:
                keys.add(k)

        # 3. Hardcoded Jetpack Compose text: Text("literal"), Text(text = "literal")
        for m in re.finditer(r'\bText\(\s*(?:text\s*=\s*)?"([^"]+)"', content):
            k = m.group(1).strip()
            if k:
                keys.add(k)

    return keys

def find_closest_matches(key: str, catalog_keys_dict: dict, n: int = 3) -> list:
    results = []
    # 1. Match against English source texts (if raw English text was passed)
    source_matches = []
    for ck, data in catalog_keys_dict.items():
        src = data.get("source_text", "")
        ratio = difflib.SequenceMatcher(None, key.lower(), src.lower()).ratio()
        if ratio >= 0.50:
            source_matches.append((ratio, ck, src))
    source_matches.sort(key=lambda x: x[0], reverse=True)
    for _, ck, src in source_matches[:2]:
        results.append(f"`{ck}` (Source: \"{src}\")")

    # 2. Match against key leaf (distinctive segment) to catch typos (require high similarity >= 0.70)
    key_leaf = key.split(".", 2)[-1] if key.count(".") >= 2 else key
    key_matches = []
    for ck in catalog_keys_dict.keys():
        ck_leaf = ck.split(".", 2)[-1] if ck.count(".") >= 2 else ck
        ratio = difflib.SequenceMatcher(None, key_leaf.lower(), ck_leaf.lower()).ratio()
        if ratio >= 0.70:
            key_matches.append((ratio, ck))
    key_matches.sort(key=lambda x: x[0], reverse=True)
    for _, ck in key_matches:
        if f"`{ck}`" not in results and not any(ck in r for r in results):
            results.append(f"`{ck}`")

    return results[:n]

def classify_key(key: str, catalog_keys_dict: dict) -> tuple:
    """Classifies an unregistered key to guide the developer accurately."""
    matches = find_closest_matches(key, catalog_keys_dict)
    if not matches:
        return ("NEW_KEY", "✨ Brand New Key (Not in Catalog)", "Add label `localization-override` to auto-ingest on merge")
    
    first = matches[0]
    if "Source:" in first:
        return ("SOURCE_MATCH", f"Reuses English text of {first}", f"Use canonical key `{first.split()[0].replace('`','')}` OR override if new key intended")
    return ("POSSIBLE_TYPO", f"Possible typo of {first}", f"Check if you intended to use `{first.replace('`','')}`")

def check_override_present(labels: list, pr_body: str) -> bool:
    if os.environ.get("LOCALIZATION_OVERRIDE", "").lower() in ("true", "1", "yes"):
        return True
    if any("localization-override" in str(l).lower() for l in labels):
        return True
    if pr_body and "[override-localization]" in pr_body.lower():
        return True
    return False

def dispatch_debt_issue(manager_repo: str, repo: str, pr_number: str, unregistered_keys: list, author: str, token: str):
    if not token:
        print("  [INFO] No LOCALIZATION_DISPATCH_TOKEN set. Skipping automated issue creation.")
        return
    url = f"https://api.github.com/repos/{manager_repo}/dispatches"
    payload = {
        "event_type": "localization_debt_logged",
        "client_payload": {
            "source_repo": repo,
            "pr_number": pr_number,
            "unregistered_keys": unregistered_keys,
            "author": author,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                print(f"  [SUCCESS] Dispatched localization debt alert to '{manager_repo}'!")
    except Exception as e:
        print(f"  [WARN] Failed to dispatch debt alert to {manager_repo}: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Cross-Project Localization Key Drift Sentinel")
    parser.add_argument("--repo", required=True, choices=["ios", "android"], help="Mobile platform under test")
    parser.add_argument("--catalog", default=CATALOG_PATH, help="Path or raw URL to master-catalog.json")
    parser.add_argument("--diff-range", default="origin/main...HEAD", help="Git diff comparison range")
    parser.add_argument("--pr-number", default=os.environ.get("PR_NUMBER", ""), help="Current Pull Request number")
    parser.add_argument("--author", default=os.environ.get("PR_AUTHOR", "developer"), help="PR Author handle")
    parser.add_argument("--labels", default=os.environ.get("PR_LABELS", ""), help="Comma-separated PR labels")
    parser.add_argument("--pr-body", default=os.environ.get("PR_BODY", ""), help="PR Description body")
    parser.add_argument("--manager-repo", default="shivR/sample-localization-manager", help="Central manager GitHub repository")
    parser.add_argument("--keys", nargs="*", help="Direct key list override for unit testing")

    args = parser.parse_args()

    print(f"\n{'=' * 70}")
    print(f"🛡️  Localization Key Drift Sentinel: repo='{args.repo}'")
    print(f"{'=' * 70}")

    catalog_dict = load_catalog(args.catalog)
    catalog_keys = set(catalog_dict.keys())
    print(f"  Loaded {len(catalog_keys)} canonical keys from catalog.")

    if args.keys is not None:
        detected_keys = set(args.keys)
    else:
        diff_lines = get_git_diff_added_lines(args.diff_range)
        if args.repo == "ios":
            detected_keys = extract_added_keys_ios(diff_lines)
        else:
            detected_keys = extract_added_keys_android(diff_lines)

    print(f"  Detected {len(detected_keys)} newly added/referenced string keys in PR.")

    unregistered_keys = sorted(list(detected_keys - catalog_keys))

    if not unregistered_keys:
        print("\n✅ [PASS] All detected localization keys are registered in the master catalog!")
        sys.exit(0)

    # We have unregistered keys
    labels_list = [l.strip() for l in args.labels.split(",") if l.strip()]
    override_active = check_override_present(labels_list, args.pr_body)

    print("\n" + "!" * 70)
    print(f"⚠️  UNREGISTERED LOCALIZATION KEYS DETECTED ({len(unregistered_keys)})")
    print("!" * 70)

    report_lines = []
    report_lines.append(f"### 🛑 Localization Governance Alert: Unregistered Keys in {args.repo.upper()} PR")
    report_lines.append(f"The following {len(unregistered_keys)} string key(s) added in this PR do not yet exist in `sample-localization-manager`:\n")
    report_lines.append("| Key in PR | Classification | Recommended Action |")
    report_lines.append("| :--- | :--- | :--- |")

    for k in unregistered_keys:
        category, status_desc, action_desc = classify_key(k, catalog_dict)
        print(f"  - Key: '{k}' -> Status: {status_desc}")
        report_lines.append(f"| `{k}` | {status_desc} | {action_desc} |")

    report_lines.append("\n### 💡 Introducing Brand New String Keys?")
    report_lines.append("You are completely free to add new keys! To proceed, choose one of these options:")
    report_lines.append("1. **Automated Ingestion (Recommended)**: Add the label `localization-override` to this PR. The check will pass immediately, and once merged to `main`, Model B will automatically register the new keys in `sample-localization-manager` and generate Gemini translations!")
    report_lines.append("2. **Catalog-First**: Register the new key in [sample-localization-manager](https://github.com/shivR/sample-localization-manager) via the Translation Dashboard before merging.")
    report_lines.append("3. **Typo Fix**: If any key above shows 'Possible Typo' or 'Reuses English text', check if you intended to reuse the existing key.\n")

    report_md = "\n".join(report_lines)

    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        try:
            with open(step_summary_path, "a", encoding="utf-8") as ssf:
                ssf.write(report_md + "\n")
        except Exception:
            pass

    if override_active:
        print("\n" + "*" * 70)
        print("✅ [EMERGENCY OVERRIDE DETECTED]")
        print("  Label 'localization-override' or tag present.")
        print("  Allowing PR merge. Logging tracked technical debt bug...")
        print("*" * 70)

        token = os.environ.get("LOCALIZATION_DISPATCH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        try:
            dispatch_debt_issue(
                manager_repo=args.manager_repo,
                repo=f"sample-localization-{args.repo}",
                pr_number=args.pr_number,
                unregistered_keys=unregistered_keys,
                author=args.author,
                token=token
            )
        except Exception as e:
            print(f"  [WARN] Issue dispatch failed: {e}", file=sys.stderr)

        print("\n✅ [OVERRIDE PERMITTED] Build succeeded! Keys will be auto-ingested into manager upon merge to main.\n")
        sys.exit(0)
    else:
        print("\n❌ [BLOCKED] PR blocked by localization governance.")
        print("  To allow these new keys and auto-ingest them on merge, add label: 'localization-override'")
        print("!" * 70 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
