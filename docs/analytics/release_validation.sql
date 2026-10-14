-- Validation only. Replace VERSION_UNDER_TEST with the candidate's app version.
-- Event rows, unique devices and unique flows are separate; do not infer installs/users.
SELECT event, properties.outcome AS outcome, properties.error_code AS error_code,
       count() AS events, uniq(distinct_id) AS devices,
       countIf(properties.flow_id IS NULL OR toString(properties.flow_id) = '') AS missing_flow_events,
       uniqIf(tuple(distinct_id, toString(properties.flow_id)),
              properties.flow_id IS NOT NULL AND toString(properties.flow_id) != '') AS observed_flows
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.analytics_environment = 'validation'
  AND properties.app_version = 'VERSION_UNDER_TEST'
  AND properties.material_origin = 'user'
  AND event IN ('studio_generation_finished', 'studio_export_finished',
                'studio_download_saved', 'studio_download_failed')
GROUP BY event, outcome, error_code
ORDER BY event, outcome;

-- Run separately: missing failure codes are a coverage defect, never a cause category.
SELECT count() AS failed_events,
       countIf(properties.error_code IS NULL OR toString(properties.error_code) = '') AS missing_error_code,
       uniq(distinct_id) AS devices
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.analytics_environment = 'validation'
  AND properties.app_version = 'VERSION_UNDER_TEST'
  AND event = 'studio_generation_finished'
  AND properties.outcome = 'failed';

-- 1.5.8 成功率埋点：失败必带阶段；按服务商拆分用 run 级 provider，不用设置页最后保存值。
SELECT event, properties.provider AS provider, properties.upstream_error_type AS upstream_error_type,
       properties.failure_stage AS failure_stage, properties.outcome AS outcome,
       count() AS events,
       countIf(properties.error_code IS NULL OR toString(properties.error_code) = '') AS missing_error_code,
       countIf(properties.failure_stage IS NULL OR toString(properties.failure_stage) = '') AS missing_failure_stage,
       avg(properties.billable_calls_before_failure) AS avg_billable_before_failure
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.analytics_environment = 'validation'
  AND properties.app_version = 'VERSION_UNDER_TEST'
  AND event IN ('studio_generation_finished', 'studio_production_finished', 'llm_request_finished',
                'asr_readiness_checked', 'provider_validation_finished')
GROUP BY event, provider, upstream_error_type, failure_stage, outcome
ORDER BY event, events DESC;
