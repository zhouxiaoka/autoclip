# Caption translation and ending recovery

This change depends on the bounded pipeline/retry repairs. It does not authorize a release.

## Translation

Translation runs before optional decoration. Each production model request receives one
target subtitle row, with neighbouring rows as context only, and returns plain text. Code
owns the cue ID and timestamps. Real local-model experiments showed that a multi-row JSON
request could merge adjacent sentences and renumber them, even when the response parsed.

Accepted rows survive later malformed replies, transport errors, step deadlines and decoration
failure. Language, numbers, protected terms and conspicuously incomplete translations are
checked. There is at most one content-repair attempt per missing row; transport failures do
not trigger content retries. Responses that echo repair instructions are rejected, and oversized
rows fall back rather than consuming an unbounded request. Each request inherits the job deadline and has a 45-second cap.
The existing 300-second packaging budget still reserves time for export.

Project-local caches include subtitle text/timing, audience, protected terms, configured model
identity and policy version. Cache reads revalidate content; writes are atomic and private.
Only hashes name cache files. No captions, paths or model endpoints are added to analytics.

`translation_status` describes row coverage (`not_required`, `complete`, `partial`, or
`source_fallback`); it does not certify semantic accuracy or publication quality. Legacy
packages with no status remain unknown. Partial/source fallback is disclosed in all eight UI
locales and is not labelled as completed bilingual subtitles.

The editor's caption-only retry returns a suggestion for the current draft revision. It loads
only the selected source rows, reuses accepted cache entries, and preserves title/style and
scene selection. Its 120-second request step has a 180-second parent budget. It neither saves
the draft nor renders/overwrites a video; the normal save/export flow creates the new revision.
Stale revisions and out-of-bounds scenes are rejected before model requests. Leaving the
editor aborts applying the response; completed rows remain locally cached.

## Endings

Exhausting the forward sentence search is no longer treated as a completed ending. The
fallback searches for an earlier complete sentence and refuses cuts that remove most of the
clip. Unresolved endings retain a review flag through draft serialization and export warnings.

Model refinement sees the tail's context and must choose an allowed row. Explicit dangling
connectives and unpunctuated copulas are excluded; model extension is capped at 25 seconds.
The existing start alignment remains deterministic. Silence detection only adjusts within the
chosen ending's window and cannot select a later sentence. Platform duration caps also use
sentence endings; an unavoidable hard cut or unverified long-form extension is marked for review.
When a sentence cut falls inside an SRT row, its caption text is trimmed at the same nearby
sentence boundary before translation, so unspoken text is not burned into the ending.

These are heuristics plus model assistance, not word-level forced alignment. Unpunctuated
ASR, topic changes and model mistakes still require reviewing the final passage. Declined or
invalid model choices do not silently acquire a successful semantic-review status.

## Acceptance

Regression coverage includes cache recovery/invalidation, cancellation/deadlines, cue mapping,
numeric/name checks, preserved exports, stale editor requests, candidate IDs, neighbouring
clips, platform limits, audio alignment and localized result surfaces. Source checks use the
full quality gate. Real-media evidence must additionally bind input hashes, model/configuration,
source version, actual exported files and last-passage review; test counts are not media acceptance.

The representative media used locally are not the unavailable original production failures.
Raw video, subtitles, model replies and private run metadata stay outside this repository.
Installed Windows/macOS acceptance and release promotion remain separate, required steps.
