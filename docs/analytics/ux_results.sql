-- Result cards. Counts and enums only; no titles, captions or reasons.
-- Production desktop cohort-filtered window matching success_rate.sql.
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
  UNION ALL SELECT '1.5.8', {release_1_5_8}
  UNION ALL SELECT '1.5.9', {release_1_5_9}
)
SELECT
  e.event AS event,
  e.properties.share_target AS share_target,
  e.properties.artifact_type AS artifact_type,
  count() AS events
FROM events e
LEFT JOIN version_releases vr ON toString(e.properties.app_version) = vr.app_version
WHERE toString(e.properties.analytics_environment) = 'production'
  AND toString(e.properties.runtime) = 'desktop'
  AND e.timestamp >= toDateTime({date_from}, 'UTC')
  AND e.timestamp < toDateTime({date_to}, 'UTC')
  AND e.person_id NOT IN COHORT {internal_cohort_id}
  AND (
    vr.app_version IS NULL
    OR vr.app_version = ''
    OR (vr.released_at_text != '' AND e.timestamp >= toDateTime(nullIf(vr.released_at_text, ''), 'UTC'))
  )
  AND e.event IN (
    'studio_output_played',
    'studio_output_shared',
    'studio_download_requested',
    'studio_download_saved',
    'studio_download_failed',
    'studio_first_clip_ready',
    'studio_output_rated',
    'studio_variant_produce_requested'
  )
GROUP BY event, share_target, artifact_type
ORDER BY events DESC
