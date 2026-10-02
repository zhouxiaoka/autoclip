-- Saved dashboard 02/03/04 query contracts. No production event rows or identifiers.
-- Separate events, devices, nonempty flows and nonempty artifacts.
-- Devices are not people/installs; variant attribute sums are not distinct files.

-- 02: automatic generation, manual export, native saves and publishing.
SELECT properties.app_version AS app_version,
       properties.material_origin AS material_origin, event,
       properties.outcome AS outcome, properties.runtime AS runtime,
       count() AS events, uniq(distinct_id) AS devices,
       uniqIf(tuple(distinct_id, toString(properties.flow_id)),
              properties.flow_id IS NOT NULL AND toString(properties.flow_id) != '') AS flows,
       uniqIf(tuple(distinct_id, toString(properties.artifact_id)),
              properties.artifact_id IS NOT NULL AND toString(properties.artifact_id) != '') AS artifacts
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.studio_schema_version = 2
  AND properties.analytics_environment = 'production'
  AND properties.material_origin IN ('sample','user','unknown')
  AND ((event = 'studio_generation_finished' AND properties.outcome IN ('completed','partial'))
       OR (properties.artifact_id IS NOT NULL AND
           (event = 'studio_download_saved' OR
            (event IN ('studio_export_finished','social_publish_finished') AND properties.outcome = 'completed'))))
GROUP BY app_version,material_origin,event,outcome,runtime
ORDER BY devices DESC;

-- 03: terminal results and failures. Historical missing error codes remain missing.
SELECT properties.app_version AS app_version,
       properties.material_origin AS material_origin, event,
       properties.outcome AS outcome, properties.error_code AS error_code,
       properties.analysis_mode AS analysis_mode,
       count() AS events, uniq(distinct_id) AS devices,
       uniqIf(tuple(distinct_id, toString(properties.flow_id)),
              properties.flow_id IS NOT NULL AND toString(properties.flow_id) != '') AS flows,
       avg(toFloat(properties.duration_ms)) AS avg_duration_ms,
       sum(toFloat(properties.result_count)) AS result_count_sum,
       sum(toFloat(properties.variant_count)) AS variant_count_sum
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.studio_schema_version = 2
  AND properties.analytics_environment = 'production'
  AND event IN ('studio_generation_finished','studio_screen_finished','studio_production_finished',
                'studio_export_finished','studio_download_failed','social_publish_finished')
GROUP BY app_version,material_origin,event,outcome,error_code,analysis_mode
ORDER BY events DESC LIMIT 100;

-- 04: a mature observed sample-device cohort, not installation conversion.
WITH sample_cohort AS (
    SELECT distinct_id, min(timestamp) AS sample_at FROM events
    WHERE event = 'example_project_viewed' AND properties.experience_schema_version = 1
      AND properties.analytics_environment = 'production'
      AND timestamp >= now() - INTERVAL 14 DAY AND timestamp < now() - INTERVAL 7 DAY
    GROUP BY distinct_id
), real_renders AS (
    SELECT distinct_id, timestamp AS rendered_at FROM events
    WHERE event IN ('studio_export_finished','studio_generation_finished')
      AND properties.studio_schema_version = 2 AND properties.analytics_environment = 'production'
      AND properties.material_origin = 'user'
      AND (properties.outcome = 'completed' OR
           (event = 'studio_generation_finished' AND properties.outcome = 'partial'
            AND toFloat(properties.completed_variant_count) > 0))
      AND timestamp >= now() - INTERVAL 14 DAY
)
SELECT uniq(s.distinct_id) AS observed_sample_devices,
       uniqIf(s.distinct_id, r.rendered_at > s.sample_at AND r.rendered_at <= s.sample_at + INTERVAL 7 DAY)
           AS real_render_within_7d_devices
FROM sample_cohort s LEFT JOIN real_renders r ON s.distinct_id = r.distinct_id;
