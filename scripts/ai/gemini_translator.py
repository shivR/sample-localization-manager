#!/usr/bin/env python3
"""
EthOS AI Translation Engine (Legacy Compatibility Wrapper)
Delegates all translation requests to openai_translator.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from openai_translator import (
    extract_placeholders,
    get_openai_api_key,
    mock_translate,
    call_openai_api,
    translate_locale_catalog,
    LOCALE_NAMES
)

# Aliases for backwards compatibility
get_gemini_api_key = get_openai_api_key
call_gemini_api = call_openai_api

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EthOS AI Translation Engine (delegates to OpenAI)")
    parser.add_argument("--locale", required=True, help="Target locale code (e.g. es, th, fr, de)")
    parser.add_argument("--name", default=None, help="Target human-readable language name (e.g. Spanish)")
    parser.add_argument("--force", action="store_true", help="Force re-translation of previously approved keys")
    args = parser.parse_args()

    translate_locale_catalog(args.locale, args.name, args.force)
