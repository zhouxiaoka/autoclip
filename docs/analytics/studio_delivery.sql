-- Observed successful delivery signals. Device counts are not people or downloads.
-- Render completion, native save and confirmed social publish remain separate.
-- Browser download_requested is deliberately excluded: disk writes are unobservable.
SELECT properties.material_origin AS material_origin,
       event, properties.runtime AS runtime,
       uniq(distinct_id) AS devices,
       uniq(tuple(distinct_id, properties.flow_id)) AS flows,
       uniq(tuple(distinct_id, properties.artifact_id)) AS artifacts
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.studio_schema_version = 2
  AND properties.analytics_environment = 'production'
  AND properties.material_origin IN ('sample', 'user', 'unknown')
  AND properties.artifact_id IS NOT NULL
  AND (event = 'studio_download_saved'
       OR (event IN ('studio_export_finished', 'social_publish_finished')
           AND properties.outcome = 'completed'))
GROUP BY material_origin, event, runtime
ORDER BY devices DESC
