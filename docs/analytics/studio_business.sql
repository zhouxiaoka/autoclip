-- Event/device signals, not a task-correlated funnel. Legacy schema is excluded.
SELECT event, properties.analytics_environment AS environment,
       properties.app_version AS app_version, properties.runtime AS runtime,
       properties.outcome AS outcome, properties.analysis_mode AS analysis_mode,
       count() AS events, uniq(distinct_id) AS devices
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.studio_schema_version = 1
  AND properties.analytics_environment = 'production'
GROUP BY event, environment, app_version, runtime, outcome, analysis_mode
ORDER BY events DESC LIMIT 100
