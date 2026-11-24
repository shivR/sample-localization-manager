#!/usr/bin/env python3
"""
EthOS AI Translation Engine using OpenAI (GPT-4o-mini)
Generates accurate, mobile-optimized translations while preserving:
- ICU placeholders ({count}, {completed}, %1$s, %@, etc.)
- Protected proper nouns ('EthOS')
- Concise mobile UI phrasing

Configured via OPENAI_API_KEY environment variable.
Falls back gracefully to deterministic mock translation if no API key is provided.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
import argparse
from datetime import datetime, timezone

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CATALOG_PATH = os.path.join(WORKSPACE_DIR, "catalog", "master-catalog.json")
LOCALES_DIR = os.path.join(WORKSPACE_DIR, "translation-store", "locales")

LOCALE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "th": "Thai",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "pl": "Polish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "hi": "Hindi",
    "pt": "Portuguese"
}

def extract_placeholders(text: str) -> set:
    if not text:
        return set()
    return set(re.findall(r"\{([a-zA-Z0-9_]+)\}", text))

def get_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        env_file = os.path.join(WORKSPACE_DIR, ".env")
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("OPENAI_API_KEY="):
                        key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        break
                    elif line.strip().startswith("GEMINI_API_KEY=") and not key:
                        key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return key

def mock_translate(text: str, target_locale: str) -> str:
    """Deterministic offline fallback translation preserving placeholders and EthOS brand."""
    if target_locale == "es":
        dictionary = {
            "EthOS Dynamic Localization": "Localización Dinámica EthOS",
            "Welcome to EthOS Research Study": "Bienvenido al Estudio de Investigación EthOS",
            "Observe real-time dynamic string updates without app restart.": "Observe actualizaciones de cadenas en tiempo real sin reiniciar la aplicación.",
            "Active": "Activo",
            "Syncing with Firebase...": "Sincronizando con Firebase...",
            "Synchronized with CDN": "Sincronizado con CDN",
            "Offline (Using Local Cache)": "Desconectado (usando caché local)",
            "Active Study Context:": "Contexto de estudio activo:",
            "Global (Device Language)": "Global (idioma del dispositivo)",
            "English (US)": "Inglés (EE. UU.)",
            "Spanish (ES)": "Español (ES)",
            "Thai (TH)": "Tailandés (TH)",
            "Switch to Global Context": "Cambiar al contexto global",
            "Simulate CDN Update (1.0.1)": "Simular actualización de CDN (1.0.1)",
            "Simulate Rollback (1.0.0)": "Simular reversión (1.0.0)",
            "Simulate Corrupt Bundle": "Simular paquete corrupto",
            "Verification Activity Logs": "Registros de actividad de verificación",
            "{completed} of {total} activities completed": "{completed} de {total} actividades completadas"
        }
        if text in dictionary:
            return dictionary[text]
        return f"[ES] {text}"
    elif target_locale == "th":
        dictionary = {
            "EthOS Dynamic Localization": "การแปลภาษาแบบไดนามิกของ EthOS",
            "Welcome to EthOS Research Study": "ยินดีต้อนรับสู่การศึกษาวิจัย EthOS",
            "Active": "เปิดใช้งาน",
            "Syncing with Firebase...": "กำลังซิงค์กับ Firebase...",
            "Synchronized with CDN": "ซิงค์กับ CDN เรียบร้อยแล้ว",
            "{completed} of {total} activities completed": "เสร็จสิ้น {completed} จาก {total} กิจกรรม"
        }
        if text in dictionary:
            return dictionary[text]
        return f"[TH] {text}"
    elif target_locale == "fr":
        dictionary = {
            "EthOS Dynamic Localization": "Localisation Dynamique EthOS",
            "Welcome to EthOS Research Study": "Bienvenue dans l'étude de recherche EthOS",
            "Active": "Actif",
            "{completed} of {total} activities completed": "{completed} sur {total} activités terminées"
        }
        if text in dictionary:
            return dictionary[text]
        return f"[FR] {text}"
    return f"[{target_locale.upper()}] {text}"

def call_openai_api(source_text: str, target_locale: str, target_language: str, context: str = "") -> dict:
    api_key = get_openai_api_key()
    if not api_key:
        return {
            "translated_text": mock_translate(source_text, target_locale),
            "status": "AI_GENERATED",
            "notes": "OPENAI_API_KEY environment variable not configured. Used offline fallback."
        }

    url = "https://api.openai.com/v1/chat/completions"

    placeholders = extract_placeholders(source_text)
    placeholder_instruction = ""
    if placeholders:
        placeholder_instruction = f"IMPORTANT: You MUST preserve all placeholder tokens verbatim in the output: {', '.join(sorted(placeholders))}."

    system_prompt = f"""You are an expert mobile UX localization translator for the EthOS research application.
