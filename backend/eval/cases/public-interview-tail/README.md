# Public interview tail recovery

Source: the repository's `backend/assets/example/source.mp4` and `source.srt` (first 90 seconds). `input.srt` retains original absolute cue timestamps from its last 30 seconds.

The eight-second candidate in `timeline.json` is a deliberately supplied regression input, not a recorded model response. Compare main `48a94357` (forward-only extension drops this tail) with the repaired refinement (adjacent earlier cues meet the existing 20-second minimum). This checks deterministic boundary recovery, not semantic/editorial quality or the separate 5/60-minute acceptance in #116.
