-- 并行稳定性口径（剔除用户主动退出 user_quit 的按日产品成功率）。
-- 本文件为官方 v4 口径（docs/analytics/success_rate.sql，图 1–图 10）的独立并行观测查询，不修改官方 v4 口径。
-- 仅在产品口径 user_x 的基础上额外剔除 error_code = 'service_restarted' 且 restart_reason = 'user_quit'；
-- crash / update / unknown 引起的 service_restarted 仍严格计入产品失败。
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
  UNION ALL
  SELECT '1.5.8' AS app_version, {release_1_5_8} AS released_at_text
  UNION ALL
  SELECT '1.5.9' AS app_version, {release_1_5_9} AS released_at_text
), base AS (
  SELECT
    toString(coalesce(properties.attempt_id, toString(uuid))) AS aid,
    argMax(toString(coalesce(properties.flow_id, properties.attempt_id, toString(uuid))), timestamp) AS fid,
    max(timestamp) AS ts,
    max(toInt(properties.attempt_sequence)) AS seq,
    argMax(toString(properties.outcome), timestamp) AS o_raw,
    argMax(coalesce(toString(properties.error_code), ''), timestamp) AS ec,
    argMax(coalesce(toString(properties.upstream_error_type), ''), timestamp) AS ue,
    argMax(coalesce(toString(properties.restart_reason), ''), timestamp) AS rr,
    argMax(coalesce(toString(properties.retry_of), ''), timestamp) AS rof
  FROM events
  LEFT JOIN version_releases vr ON vr.app_version = toString(properties.app_version)
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND toString(properties.analytics_environment) = 'production'
    AND toString(properties.runtime) = 'desktop'
    AND timestamp >= toDateTime({date_from}, 'UTC')
    AND timestamp < toDateTime({date_to}, 'UTC')
    AND person_id NOT IN COHORT {internal_cohort_id}
    AND (vr.app_version IS NULL OR vr.app_version = '' OR (vr.released_at_text != '' AND timestamp >= toDateTime(nullIf(vr.released_at_text, ''), 'UTC')))
  GROUP BY aid
), chained AS (
  SELECT b.*,
    multiIf(p4.aid != '', p4.fid, p3.aid != '', p3.fid, p2.aid != '', p2.fid, p1.aid != '', p1.fid, b.fid) AS chain_fid,
    multiIf(r.retried != '', 0, 1) AS leaf
  FROM base b
  LEFT JOIN base p1 ON b.rof = p1.aid
  LEFT JOIN base p2 ON p1.rof = p2.aid
  LEFT JOIN base p3 ON p2.rof = p3.aid
  LEFT JOIN base p4 ON p3.rof = p4.aid
  LEFT JOIN (SELECT DISTINCT rof AS retried FROM base WHERE rof != '') r ON r.retried = b.aid
), c AS (
  SELECT *,
    multiIf(o_raw IN ('completed', 'success'), 'success', o_raw = 'partial', 'partial', o_raw IN ('cancelled', 'canceled'), 'cancelled', 'error') AS o,
    (o = 'cancelled'
      OR ec IN ('authentication', 'llm_auth_invalid', 'invalid_key', 'insufficient_quota', 'llm_not_configured', 'cancelled', 'user_cancelled')
      OR ue IN ('invalid_key', 'insufficient_quota', 'permission_denied')) AS user_hard,
    (user_hard OR ec IN ('connection', 'source_too_short', 'source_no_audio', 'source_unreadable', 'source_blocked', 'source_not_found', 'source_unsupported')) AS user_x,
    (user_x OR (ec = 'service_restarted' AND rr = 'user_quit')) AS stability_x,
    (o = 'success' OR NOT user_x) AS qual_prod,
    (o = 'success' OR NOT stability_x) AS qual_stability,
    (ifNull(seq, 0), leaf, ts) AS ord
  FROM chained
), flows AS (
  SELECT chain_fid AS fid, max(ts) AS fts, argMax(o, ord) AS fo, argMax(qual_prod, ord) AS fq_prod,
    argMax(qual_stability, ord) AS fq_stability,
    (countIf(seq IS NOT NULL) = 0 AND sum(leaf) > 1) AS unknown
  FROM c GROUP BY chain_fid
), d1 AS (
  SELECT toDate(ts) AS d, countIf(o = 'success') AS ok, countIf(qual_prod) AS q_prod,
    countIf(qual_stability) AS q_stability,
    countIf(ec = 'service_restarted' AND rr = 'user_quit') AS user_quit_n
  FROM c GROUP BY d
), d2 AS (
  SELECT toDate(fts) AS d, countIf(fo = 'success' AND NOT unknown) AS flow_ok,
    countIf(fq_prod AND NOT unknown) AS fq_prod,
    countIf(fq_stability AND NOT unknown) AS fq_stability
  FROM flows GROUP BY d
)
SELECT toString(d1.d) AS dt, d1.ok AS ok,
  round(d1.ok / nullIf(d1.q_prod, 0), 3) AS product_attempt_rate,
  round(d1.ok / nullIf(d1.q_stability, 0), 3) AS stability_attempt_rate,
  round(d2.flow_ok / nullIf(d2.fq_prod, 0), 3) AS product_flow_rate,
  round(d2.flow_ok / nullIf(d2.fq_stability, 0), 3) AS stability_flow_rate,
  d1.q_prod AS q_prod, d1.q_stability AS q_stability, d1.user_quit_n AS user_quit_restarts
FROM d1 LEFT JOIN d2 ON d1.d = d2.d
ORDER BY dt;
