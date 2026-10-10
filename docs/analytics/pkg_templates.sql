-- pkg_templates_v1. Enums and counts only. Compare the flag with $feature/pkg_templates_v1 once PostHog is sending it.
-- Generation success.
SELECT properties.outcome AS outcome, count() AS events
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND event = 'studio_generation_finished'
  AND properties.studio_schema_version = 2
  AND properties.analytics_environment = 'production'
GROUP BY outcome
ORDER BY events DESC;

-- Render duration inputs for p90. Bucket in the dashboard; do not average titles or paths (they are not on the event).
SELECT properties.template AS template, properties.encoder AS encoder,
       properties.downgrade_reason AS downgrade_reason, properties.os AS os,
       properties.outcome AS outcome, properties.failure_reason AS failure_reason,
       quantile(0.9)(properties.duration_ms) AS render_p90_ms, count() AS events
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND event = 'studio_template_render_finished'
  AND properties.studio_schema_version = 2
GROUP BY template, encoder, downgrade_reason, os, outcome, failure_reason
ORDER BY events DESC
LIMIT 100;

-- Override rate: overridden flows over flows that recorded a template choice.
SELECT properties.from_template AS from_template, properties.to_template AS to_template,
       properties.stage AS stage, count() AS events
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND event = 'studio_template_overridden'
  AND properties.studio_schema_version = 2
GROUP BY from_template, to_template, stage
ORDER BY events DESC;

-- Download and copy, split by template.
SELECT event, properties.template AS template, properties.artifact_type AS artifact_type,
       properties.share_target AS share_target, count() AS events
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND event IN ('studio_download_saved', 'studio_download_requested', 'studio_output_shared')
  AND properties.studio_schema_version = 2
GROUP BY event, template, artifact_type, share_target
ORDER BY events DESC
LIMIT 100;
