-- Validation only. Replace VERSION_UNDER_TEST with the candidate's app version.
-- Event rows, unique devices and unique flows are separate; do not infer installs/users.
-- Startup regression: check the first screen as well as launch events on a fresh
-- validation session. Desktop arch must be aarch64 (Mac arm64) / x86_64 (Win x64).
SELECT event, properties.os AS os, properties.arch AS arch,
       count() AS events, uniq(distinct_id) AS devices,
       countIf(properties.os IS NULL OR toString(properties.os) = '') AS missing_os,
       countIf(properties.arch IS NULL OR toString(properties.arch) = '') AS missing_arch
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.analytics_environment = 'validation'
  AND properties.app_version = 'VERSION_UNDER_TEST'
  AND properties.runtime = 'desktop'
  AND event IN ('$pageview', 'setup_presented', 'app_installed', 'app_opened', 'app_updated')
GROUP BY event, os, arch
ORDER BY event, os, arch;

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
  AND properties.outcome = 'error';

-- 1.5.7 成功率埋点：失败必带阶段；按服务商拆分用 run 级 provider，不用设置页最后保存值。
-- R27 #415 I422：按 attribution_source 拆。local = 非模型归因，统计责任仍按错误码判断（如 source_blocked 照旧剔除）；local 时 provider 置空，
-- 只表示"用过这个连接"，不算这个服务商失败；request/phase 才按服务商看。
SELECT event, properties.attribution_source AS attribution_source,
       if(toString(properties.attribution_source) = 'local', NULL, properties.provider) AS provider,
       properties.upstream_error_type AS upstream_error_type,
       properties.failure_stage AS failure_stage, properties.outcome AS outcome,
       count() AS events,
       countIf(properties.error_code IS NULL OR toString(properties.error_code) = '') AS missing_error_code,
       countIf(properties.failure_stage IS NULL OR toString(properties.failure_stage) = '') AS missing_failure_stage,
       avg(properties.billable_calls_before_failure) AS avg_billable_before_failure,
       avg(properties.degrade_count) AS avg_degrade_count,
       countIf(properties.degrade_count > 0) AS events_with_degrade
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.analytics_environment = 'validation'
  AND properties.app_version = 'VERSION_UNDER_TEST'
  AND event IN ('studio_generation_finished', 'studio_production_finished', 'llm_request_finished',
                'asr_readiness_checked', 'provider_validation_finished')
GROUP BY event, attribution_source, provider, upstream_error_type, failure_stage, outcome
ORDER BY event, events DESC;

-- S5: AUTO vision degradation uses a fixed code, never free-text reasons.
SELECT event, properties.degrade_reason AS degrade_reason,
       properties.analysis_mode AS analysis_mode, properties.route AS route,
       properties.outcome AS outcome, count() AS events, uniq(distinct_id) AS devices
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.analytics_environment = 'validation'
  AND properties.app_version = 'VERSION_UNDER_TEST'
  AND event IN ('studio_screen_finished', 'studio_generation_finished')
  AND properties.degrade_reason = 'vision_unavailable_subtitle_fallback'
GROUP BY event, degrade_reason, analysis_mode, route, outcome
ORDER BY event, outcome;
