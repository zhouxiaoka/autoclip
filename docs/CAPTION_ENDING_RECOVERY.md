# Caption translation and ending recovery

This change depends on the bounded pipeline/retry repairs. It does not authorize a release.

## Translation

Translation runs before optional decoration. Display pages are rejoined into bounded source
utterances or short passages before translation, without crossing explicit speaker/scene
boundaries. Each production model request receives only that source unit and protected terms,
and returns plain text. Separate neighbouring context is excluded: local-model comparisons
showed that it could leak into the current cue. Code owns cue IDs and timestamps; display
pagination follows translation. Sentence boundaries exclude initials and common abbreviations.
Brief breaths do not split an unfinished clause. A source paragraph can retain shared context
up to 30 seconds/600 characters, while explicit speaker and scene changes remain separate.
Proper names are extracted within source units, excluding discourse-word combinations;
only names in the current unit enter its request. Reversible placeholders preserve their
original spelling. Missing or invented placeholders fail validation before cache writes.
Grounded uppercase acronyms and short lowercase consonant initialisms receive the same
protection; all-caps dialogue and common vocalizations are excluded from that inference.

Accepted rows survive later malformed replies, transport errors, step deadlines and decoration
failure. Language, numbers, protected terms and conspicuously incomplete translations are
checked, including newly repeated whole paragraphs. There is at most one content-repair attempt per missing unit; transport failures do
not trigger content retries. Responses that echo repair instructions are rejected, and oversized
rows fall back rather than consuming an unbounded request. Each request inherits the job deadline and has a 45-second cap.
When the rejected response invented English words by expanding a source abbreviation, the
single repair receives that concrete error instead of only a generic retry instruction.
The existing 300-second packaging budget still reserves time for export.
Equivalent small Chinese numerals (for example, Arabic 15 and Chinese fifteen) are accepted;
changed values and suffixes inside larger numbers are not. This checks numeric presence,
not the semantic relationship between quantities.

Project-local caches include subtitle text/timing, audience, protected terms, configured model
identity and policy version. Cache reads revalidate content; writes are atomic and private.
Only hashes name cache files. No captions, paths or model endpoints are added to analytics.

`translation_status` describes source-unit coverage (`not_required`, `complete`, `partial`, or
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
connectives and unpunctuated copulas are excluded. Extension requires a transcript-supported
sentence ending and is capped at 25 seconds; a complete original ending cannot grow into the
next topic. An invalid candidate ID gets at most one repair using allowed candidates only;
transport failures and explicit review requests are not retried.
Rhetorical lead-ins such as "you know what?" require their following statement. When such a
lead-in is inside the original selection, model candidates before it are removed so a
grammatical early cut cannot silently discard the conclusion. Genuine next questions still
allow retreat to the first completed answer when the duration constraints permit it.
The existing start alignment remains deterministic. Silence detection only adjusts within the
chosen ending's window and cannot select a later sentence. Platform duration caps also use
sentence endings; an unavoidable hard cut or unverified long-form extension is marked for review.
For adjacent ASR rows, a real audio pause can correct up to 250 ms of early row-end timing;
this tolerance does not add unconditional padding or permit a later topic's pause.
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
Comparisons still exposed untranslated units, incorrect negation and awkward idioms with the
local 3B model. Cloud comparisons also exposed name transliteration, numeral rejection,
early conclusion cuts and semantic mistranslations. Structural coverage and playable exports
do not constitute content acceptance; model self-review alone is not an acceptance oracle.
Sentence timing within an SRT row is estimated, not word-level alignment. Review the same
frozen material before/after and keep unresolved semantic errors as blockers.
Raw video, subtitles, model replies and private run metadata stay outside this repository.
Installed Windows/macOS acceptance and release promotion remain separate, required steps.