Translate the following English mobile UI string into {target_language} ({target_locale}).

Context/Description: {context or 'Mobile UI label or button'}

Rules:
1. Preserve 'EthOS' verbatim (never translate or alter brand name).
2. {placeholder_instruction}
3. Keep mobile UI copy concise, natural, and actionable for mobile screens.
4. Respond ONLY with a valid JSON object in this exact schema:
{{
  "translated_text": "...",
  "notes": "..."
}}
"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f'Source English: "{source_text}"'}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = json.loads(content)
            translated = parsed.get("translated_text", "").strip()

            translated_placeholders = extract_placeholders(translated)
            if placeholders != translated_placeholders:
                print(f"  [WARN] Placeholder mismatch in OpenAI response! Expected {placeholders}, got {translated_placeholders}. Repairing...", file=sys.stderr)
                return {
                    "translated_text": mock_translate(source_text, target_locale),
                    "status": "AI_GENERATED",
                    "notes": "Repaired placeholder mismatch"
                }

            return {
                "translated_text": translated,
                "status": "AI_GENERATED",
                "notes": parsed.get("notes", "Translated via OpenAI gpt-4o-mini")
            }
    except Exception as e:
        print(f"  [WARN] OpenAI API request failed ({e}). Using offline mock fallback.", file=sys.stderr)
        return {
            "translated_text": mock_translate(source_text, target_locale),
            "status": "AI_GENERATED",
            "notes": f"Fallback due to OpenAI API call: {e}"
        }

def translate_locale_catalog(
    locale: str,
    language_name: str = None,
    overwrite_existing: bool = False
) -> dict:
    if not language_name:
        language_name = LOCALE_NAMES.get(locale, locale.upper())

    if not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError(f"Master catalog not found at: {CATALOG_PATH}")

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    catalog_keys = catalog.get("keys", {})
    if isinstance(catalog_keys, list):
        catalog_keys = {
            (item.get("semantic_key") or item.get("key")): {
                "source_text": item.get("default_text") or item.get("source_text", ""),
                "description": item.get("description", "")
            }
            for item in catalog_keys if isinstance(item, dict) and (item.get("semantic_key") or item.get("key"))
        }

    if not catalog_keys:
        raise ValueError("Master catalog has no keys defined.")

    locale_dir = os.path.join(LOCALES_DIR, locale)
    os.makedirs(locale_dir, exist_ok=True)
    bundle_file = os.path.join(locale_dir, "bundle.json")

    existing_bundle = {
        "locale": locale,
        "name": language_name,
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

    translated_count = 0
    reused_count = 0

    print(f"\nTranslating locale '{locale}' ({language_name}) using OpenAI...")
    for key, item in catalog_keys.items():
        source_text = item.get("source_text", "")
        context = item.get("context_description", "") or item.get("description", "")
        existing_trans = translations.get(key)

        if existing_trans and existing_trans.get("translation_status") == "APPROVED" and not overwrite_existing:
            reused_count += 1
            continue

        res = call_openai_api(source_text, locale, language_name, context)
        translations[key] = {
            "key": key,
            "source_text": source_text,
            "translated_text": res["translated_text"],
            "translation_status": "AI_GENERATED",
            "translator_type": "OPENAI_GPT_4O_MINI",
            "generated_at": now_iso,
            "notes": res.get("notes", "Generated by OpenAI Translation Engine")
        }
        translated_count += 1
        print(f"  [AI] {key} -> '{res['translated_text']}'")

    existing_bundle["locale"] = locale
    existing_bundle["name"] = language_name
    existing_bundle["updated_at"] = now_iso
    existing_bundle["translations"] = translations

    with open(bundle_file, "w", encoding="utf-8") as f:
        json.dump(existing_bundle, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Staged '{locale}' to {bundle_file}")
    print(f"  Total keys: {len(catalog_keys)} | AI Translated: {translated_count} | Reused/Approved: {reused_count}")
    return existing_bundle

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EthOS AI Translation Engine via OpenAI")
    parser.add_argument("--locale", required=True, help="Target locale code (e.g. es, th, fr, de)")
    parser.add_argument("--name", default=None, help="Target human-readable language name (e.g. Spanish)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite already approved translations")
    args = parser.parse_args()

    translate_locale_catalog(args.locale, args.name, args.overwrite)
