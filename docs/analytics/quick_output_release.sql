-- 1.5 additive fields; null means unknown. Browser requested is not disk delivery.
SELECT event, properties.app_version AS version, properties.material_origin AS material_origin,
       properties.outcome AS outcome, properties.portrait_style AS portrait_style,
       properties.artifact_type AS artifact_type, properties.template AS template,
       count() AS events, uniq(distinct_id) AS devices,
       sum(toFloat(properties.completed_variant_count)) AS completed_variants,
       sum(toFloat(properties.outro_applied_count)) AS outro_applied,
       sum(toFloat(properties.outro_fallback_count)) AS outro_fallback,
       sum(toFloat(properties.outro_unknown_count)) AS outro_unknown,
       sum(toFloat(properties.framing_pending_count)) AS framing_pending
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.analytics_environment = 'production'
  AND properties.studio_schema_version = 2
  AND event IN ('studio_import_accepted', 'studio_generation_finished', 'studio_variant_finished',
                'studio_cover_redesign_finished', 'studio_post_save_accepted',
                'studio_download_requested', 'studio_download_saved', 'studio_download_failed')
GROUP BY event, version, material_origin, outcome, portrait_style, artifact_type, template
ORDER BY event, events DESC LIMIT 200
