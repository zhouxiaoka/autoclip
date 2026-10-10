-- Shadow QA outcomes. Counts are checker results, not delivered videos.
-- Buckets stay inside the event contract; raw measurements are not stored.
SELECT properties.qa_checker AS checker,
       properties.qa_outcome AS outcome,
       properties.qa_bucket AS bucket,
       count() AS checks,
       quantile(0.9)(properties.duration_ms) AS duration_ms_p90
FROM events
WHERE timestamp >= now() - INTERVAL 14 DAY
  AND event = 'studio_qa_checked'
  AND properties.studio_schema_version = 2
  AND properties.qa_mode = 'shadow'
GROUP BY checker, outcome, bucket
ORDER BY checker, checks DESC
