-- Duration is backend execution time only; null/missing values are excluded by avg.
SELECT event, properties.outcome AS outcome, properties.error_code AS error_code,
       properties.analysis_mode AS analysis_mode,
       count() AS events, uniq(distinct_id) AS devices,
       avg(toFloat(properties.duration_ms)) AS avg_duration_ms,
       sum(toFloat(properties.succeeded_count)) AS succeeded_goals,
       sum(toFloat(properties.failed_count)) AS failed_goals,
       sum(toFloat(properties.result_count)) AS outputs
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.studio_schema_version = 1
  AND properties.analytics_environment = 'production'
  AND event IN ('studio_screen_finished', 'studio_production_finished',
    'studio_export_finished', 'studio_download_saved', 'studio_download_failed', 'social_publish_finished')
GROUP BY event, outcome, error_code, analysis_mode
ORDER BY events DESC LIMIT 100
