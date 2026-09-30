-- Mature 7-day follow-up for devices observed viewing a sample 7–14 days ago.
-- This is NOT an install cohort, first-ever sample cohort, or a causal experiment.
-- Render success is the endpoint here; it does not establish disk save or satisfaction.
WITH sample_cohort AS (
    SELECT distinct_id, min(timestamp) AS sample_at
    FROM events
    WHERE event = 'example_project_viewed'
      AND properties.experience_schema_version = 1
      AND properties.analytics_environment = 'production'
      AND timestamp >= now() - INTERVAL 14 DAY
      AND timestamp < now() - INTERVAL 7 DAY
    GROUP BY distinct_id
), real_renders AS (
    SELECT distinct_id, timestamp AS rendered_at
    FROM events
    WHERE event = 'studio_export_finished'
      AND properties.studio_schema_version = 2
      AND properties.analytics_environment = 'production'
      AND properties.material_origin = 'user'
      AND properties.outcome = 'completed'
      AND timestamp >= now() - INTERVAL 14 DAY
)
SELECT uniq(s.distinct_id) AS observed_sample_devices,
       uniqIf(s.distinct_id, r.rendered_at > s.sample_at
           AND r.rendered_at <= s.sample_at + INTERVAL 7 DAY) AS real_render_within_7d_devices
FROM sample_cohort s
LEFT JOIN real_renders r ON s.distinct_id = r.distinct_id
