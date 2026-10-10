-- Shadow QA outcomes. One studio_qa_checked event carries all five checkers.
-- Counts are checker results, not delivered videos.
-- Buckets stay inside the event contract; raw measurements are not stored.
-- distinct_id is the anonymous id already stored for this machine.
-- properties.`$feature/qa_gate_blocking` is the variant assigned to that generation.
SELECT checker, outcome, bucket, count() AS checks
FROM (
  SELECT 'avsync' AS checker, properties.qa_avsync AS outcome, properties.qa_avsync_bucket AS bucket
  FROM events
  WHERE timestamp >= now() - INTERVAL 14 DAY
    AND event = 'studio_qa_checked'
    AND properties.studio_schema_version = 2
    AND properties.qa_mode = 'shadow'
  UNION ALL
  SELECT 'face', properties.qa_face, properties.qa_face_bucket FROM events
  WHERE timestamp >= now() - INTERVAL 14 DAY AND event = 'studio_qa_checked'
    AND properties.studio_schema_version = 2 AND properties.qa_mode = 'shadow'
  UNION ALL
  SELECT 'loudness', properties.qa_loudness, properties.qa_loudness_bucket FROM events
  WHERE timestamp >= now() - INTERVAL 14 DAY AND event = 'studio_qa_checked'
    AND properties.studio_schema_version = 2 AND properties.qa_mode = 'shadow'
  UNION ALL
  SELECT 'jitter', properties.qa_jitter, properties.qa_jitter_bucket FROM events
  WHERE timestamp >= now() - INTERVAL 14 DAY AND event = 'studio_qa_checked'
    AND properties.studio_schema_version = 2 AND properties.qa_mode = 'shadow'
  UNION ALL
  SELECT 'ending', properties.qa_ending, properties.qa_ending_bucket FROM events
  WHERE timestamp >= now() - INTERVAL 14 DAY AND event = 'studio_qa_checked'
    AND properties.studio_schema_version = 2 AND properties.qa_mode = 'shadow'
)
GROUP BY checker, outcome, bucket
ORDER BY checker, checks DESC
