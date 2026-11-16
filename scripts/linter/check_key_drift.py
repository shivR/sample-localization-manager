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

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CATALOG_PATH = os.path.join(WORKSPACE_DIR, "catalog", "master-catalog.json")

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
        return res2.stdout.splitlines() if res2.returncode == 0 else []
    except Exception as e:
        print(f"[WARN] Failed to read git diff: {e}", file=sys.stderr)
        return []

def extract_added_keys_ios(diff_lines: list) -> set:
    keys = set()
    for line in diff_lines:
        if line.startswith("+") and not line.startswith("+++"):
            # iOS .strings pattern: "key.name" = "Value";
            strings_match = re.search(r'^\+\s*"([a-zA-Z0-9_.-]+)"\s*=', line)
            if strings_match:
                keys.add(strings_match.group(1))
            # Swift code pattern: string(for: "key.name")
            swift_match = re.search(r'string\(\s*for:\s*"([a-zA-Z0-9_.-]+)"', line)
            if swift_match:
                keys.add(swift_match.group(1))
    return keys

def extract_added_keys_android(diff_lines: list) -> set:
    keys = set()
    for line in diff_lines:
        if line.startswith("+") and not line.startswith("+++"):
            # Android strings.xml pattern: <string name="key_name">
            xml_match = re.search(r'^\+\s*<string\s+name="([a-zA-Z0-9_.-]+)"', line)
            if xml_match:
                keys.add(xml_match.group(1))
            # Kotlin code pattern: string("key.name")
            kt_match = re.search(r'string\(\s*"([a-zA-Z0-9_.-]+)"', line)
            if kt_match:
                keys.add(kt_match.group(1))
    return keys

def find_closest_matches(key: str, catalog_keys: set, n: int = 3) -> list:
    return difflib.get_close_matches(key, catalog_keys, n=n, cutoff=0.3)

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

    catalog_keys = load_catalog_keys(args.catalog)
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
    report_lines.append(f"The following {len(unregistered_keys)} string keys added in this PR do not exist in `sample-localization-manager`:\n")
    report_lines.append("| Added Key in PR | Suggested Catalog Match | Action Required |")
    report_lines.append("| :--- | :--- | :--- |")

    for k in unregistered_keys:
        matches = find_closest_matches(k, catalog_keys)
        match_str = f"`{matches[0]}`" if matches else "*No close match*"
        print(f"  - Key: '{k}' -> Closest Match: {match_str}")
        report_lines.append(f"| `{k}` | {match_str} | Use canonical key OR register in manager |")

    report_lines.append("\n### How to Resolve:")
    report_lines.append("1. **Reuse Existing Key**: If one of the suggested catalog keys fits your semantic use case, change your code to use that key.")
    report_lines.append("2. **Register New Key**: Add the key in [sample-localization-manager](https://github.com/shivR/sample-localization-manager) via the Translation Dashboard.")
    report_lines.append("3. **Emergency Override**: If this is a critical hotfix, add the label `localization-override` to this PR. The check will pass and automatically file a tracked technical debt bug in the manager repo.\n")

    report_md = "\n".join(report_lines)

    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        with open(step_summary_path, "a", encoding="utf-8") as ssf:
            ssf.write(report_md + "\n")

    if override_active:
        print("\n" + "*" * 70)
        print("⚠️  [EMERGENCY OVERRIDE DETECTED]")
        print("  Label 'localization-override' or tag present.")
        print("  Allowing PR merge, but logging tracked technical debt bug...")
        print("*" * 70)

        token = os.environ.get("LOCALIZATION_DISPATCH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        dispatch_debt_issue(
            manager_repo=args.manager_repo,
            repo=f"sample-localization-{args.repo}",
            pr_number=args.pr_number,
            unregistered_keys=unregistered_keys,
            author=args.author,
            token=token
        )
        print("✅ [OVERRIDE PERMITTED] Build succeeded with technical debt warning.\n")
        sys.exit(0)
    else:
        print("\n❌ [BLOCKED] PR blocked by localization governance.")
        print("  To bypass for an urgent hotfix, add label: 'localization-override'")
        print("!" * 70 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
