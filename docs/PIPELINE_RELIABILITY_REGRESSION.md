# Request and transcription reliability regressions

The v1.5.8 diagnosis found permanent provider errors being retried as malformed
model output, then routed into the legacy analysis pipeline. It also found empty
subtitle files bypassing ASR readiness and being reused on retry; runtime and stop
errors could become an incorrect `transcription_empty` result.

## Request boundaries

- Only invalid model output may enter format repair / legacy analysis. HTTP,
  transport and unknown runtime errors retain their original exception and
  request attribution. Quota, key and endpoint failures stop after one call.
- A clip window has at most two request callbacks, shared across format and
  transport repairs. Transient failures retain bounded backoff; exhausted
  transport retries never start legacy analysis. Existing SDK-level limits and
  the enclosing job time budget still apply, so callback counts are not claims
  about the exact number of HTTP packets sent by every SDK.
- The first terminal window failure stops queued windows and wakes sibling
  retry waits. Already running provider requests drain; this does not claim
  remote cancellation or cancellation of charges already incurred.
- Cancellation, deletion, shutdown and exhausted budgets survive the safe error
  boundary. Task persistence retains status, HTTP status and upstream type;
  Studio still owns the enclosing generation outcome.

## Transcription boundaries

- Readiness, local planning, resume and the adapter require parsed nonempty SRT
  cues with positive time spans. A mere file, header or invalid text is not a
  usable transcript. Numeric spoken text remains valid.
- HTTP import stages the actual uploaded subtitle bytes for preflight, rather
  than an empty presence marker. Valid attached subtitles bypass missing ASR;
  invalid content cannot bypass it. Refused uploads still leave no staged files.
- Unusable imported subtitles are preserved; when ASR is ready, generated text
  goes into project metadata. Missing ASR blocks before model work.
- Empty generated SRT is rejected before resume stamps or analysis. Unexpected
  runtime failures use the existing `subtitle_setup` code, not a silent-source
  assertion. Existing eight-language UI messages and event enums are reused.
- Whisper progress, download/load and transcription propagate stop signals;
  a stop does not trigger VAD/GPU fallback or become a setup failure.

## Evidence and remaining acceptance

Offline regressions cover raw and redacted provider errors, bounded transient
retries, queue stopping, SQLite task results, subtitle persistence/reuse and
Whisper stop behavior. The local framing budget regression is documented in
`FRAMING_BUDGET_REGRESSION.md`. No paid service calls are required by these tests.

Before any release, test the final Windows x64 and macOS arm64 packages with
actual providers and local Whisper: empty attached/platform subtitles, missing
runtime/model, runtime failure, truly silent input, valid spoken input, stop,
shutdown, restart and retry after repair. Verify output playback and preserved
files. Record package hashes and source SHA under `TESTING_ACCEPTANCE.md`.

Telemetry validation must retain the existing coarse error codes and upstream
types through task and generation persistence. No new event/schema/query
denominator is introduced. A stopped run must remain stopped rather than a
provider or no-speech failure; use the existing release validation SQL and
deduplicated attempt contract to verify actual installed-package receipts.
Offline regressions and a source gate do not establish production uplift.
