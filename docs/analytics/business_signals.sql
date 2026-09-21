-- UI-observed V2 signals. Empty results before rollout are expected.
-- Arrival time; not a completed cohort, task success rate, or customer satisfaction.
SELECT event,
       toString(properties.outcome) AS outcome,
       toString(properties.artifact_type) AS artifact_type,
       count() AS event_count,
       uniq(distinct_id) AS devices,
       uniqIf(toString(properties.task_id), isNotNull(properties.task_id)) AS tasks
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND toString(properties.schema_version) = '2'
  AND properties.analytics_environment = 'production'
  AND event IN ('import_requested', 'import_accepted', 'import_request_failed',
                'import_finished', 'processing_task_observed', 'processing_finished',
                'processing_request_failed', 'provider_test_finished',
                'publish_export_finished', 'publish_export_request_failed',
                'media_download_received', 'media_download_request_failed')
GROUP BY event, outcome, artifact_type
ORDER BY event, outcome, artifact_type
