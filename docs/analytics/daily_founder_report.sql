-- AutoClip founder daily report. UTC calendar day.
-- Official numbers: 1.5 from-app bugs, first real clip vs sample, 1.5.0 Windows/Mac DAU.
-- Rolling windows here match the PostHog dashboard. The script substitutes explicit day bounds.

-- ① 14-day from-app bugs. Only version_group=1.5 is metric 1.
SELECT
    toString(toDate(timestamp)) AS day,
    if(match(toString(properties.app_version), '^1\\.5'), '1.5', 'older') AS version_group,
    uniq(toString(properties.feedback_id)) AS bug_reports
FROM events
WHERE timestamp >= now() - INTERVAL 14 DAY
  AND event = 'feedback_submitted'
  AND properties.category = 'bug'
  AND toString(properties.feedback_id) != ''
GROUP BY day, version_group
ORDER BY day ASC

-- ② First completed delivery per device, last 14 days of first-success dates.
-- Lookback is 35 days so "first" is not truncated to the chart window.
WITH deliveries AS (
    SELECT person_id, timestamp, properties.material_origin AS origin
    FROM events
    WHERE timestamp >= now() - INTERVAL 35 DAY
      AND timestamp < now()
      AND toString(properties.analytics_environment) = 'production'
      AND properties.material_origin IN ('user', 'sample')
      AND (
          event = 'studio_download_saved'
          OR (
              event IN ('studio_export_finished', 'studio_generation_finished')
              AND properties.outcome = 'completed'
          )
      )
),
firsts AS (
    SELECT
        person_id,
        argMin(origin, timestamp) AS first_origin,
        min(timestamp) AS first_at
    FROM deliveries
    GROUP BY person_id
)
SELECT
    toString(toDate(first_at)) AS day,
    first_origin,
    uniq(person_id) AS first_devices
FROM firsts
WHERE first_at >= now() - INTERVAL 14 DAY
GROUP BY day, first_origin
ORDER BY day ASC

-- ③ 1.5.0 production DAU by os.
SELECT
    toString(toDate(timestamp)) AS day,
    toString(properties.os) AS os,
    uniq(person_id) AS devices
FROM events
WHERE timestamp >= now() - INTERVAL 14 DAY
  AND event = 'app_opened'
  AND toString(properties.analytics_environment) = 'production'
  AND toString(properties.app_version) = '1.5.0'
  AND properties.os IN ('windows', 'macos')
GROUP BY day, os
ORDER BY day ASC
