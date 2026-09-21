-- Rolling 7-day coverage audit, including legacy/development events intentionally.
SELECT event,
       toString(properties.schema_version) AS schema_version,
       toString(properties.analytics_environment) AS environment,
       toString(properties.app_version) AS app_version,
       count() AS event_count, uniq(distinct_id) AS devices
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY AND event NOT LIKE '$%'
GROUP BY event, schema_version, environment, app_version
ORDER BY event_count DESC LIMIT 100
