# Step 3 scoring backends

`backend/pipeline/scoring_backend.py` defines `ScoringBackend.score(clips) -> list[ScoreResult]` (#117). The default `LLMScoringBackend` uses the existing `LLMClient`, selected provider and retry/cache behavior. No new external scoring service is included.

Each input contains `id`, `outline`, `content`, absolute `start_time`/`end_time`, and the corresponding `transcript` excerpt. Return one object per evaluated clip with the unchanged `id` (preferred) or full `outline`, `final_score` in 0–1, and `recommend_reason`. The backend evaluates content; the pipeline owns identity alignment, duration correction, threshold selection and video generation.

Inject an implementation into `ClipScorer(..., scoring_backend=backend)` or `run_step3_scoring(..., scoring_backend=backend)` from Python. A custom backend does not initialize `LLMClient` or require an LLM key. This is an in-process extension contract, not a plugin marketplace or a setting for loading arbitrary code.

Results may be reordered or partially missing. Alignment uses ID before full outline; duplicate identities are ambiguous, and unrelated named results are not assigned by position. Missing results, exceptions and invalid/non-finite scores receive the explicit 0.5 unscored fallback. Existing numeric 0–10/0–100 responses remain accepted; new backends should use 0–1. Scored custom results have `score_source=backend`, default results `llm`, and unscored results `fallback`.

All category recommendation prompts receive a final common score schema that overrides their older reason-only examples. This repairs the prompt/parser mismatch that caused the earlier real qwen-plus samples to return only unscored results. Behavioral acceptance in `backend/tests/test_scoring_backend.py` verifies the actual Step 3 runner, transcript inputs, identity alignment, failure behavior and every shipped category prompt without a paid model call.
