#!/usr/bin/env python3
"""
EthOS Sample Native Fallback Exporter
Generates native embedded fallback resources for:
- iOS (Localizable.strings) in sample-ios-app
- Android (strings.xml) in sample-android-app
"""

import os
import sys
import json
import xml.sax.saxutils as xml_utils
from pathlib import Path

MANAGER_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = MANAGER_DIR.parent
IOS_APP_DIR = ROOT_DIR / "sample-ios-app"
ANDROID_APP_DIR = ROOT_DIR / "sample-android-app"
LOCALES_DIR = MANAGER_DIR / "translation-store" / "locales"

LOCALES = ["en", "es", "th"]

IOS_LPROJ_MAP = {
    "en": "en.lproj",
    "es": "es.lproj",
    "th": "th.lproj"
}

ANDROID_VALUES_MAP = {
    "en": "values",
    "es": "values-es",
    "th": "values-th"
}

def escape_ios_string(text: str) -> str:
    if not text:
        return ""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

def escape_android_string(text: str) -> str:
    if not text:
        return ""
    escaped = xml_utils.escape(text)
    escaped = escaped.replace("'", "\\'").replace('"', '\\"')
    escaped = escaped.replace('\n', '\\n').replace('\r', '')
    return escaped

def semantic_key_to_android_name(key: str) -> str:
    sanitized = key.replace('.', '_').replace('-', '_')
    return sanitized

def load_approved_strings(locale: str) -> dict:
    bundle_path = LOCALES_DIR / locale / "bundle.json"
    if not bundle_path.exists():
        return {}
    with open(bundle_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    strings = {}
    translations = data.get("translations", {})
    for key, rec in translations.items():
        status = rec.get("translation_status")
        val = rec.get("translated_text")
        if locale == "en":
            val = rec.get("source_text")
        if val and (locale == "en" or status == "APPROVED"):
            strings[key] = val
    return strings

def export_ios(target_root: Path):
    print("--- Exporting iOS Localizable.strings ---")
    for loc in LOCALES:
        lproj = IOS_LPROJ_MAP.get(loc, f"{loc}.lproj")
        out_dir = target_root / "Resources" / "NativeFallbacks" / lproj
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "Localizable.strings"
        
        strings = load_approved_strings(loc)
        lines = [
            f"/* Generated Native Fallback Strings for EthOS Sample App ({loc}) */",
            f"/* Generated at {MANAGER_DIR.name} */\n"
        ]
        for key in sorted(strings.keys()):
            val = escape_ios_string(strings[key])
            lines.append(f'"{key}" = "{val}";')
            
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"  [PASS] Exported {len(strings)} strings to {out_file.relative_to(ROOT_DIR)}")

def export_android(target_root: Path):
    print("--- Exporting Android strings.xml ---")
    for loc in LOCALES:
        val_folder = ANDROID_VALUES_MAP.get(loc, f"values-{loc}")
        out_dir = target_root / "app" / "src" / "main" / "res" / val_folder
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "strings.xml"
        
        strings = load_approved_strings(loc)
        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<!-- Generated Native Fallback Strings for EthOS Sample App -->',
            '<resources>'
        ]
        for key in sorted(strings.keys()):
            res_name = semantic_key_to_android_name(key)
            val = escape_android_string(strings[key])
            lines.append(f'    <string name="{res_name}">{val}</string>')
        lines.append('</resources>')
        
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"  [PASS] Exported {len(strings)} strings to {out_file.relative_to(ROOT_DIR)}")

if __name__ == "__main__":
    export_ios(IOS_APP_DIR)
    export_android(ANDROID_APP_DIR)
    print("\n[SUCCESS] Exported native fallback files to sample iOS & Android apps!")
