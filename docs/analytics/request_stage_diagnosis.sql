-- 请求级耗时诊断；这是请求数，不是出片 attempt 分母。
-- 必须固定版本和 UTC 窗口。安装验收将 environment 设置为 validation，不能混入 production。
-- 旧版本的 other / render 不回填；无 attempt ID 时，不按设备+时间窗口推断精确任务归属。
SELECT
  toString(properties.app_version) AS app_version,
  toString(properties.provider) AS provider,
  toString(properties.model) AS model,
  coalesce(nullIf(toString(properties.stage), ''), '(missing)') AS request_stage,
  toString(properties.outcome) AS outcome,
  count() AS requests,
  round(avg(toFloat(properties.duration_ms)) / 1000, 2) AS avg_seconds,
  round(max(toFloat(properties.duration_ms)) / 1000, 2) AS max_seconds
FROM events
WHERE event = 'llm_request_finished'
  AND toString(properties.app_version) = {app_version}
  AND toString(properties.analytics_environment) = {environment}
  AND toString(properties.runtime) = 'desktop'
  AND timestamp >= toDateTime({date_from}, 'UTC')
  AND timestamp < toDateTime({date_to}, 'UTC')
GROUP BY app_version, provider, model, request_stage, outcome
ORDER BY requests DESC;
