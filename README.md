# EthOS Sample Localization Manager

This repository serves as the central authoring, review, governance, and publishing authority for dynamic localization in the EthOS sample application ecosystem.

## Architecture

- **Catalog (`catalog/master-catalog.json`)**: Master catalog of semantic keys (e.g. `ethos.sample.title`, `ethos.sample.btn.submit`).
- **Translation Store (`translation-store/locales/`)**: Stores source English text and human-reviewed target language translations.
- **Schemas (`schemas/`)**: JSON schemas enforcing Draft-07 validation for published bundles, database manifests, and release metadata.
- **Publishing Engine (`scripts/`)**:
  - `compiler.py`: Compiles translation store records into client-optimized bundles with placeholder validation and SHA-256 calculation.
  - `publisher.py`: Atomic 10-step publisher that stages bundles and updates the Realtime Database manifest.
  - `rollback.py`: Safe pointer rollback to previous release versions.
  - `export_fallbacks.py`: Generates native compile-time fallback strings for iOS (`Localizable.strings`) and Android (`strings.xml`).

## Commands

```bash
# Compile bundle
python3 scripts/compiler.py --locale es --version 1.0.0

# Publish locale release
python3 scripts/publisher.py --locale es --version 1.0.0 --env development

# Roll back locale
python3 scripts/rollback.py --locale es --target-version 1.0.0 --env development

# Export native fallbacks to mobile projects
python3 scripts/export_fallbacks.py

# Run test suite
python3 tests/test_sample_pipeline.py
```
