# Issue follow-up — 2026-09-30

Baseline: merged main `48a94357`. Branch: `codex/issue-recovery-followup-20260930`.

## Reproduced defects

- **Scoring contract:** category recommendation prompts required `{id: reason}` while Step 3 expected an array containing `final_score`. Earlier authorized CLI/MCP real samples consequently matched zero scores. Default scoring now appends a common array contract and includes stable clip IDs. This round adds no paid calls and does not claim a fresh model-quality comparison.
- **Score identity:** main gave `[0.9, 0.2]` to clips 1/2 when a model returned scores in order 2/1; repaired alignment gives `[0.2, 0.9]`. Full long outlines work, ambiguous duplicate identities fall back, and unknown named results are not assigned by position.
- **Invalid scores:** main interpreted NaN as 1.0; repaired handling marks it unscored at 0.5. Infinity, negative/out-of-range scores and booleans also fall back.
- **Empty timeline recovery:** main drops a valid short tail because it only extends forward. The repaired path may extend backward along adjacent cues to the existing minimum, bounded by the previous topic and speech gaps. It does not extend a tail partially just to erase a gap and merge unrelated topics. Synthetic before/after: 0 → 1 candidate.
- **Timeline schema:** one malformed object previously caused the entire otherwise valid array to fail private global validation. Validation now operates per item, accepts a retained `title`, numeric seconds and standard one-digit-minute/long-minute colon forms, and still rejects invalid/overflow/non-finite values. Bounds remain absolute within the current subtitle chunk.
- **Rechunking:** old SRT block files remained in the project and were concatenated into later score excerpts. Step 1 now publishes an active chunk manifest; scoring reads only current blocks while keeping old files as diagnostics. Legacy projects without a manifest retain their old reader.

## Issue acceptance

- **#117:** a typed scoring protocol is in code, with injection at `ClipScorer` / `run_step3_scoring`. Default implementation still calls the current configured LLM. A custom backend runs actual Step 3 without initializing an LLM client, including threshold selection and saved output. See `SCORING_BACKENDS.md`.
- **#120:** the current home import already uses `Btn`, `Segmented` and `Dialog`. ProjectCard now uses `ac-card`, `ac-card-thumb`, `Btn`, `Icon`, `StatusDot` and `Dialog`; removes gradient/emoji-color category mapping and the unimplemented download action. Retry, feedback, delete and import confirmation remain. New status text covers all eight languages.
- Dialog now names its modal, focuses its controls, keeps Tab within it, and restores the prior focus on Escape/cancel; open AntD dropdowns retain their own keyboard handling. Thumbnail updates also react to the backend thumbnail field.

## Verification

- Scoring, timeline, quality and settings recovery: 63 targeted tests passed after the final protocol and chunk-manifest changes; full counts are in CI. Local full backend at that point: 774 passed / 3 skipped and one sandbox port-binding failure; that exact HTTP integration test passed separately with local listening allowed.
- Frontend 171 tests, typecheck, lint and build passed after the final Dialog focus change and integration of main `eaef5b0e` (#235); both sets of added translation keys were retained. Existing large-bundle/mixed-import build notices remain.
- `python -m backend.eval` passes both cases. New `public-interview-tail` uses real repository subtitle cues and a deliberately supplied eight-second candidate (not a recorded model response). It recovers to 21.109 seconds on cue boundaries; actual local ffmpeg output was nonempty H.264/AAC, approximately 21.27 seconds. It is a boundary regression, not the missing 5/60-minute editorial comparison in #116.
- agent-browser verified actual HomePage/ProjectCard components against isolated fixture API responses: four project states, no runtime error/overlay, light and dark themes, 820px width without horizontal overflow, Escape cancellation keeps four projects, focus starts on cancel, Shift+Tab/Tab cycle inside the modal, Escape restores Delete focus; keyboard confirmation deletes exactly the selected fixture, leaving three projects and no open dialog. Fixtures use no API keys and perform no model calls. Temporary screenshots and baseline comparison report are under `/tmp/autoclip-project-cards-*.png` and `/tmp/autoclip-followup-repro/report.json`.

#217/#198/#195/#182 get concrete recovery improvements but their unavailable original inputs remain a reproduction gap. #159 has no diagnostic body. A merge does not create signed installers, publish Intel packages, supply a human reviewer for #124, or complete #118/#116; those acceptance requirements remain explicit.
