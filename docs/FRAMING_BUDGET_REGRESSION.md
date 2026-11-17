# Local framing / model budget regression

The production job shares a 1,200-second model-request budget. Local Whisper and
encoding pause that clock; speaker detection previously did not. After 1,000
seconds of model work, 300 seconds of local detection exhausted the clock and
the following packaging/model call raised `JobDurationExceeded`, even when
detection safely fell back to the full frame.

`backend/tests/test_framing_job_budget.py` reproduces the boundary using a
controlled clock, without real provider calls. It covers successful scanning,
detector failure/fallback, the install wait's independent deadline, remaining
provider timeout, and an already expired job. These are offline regressions,
not evidence of installed-package acceptance or a measured production uplift.

Before release, run the installed Windows x64 and macOS arm64 packages with
portrait output and a slow local scan. Record the actual model-stage time,
framing duration, subsequent request timeout, package hashes and source SHA.
Verify the output plays, detector fallback preserves the frame, and a genuinely
exhausted model budget still stops the job. Include this regression in
`failure_recovery` and `output_delivery`; retain the existing test and release
requirements in `TESTING_ACCEPTANCE.md`.
