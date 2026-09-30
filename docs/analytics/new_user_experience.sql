-- Diagnostic stage counts, NOT a conversion funnel. Production only; last 7 days.
-- An absent terminal can mean superseded discovery, app exit or telemetry loss.
SELECT event, properties.placement AS placement,
       properties.section AS section, properties.provider AS provider,
       properties.trigger AS trigger, properties.outcome AS outcome,
       properties.material_origin AS material_origin,
       count() AS events, uniq(distinct_id) AS devices,
       avg(toFloat(properties.duration_ms)) AS avg_duration_ms
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.experience_schema_version = 1
  AND properties.analytics_environment = 'production'
GROUP BY event, placement, section, provider, trigger, outcome, material_origin
ORDER BY events DESC LIMIT 200
