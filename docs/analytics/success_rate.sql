-- 1.5.8 出片成功率（审查副本）。口径见 docs/analytics/TRACKING_PLAN.md §6–§7、§2.3、§4.4。
-- 业务看板只看 production + 目标 app_version。validation 事件不进转化率。
-- {version} 发版后替换为当前正式版，例如 '1.5.8'。
--
-- 查询映射保留（覆盖 1.5.7 及更早）。1.5.8 起生产者只发规范值，映射仍用于历史行：
--   outcome_canon = multiIf(outcome IN ('completed','success'), 'success', outcome IN ('failed','error'), 'error', outcome)
--   os_canon      = multiIf(os IN ('darwin','macos'), 'macos', os IN ('win32','windows'), 'windows', os = 'linux', 'linux', 'unknown')
--   app_version   = coalesce(nullIf(app_version, ''), nullIf(version, ''))
-- provider_test_* → provider_connection_test_*；publish_export_* → studio_export_*。见 §8.2。

-- 图 1 / 图 3：按次出片成功率（可再 breakdown provider）
SELECT
  countIf(multiIf(properties.outcome IN ('completed', 'success'), 'success', properties.outcome IN ('failed', 'error'), 'error', properties.outcome) = 'success') AS completed,
  countIf(
    multiIf(properties.outcome IN ('completed', 'success'), 'success', properties.outcome IN ('failed', 'error'), 'error', properties.outcome) = 'success'
    OR (
      multiIf(properties.outcome IN ('completed', 'success'), 'success', properties.outcome IN ('failed', 'error'), 'error', properties.outcome) IN ('error', 'partial')
      AND coalesce(properties.upstream_error_type, '') NOT IN
          ('invalid_key', 'insufficient_quota', 'permission_denied', 'model_not_found', 'bad_endpoint')
      AND coalesce(properties.error_code, '') NOT IN
          ('llm_not_configured', 'source_too_short', 'source_no_audio', 'source_unreadable',
           'whisper_not_installed', 'source_blocked', 'service_restarted',
           'invalid_key', 'insufficient_quota')
    )
  ) AS qualifying,
  completed / qualifying AS attempt_success_rate
FROM events
WHERE event IN ('studio_generation_finished', 'studio_production_finished')
  AND properties.analytics_environment = 'production'
  AND properties.app_version = {version}
  AND timestamp >= now() - INTERVAL 7 DAY;

-- 图 2：按人首次合格出片成功率
SELECT
  uniqIf(distinct_id, first_outcome = 'success') AS first_success_users,
  uniq(distinct_id) AS qualifying_users,
  first_success_users / qualifying_users AS first_attempt_success_rate
FROM (
  SELECT
    distinct_id,
    argMin(multiIf(properties.outcome IN ('completed', 'success'), 'success', properties.outcome IN ('failed', 'error'), 'error', properties.outcome), timestamp) AS first_outcome
  FROM events
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND properties.analytics_environment = 'production'
    AND properties.app_version = {version}
    AND timestamp >= now() - INTERVAL 7 DAY
    AND (
      multiIf(properties.outcome IN ('completed', 'success'), 'success', properties.outcome IN ('failed', 'error'), 'error', properties.outcome) = 'success'
      OR (
        multiIf(properties.outcome IN ('completed', 'success'), 'success', properties.outcome IN ('failed', 'error'), 'error', properties.outcome) IN ('error', 'partial')
        AND coalesce(properties.upstream_error_type, '') NOT IN
            ('invalid_key', 'insufficient_quota', 'permission_denied', 'model_not_found', 'bad_endpoint')
        AND coalesce(properties.error_code, '') NOT IN
            ('llm_not_configured', 'source_too_short', 'source_no_audio', 'source_unreadable',
             'whisper_not_installed', 'source_blocked', 'service_restarted')
      )
    )
  GROUP BY distinct_id
);

-- 图 4：失败身份（failure_stage × error_code）
SELECT
  properties.failure_stage AS failure_stage,
  properties.error_code AS error_code,
  count() AS events
FROM events
WHERE event IN ('studio_generation_finished', 'studio_production_finished')
  AND properties.analytics_environment = 'production'
  AND properties.app_version = {version}
  AND multiIf(properties.outcome IN ('completed', 'success'), 'success', properties.outcome IN ('failed', 'error'), 'error', properties.outcome) IN ('error', 'partial')
  AND timestamp >= now() - INTERVAL 7 DAY
GROUP BY failure_stage, error_code
ORDER BY events DESC;

-- 图 5：模型请求上游错误（诊断，不是 6.1 分母）
SELECT
  properties.provider AS provider,
  properties.upstream_error_type AS upstream_error_type,
  count() AS events
FROM events
WHERE event = 'llm_request_finished'
  AND properties.analytics_environment = 'production'
  AND properties.app_version = {version}
  AND properties.outcome = 'error'
  AND timestamp >= now() - INTERVAL 7 DAY
GROUP BY provider, upstream_error_type
ORDER BY events DESC;
