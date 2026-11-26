# Translating AutoClip

AutoClip currently ships with **13 languages** across the desktop UI, tray menus, and READMEs. Contributions to improve existing translations or add new languages are warmly welcome!

## Supported Languages (13)

`en` (English) · `zh` (简体中文) · `zh-TW` (繁體中文) · `ja` (日本語) · `ko` (한국어) · `es` (Español) · `pt` (Português) · `ru` (Русский) · `fr` (Français) · `id` (Bahasa Indonesia) · `tr` (Türkçe) · `vi` (Tiếng Việt) · `de` (Deutsch)

**Most-requested next languages (toward 20+):**
`it` (Italiano) · `pl` (Polski) · `th` (ไทย) · `nl` (Nederlands) · `uk` (Українська) · `hi` (हिन्दी) · `ar` (العربية)

---

## How Translations Work

1. **UI strings** live in `frontend/src/i18n/locales/<code>.json`, keyed off `en.json`.
   - Keep interpolation placeholders like `{{count}}` or `{{name}}` intact.
   - Brand names, model IDs, and technical flags stay in English.
   - Any missing key automatically falls back to `en.json` at runtime, though CI requires all shipped locale files to keep keys in sync with `en.json`.
2. **README translations** live in `docs/i18n/README-<CODE>.md` (English is root `README.md`).
   - All READMEs share identical command examples, badges, and language navigation links, enforced by `scripts/check_readmes.py`.

---

## Improving an Existing Language

1. Edit the corresponding JSON file in `frontend/src/i18n/locales/<code>.json` (and optionally `docs/i18n/README-<CODE>.md`).
2. Run the locale & README checks:
   ```bash
   python3 scripts/check_locales.py --check
   python3 scripts/check_readmes.py
   ```
3. Open a pull request!

---

## Adding a New Language

1. Copy `frontend/src/i18n/locales/en.json` to `frontend/src/i18n/locales/<code>.json` and translate the values.
2. Register the locale in `frontend/src/i18n/index.ts` and `frontend/src/i18n/language.ts`.
3. Add a translated README at `docs/i18n/README-<CODE>.md` and register it in `scripts/check_readmes.py` and `backend/tests/test_doc_versions.py`.
4. Run `python3 scripts/sync_readme_blocks.py` to synchronize shared badges, download CTA, and language navigation across all READMEs.
5. Verify everything passes:
   ```bash
   python3 scripts/check_locales.py --check
   python3 scripts/check_readmes.py
   ```
6. Open a pull request — thank you for helping make AutoClip accessible worldwide!
