# EthOS Sample Localization Manager

This repository serves as the central authoring, review, governance, and publishing authority for dynamic localization in the EthOS application ecosystem.

---

## 1. Architecture Overview

- **Catalog (`catalog/master-catalog.json`)**: Master catalog of semantic keys (e.g. `ethos.sample.title`, `ethos.sample.btn.submit`).
- **Translation Store (`translation-store/locales/`)**: Stores source English text and target language translations (`en`, `es`, `th`, `fr`, etc.).
- **Schemas (`schemas/`)**: JSON schemas enforcing Draft-07 validation for published bundles, database manifests, and release metadata.
- **Web Dashboard (`docs/index.html`)**: Interactive review UI with 1-click OpenAI auto-translation, CSV Google Sheets exchange, and Firebase deployment.
- **Publishing & Governance Engine (`scripts/`)**:
  - `ai/openai_translator.py`: Generates mobile-optimized translations via OpenAI (GPT-4o-mini) while preserving ICU tokens and brand proper nouns (with `ai/gemini_translator.py` compatibility wrapper).
  - `exchange/csv_exchange.py`: Exports and imports CSV for external linguists (Google Sheets round-trip) with breaking-change detection.
  - `linter/check_key_drift.py`: Cross-project PR governance sentinel that blocks unregistered keys with an emergency override escape hatch.
  - `compiler.py`: Compiles translation store records into client-optimized bundles with placeholder validation.
  - `publisher.py`: Atomic 10-step publisher that stages bundles and updates the Realtime Database manifest.
  - `rollback.py`: Safe pointer rollback to previous release versions.
  - `export_fallbacks.py`: Generates native compile-time fallback strings for iOS (`Localizable.strings`) and Android (`strings.xml`).

---

## 2. AI Translation Setup with OpenAI

The translation engine integrates **OpenAI GPT-4o-mini** for rapid, culturally authentic, and mobile-concise translations while strictly safeguarding ICU placeholders (e.g., `{completed}`, `{total}`) and the protected proper noun `EthOS`.

### Step 1: Obtain an OpenAI API Key
1. Visit [OpenAI API Keys](https://platform.openai.com/api-keys).
2. Sign in with your OpenAI account and click **"Create new secret key"**.
3. Create an API key and copy it (starts with `sk-...`).

### Step 2: Configure Environment Variable
In your terminal, export the key (or add it to your shell profile / `.env` file):
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

### Step 3: Run AI Translation
To translate a new language or auto-translate missing strings:
```bash
# Translate French (fr)
python3 scripts/ai/openai_translator.py --locale fr --name French

# Auto-translate missing strings in Spanish (es)
python3 scripts/ai/openai_translator.py --locale es --name Spanish
```
> *Note:* If `OPENAI_API_KEY` is omitted, the engine automatically falls back to an offline deterministic mock translator for development and test suites.

---

## 3. Google Sheets CSV Round-Trip Translation

For teams collaborating with human linguists or reviewing translations in spreadsheets:

### Step 1: Export Strings to CSV
```bash
python3 scripts/exchange/csv_exchange.py --export --locale es
```
This generates an RFC 4180 CSV file: `translation-store/exchange/es_translations_<timestamp>.csv` with headers:
`key, source_english, translation_es, description, category, status`

### Step 2: Translate in Google Sheets
1. Open [Google Sheets](https://sheets.new) and import the exported CSV.
2. Edit or add translations in the `translation_es` column.
3. Download as **Comma Separated Values (.csv)**.

### Step 3: Import and Validate Parity
```bash
python3 scripts/exchange/csv_exchange.py --import-file path/to/translated.csv --locale es
```
**Breaking-Change Protection:**
- If any existing catalog keys are missing from the uploaded CSV, the import is **automatically blocked** to prevent string loss in production:
  ```
  ⚠️ BREAKING CHANGE DETECTED: MISSING CATALOG KEYS
  The imported CSV is missing 2 keys present in the master catalog:
    - ethos.sample.btn.exit_study (English: 'Exit Study')
    - ethos.sample.btn.refresh (English: 'Check for Updates')
  ```
- **User Override:** If you intentionally want to proceed and allow missing strings to fall back to English, re-run with:
  ```bash
  python3 scripts/exchange/csv_exchange.py --import-file path/to/translated.csv --locale es --allow-deletions
  ```

---

## 4. Web Review Dashboard (GitHub Pages / Local)

The repository includes a responsive web application in `docs/index.html` that can be hosted via **GitHub Pages** or served locally:

```bash
# Serve dashboard locally
python3 -m http.server 8080 --directory docs/
# Open in browser: http://localhost:8080
```

### Dashboard Capabilities:
- **Locale Switcher**: Switch between active languages or add a new locale.
- **Add New String**: Modal to introduce a new semantic key and English text with instant multi-language translation.
- **Auto-Translate with OpenAI**: 1-click batch translation of all pending keys.
- **Export / Import CSV**: Direct file download and drag-and-drop upload with breaking-change warning dialogs.
- **Review Table**: In-line text editing, single-key `[Approve]` / `[Reject]`, and `[Approve All Visible]`.
- **1-Click Deploy to Firebase**: Bumps the semantic version (`1.0.0` -> `1.1.0`), runs dual-gate verification, and deploys to Firebase Storage and Realtime Database.

---

## 5. Cross-Project PR Governance Sentinel

When iOS or Android developers create a Pull Request that introduces or modifies localization keys:

1. **Automated CI Check**:
   - The workflow `.github/workflows/pr-localization-sentinel.yml` runs in `sample-localization-ios` and `sample-localization-android`.
   - It compares `git diff origin/main...HEAD` against `master-catalog.json`.
2. **PR Blocking Behavior**:
   - If an unregistered key is detected, the check **fails and blocks the PR from merging**.
   - A sticky bot comment is posted with closest matching keys (e.g. `auth_login` -> `ethos.sample.actions.login`).
3. **Emergency Override Escape Hatch**:
   - For urgent hotfixes, an engineer can add the PR label `localization-override` (or write `[override-localization]` in the PR body).
   - The check passes to allow the merge, but automatically dispatches an event to this manager repo to create a **tracked technical debt GitHub Issue**.

---

## 6. CLI Operational Reference

```bash
# 1. Compile bundle
python3 scripts/compiler.py --locale es --version 1.0.0

# 2. Publish locale release to Firebase
python3 scripts/publisher.py --locale es --version 1.0.0 --env development

# 3. Emergency rollback
python3 scripts/rollback.py --locale es --target-version 1.0.0 --env development

# 4. Export native fallbacks to mobile projects
python3 scripts/export_fallbacks.py --platform all

# 5. Run test suites
python3 tests/test_ai_translation.py
python3 tests/test_csv_exchange.py
python3 tests/test_key_drift_linter.py
python3 tests/test_sample_pipeline.py
```
