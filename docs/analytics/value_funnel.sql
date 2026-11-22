-- AutoClip Product Value Funnel (PostHog HogQL, v4 hygiene)
-- End-to-end value loop: 导入 -> 首片出片成功 -> 播放成片 -> 下载保存 -> 7日复剪
--
-- Required variables (matching success_rate.sql):
--   {date_from}         inclusive UTC start, e.g. '2026-11-01 00:00:00'
--   {date_to}           exclusive UTC end,   e.g. '2026-12-01 00:00:00'
--   {internal_cohort_id} PostHog internal/QA cohort ID (project 450605: 641509)
--   {release_1_5_7}     1.5.7 public release UTC timestamp
--   {release_1_5_8}     1.5.8 public release UTC timestamp
--   {release_1_5_9}     1.5.9 public release UTC timestamp ('' excludes pre-release QA)

-- ============================================================================
-- Panel 1: 端到端产品价值漏斗（按设备 / person_id）
-- 导入受理 -> 首片出片成功 -> 播放成片 -> 下载保存 -> 7日复剪
-- ============================================================================
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
  UNION ALL SELECT '1.5.8', {release_1_5_8}
  UNION ALL SELECT '1.5.9', {release_1_5_9}
),
base AS (
  SELECT
    e.person_id AS person_id,
    e.event AS event,
    e.timestamp AS ts,
    toString(e.properties.app_version) AS app_version,
    toString(e.properties.outcome) AS outcome,
    toString(e.properties.provider) AS provider,
    toString(e.properties.artifact_type) AS artifact_type,
    toFloat64OrNull(toString(e.properties.duration_ms)) AS duration_ms
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
      'studio_import_accepted',
      'studio_generation_finished',
      'studio_production_finished',
      'studio_output_played',
      'studio_download_saved',
      'studio_export_finished'
    )
),
per_person AS (
  SELECT
    person_id,
    minIf(ts, event = 'studio_import_accepted') AS first_import_at,
    minIf(
      ts,
      event IN ('studio_generation_finished', 'studio_production_finished')
      AND outcome IN ('completed', 'success')
    ) AS first_success_at,
    minIf(ts, event = 'studio_output_played') AS first_play_at,
    minIf(ts, event = 'studio_download_saved') AS first_download_at
  FROM base
  GROUP BY person_id
),
repeat_7d AS (
  SELECT
    p.person_id AS person_id,
    countIf(
      b.event IN ('studio_import_accepted', 'studio_generation_finished', 'studio_export_finished')
      AND b.ts > p.first_success_at + INTERVAL 1 HOUR
      AND b.ts <= p.first_success_at + INTERVAL 7 DAY
    ) > 0 AS returned_7d
  FROM per_person p
  LEFT JOIN base b ON b.person_id = p.person_id
  WHERE p.first_success_at IS NOT NULL
  GROUP BY p.person_id
)
SELECT
  countIf(p.first_import_at IS NOT NULL) AS imported_people,
  countIf(p.first_success_at IS NOT NULL) AS succeeded_people,
  countIf(p.first_success_at IS NOT NULL AND p.first_play_at >= p.first_success_at) AS played_people,
  countIf(p.first_success_at IS NOT NULL AND p.first_download_at >= p.first_success_at) AS downloaded_people,
  countIf(r.returned_7d = 1) AS repeat_7d_people,
  round(100.0 * countIf(p.first_success_at IS NOT NULL) / nullIf(countIf(p.first_import_at IS NOT NULL), 0), 1) AS import_to_success_pct,
  round(100.0 * countIf(p.first_success_at IS NOT NULL AND p.first_play_at >= p.first_success_at) / nullIf(countIf(p.first_success_at IS NOT NULL), 0), 1) AS success_to_play_pct,
  round(100.0 * countIf(p.first_success_at IS NOT NULL AND p.first_download_at >= p.first_success_at) / nullIf(countIf(p.first_success_at IS NOT NULL), 0), 1) AS success_to_download_pct,
  round(100.0 * countIf(r.returned_7d = 1) / nullIf(countIf(p.first_success_at IS NOT NULL), 0), 1) AS success_to_repeat_7d_pct
FROM per_person p
LEFT JOIN repeat_7d r ON r.person_id = p.person_id;

-- ============================================================================
-- Panel 2: 首片成功 -> 下载保存 & 7日复剪（按服务商拆解，验证 DeepSeek / 百炼 优先策略）
-- ============================================================================
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
  UNION ALL SELECT '1.5.8', {release_1_5_8}
  UNION ALL SELECT '1.5.9', {release_1_5_9}
),
base AS (
  SELECT
    e.person_id AS person_id,
    e.event AS event,
    e.timestamp AS ts,
    toString(e.properties.outcome) AS outcome,
    coalesce(nullIf(toString(e.properties.provider), ''), 'unknown') AS provider,
    toFloat64OrNull(toString(e.properties.duration_ms)) AS duration_ms
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
      'studio_generation_finished',
      'studio_production_finished',
      'studio_download_saved',
      'studio_import_accepted',
      'studio_export_finished'
    )
),
first_win AS (
  SELECT
    person_id,
    argMin(provider, ts) AS first_provider,
    min(ts) AS first_success_at,
    argMin(duration_ms, ts) AS first_duration_ms
  FROM base
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND outcome IN ('completed', 'success')
  GROUP BY person_id
)
SELECT
  w.first_provider AS provider,
  count() AS succeeded_people,
  round(quantileExact(0.5)(w.first_duration_ms) / 60000.0, 2) AS p50_minutes,
  countIf(
    exists(
      SELECT 1 FROM base b
      WHERE b.person_id = w.person_id
        AND b.event = 'studio_download_saved'
        AND b.ts >= w.first_success_at
    )
  ) AS downloaded_people,
  countIf(
    exists(
      SELECT 1 FROM base b
      WHERE b.person_id = w.person_id
        AND b.event IN ('studio_import_accepted', 'studio_generation_finished', 'studio_export_finished')
        AND b.ts > w.first_success_at + INTERVAL 1 HOUR
        AND b.ts <= w.first_success_at + INTERVAL 7 DAY
    )
  ) AS repeat_7d_people
FROM first_win w
GROUP BY w.first_provider
ORDER BY succeeded_people DESC;

-- ============================================================================
-- Panel 3: 结果页交付动作分布（播放 / 下载成片 / 下载发布包 / 复制文案 / 评分）
-- ============================================================================
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
  UNION ALL SELECT '1.5.8', {release_1_5_8}
  UNION ALL SELECT '1.5.9', {release_1_5_9}
)
SELECT
  e.event AS event,
  coalesce(nullIf(toString(e.properties.artifact_type), ''), 'none') AS artifact_type,
  coalesce(nullIf(toString(e.properties.share_target), ''), 'none') AS share_target,
  count() AS events,
  uniqExact(e.person_id) AS unique_people
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
    'studio_download_saved',
    'studio_download_failed',
    'studio_output_shared',
    'studio_output_rated'
  )
GROUP BY event, artifact_type, share_target
ORDER BY events DESC;
