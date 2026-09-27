SELECT event, properties.analytics_environment AS environment,
       properties.app_version AS app_version, properties.outcome AS outcome,
       properties.error_code AS error_code, count() AS events, uniq(distinct_id) AS devices
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.studio_schema_version = 1
  AND properties.analytics_environment = 'validation'
GROUP BY event, environment, app_version, outcome, error_code
ORDER BY event LIMIT 100
