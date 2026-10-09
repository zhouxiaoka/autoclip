-- Result cards. Counts and enums only; no titles, captions or reasons.
SELECT
  event,
  properties.share_target AS share_target,
  properties.artifact_type AS artifact_type,
  count() AS events
FROM events
WHERE timestamp > now() - INTERVAL 14 DAY
  AND event IN (
    'studio_output_shared',
    'studio_download_requested',
    'studio_download_saved',
    'studio_download_failed',
    'studio_first_clip_ready',
    'studio_output_rated',
    'studio_variant_produce_requested'
  )
GROUP BY event, share_target, artifact_type
ORDER BY events DESC
