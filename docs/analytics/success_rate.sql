-- 1.5.7 出片成功率（v4 口径）。终态事件由后端发送，看板合入后同步。studio_generation_finished / studio_production_finished 由后端
-- settle_attempt 在落盘后各发一次（runtime=desktop，analytics_environment 仍是 AUTOCLIP_BUILD_ENVIRONMENT）。
-- 前端不再发这两条，避免和后端重复计入分母。分子和分母都是这两条终态，没有单独的起始事件要搬家。
-- 本文件在 #416 之上按 (attempt_sequence, leaf, ts) 取末次，并输出 unknown_flows / 图 6。查询本身不改。
-- 口径见 docs/analytics/TRACKING_PLAN.md §6–§7。所有查询共用同一个 base / c 定义。
--
-- 分母为 0（稀疏的日期 / 版本 / 空窗口）时比率返回 NULL，不是 NaN（R20 #142：nullIf(分母, 0)）。
-- 参数（发版/报数时替换，不再用 now() - 7d 滚动窗口）：
--   {date_from}          固定 UTC 起点（含），例如 '2026-10-09 00:00:00'
--   {date_to}            固定 UTC 终点（不含），例如 '2026-10-16 00:00:00'
--   {internal_cohort_id} 内部账号 cohort id（project 450605 当前为 641509）
--   {release_1_5_7}      1.5.7 正式发布时间（UTC，含）。GitHub Release 的 published_at 形如
--                        YYYY-MM-DDTHH:MM:SSZ，填成带单引号的 'YYYY-MM-DD HH:MM:SS'（去掉 T 和 Z）。
--                        执行 RELEASE_CHECKLIST.md 3.5 Promote 的人，把它填进 PostHog 项目 450605
--                        看板「AutoClip｜1.5.7 出片成功率」里本文件的每一条 insight
--                        （version_releases 中 1.5.7 那一行的 released_at_text）。本文件不写死日期。
--                        空字符串 '' 表示还没填：这一版的事件全部不计入。1.5.6 及更早不在表里。
--
-- 定义：
--   attempt  = 一次终态尝试，按 attempt_id 去重（取最后一条）；缺 attempt_id 的历史行按事件 uuid 计。
--   flow     = 用户的一次出片流程：沿 retry_of 回溯到重试链根（最多 4 跳），用根 attempt 的 flow_id；
--              结果取该流程 / 重试链里最后一次 attempt，排序键为 (attempt_sequence, leaf, ts)：先按 attempt_sequence
--              （后端回执的项目内序号，#419；没有序号按 0，所以有序号的 attempt 总排在旧 attempt 后面），其次按 leaf
--              （retry_of 链末端 = 没有被再重试的 attempt），ts（观察时间）只用来打平（事件乱序到达不改结果）。
--   未知流程 = 没有 attempt_sequence 且有不止一个链末端的流程（#419 之前、同 flow_id 多次 attempt，无法证明哪次
--              是最后一次）：不进图 1 / 图 5 的流程分子分母，单独计 unknown_flows（R26 #362）。attempt 级不受影响，
--              单 attempt 或 retry_of 链完整的旧流程照常计算。
--   person   = person_id（不是 distinct_id / 设备）。
--   success  = outcome IN ('completed','success')。partial 不算成功，单独算 partial-delivery 率。
--   全量口径分母剔除（user_hard，只剔除明确的用户行为）：
--     outcome = cancelled；error_code IN (authentication, llm_auth_invalid, invalid_key, insufficient_quota,
--     llm_not_configured, cancelled, user_cancelled)；upstream_error_type IN (invalid_key, insufficient_quota, permission_denied)。
--   产品口径分母再剔除（user_x）：error_code IN (connection, source_too_short, source_no_audio, source_unreadable, source_blocked, source_not_found)。
--   两个口径都算产品失败（不剔除）：whisper_not_installed、service_restarted、model_not_found、bad_endpoint
--   （error_code 或 upstream_error_type）。
-- 只看 analytics_environment = 'production' 且 runtime = 'desktop'，排除内部 cohort。
-- validation / development 仍由上面的过滤排除。打成 production 的内部账号仍靠 {internal_cohort_id} 排除。
-- 旧的 1.5.7 内部测试包也是 production + desktop，两个内部 cohort 都是空的，环境和 cohort 分不开。
-- 表 version_releases 给表里的对外版本加发布时间下限：timestamp >= released_at（含）才计入。
-- 1.5.6 及更早不在表里，不受这道下限影响。事件上没有 commit 或构建时间，这里不新增字段，也不改 cohort。
-- 图 5 仍按 app_version 分组。
--   frame_extract_failed（本地抽帧失败，1.5.7 R11）是产品失败，计入两个口径的分母，不在任何剔除列表里。
--   frame_extract_subtitle_fallback / source_too_long_subtitle_route / vision_*_subtitle_fallback 是成功出片上的
--   degrade_reason（降级走字幕），不是失败码，见图 6。

-- 图 1：按日 按次 / 按流程 成功率（全量 + 产品）与 partial-delivery 率
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
), base AS (
  SELECT
    toString(coalesce(properties.attempt_id, toString(uuid))) AS aid,
    argMax(toString(coalesce(properties.flow_id, properties.attempt_id, toString(uuid))), timestamp) AS fid,
    argMax(person_id, timestamp) AS pid,
    max(timestamp) AS ts,
    -- R25 #346: the backend receipt's per-project attempt sequence (NULL on rows from before #419)
    max(toInt(properties.attempt_sequence)) AS seq,
    argMax(toString(properties.outcome), timestamp) AS o_raw,
    argMax(coalesce(toString(properties.error_code), ''), timestamp) AS ec,
    argMax(coalesce(toString(properties.upstream_error_type), ''), timestamp) AS ue,
    argMax(coalesce(toString(properties.failure_stage), '(空)'), timestamp) AS stage,
    argMax(toString(properties.app_version), timestamp) AS v,
    argMax(coalesce(toString(properties.retry_of), ''), timestamp) AS rof
  FROM events
  LEFT JOIN version_releases vr ON vr.app_version = toString(properties.app_version)
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND toString(properties.analytics_environment) = 'production'
    AND toString(properties.runtime) = 'desktop'
    AND timestamp >= toDateTime({date_from}, 'UTC')
    AND timestamp < toDateTime({date_to}, 'UTC')
    AND person_id NOT IN COHORT {internal_cohort_id}
    -- HogQL 未匹配的 LEFT JOIN 得到 '' 而不是 NULL，表外版本（1.5.6 及更早）也要放行。
    AND (vr.app_version IS NULL OR vr.app_version = '' OR (vr.released_at_text != '' AND timestamp >= toDateTime(nullIf(vr.released_at_text, ''), 'UTC')))
  GROUP BY aid
), chained AS (
  -- retry chain: follow retry_of up to 4 hops to the chain root, the flow is the root's flow.
  SELECT b.*,
    multiIf(p4.aid != '', p4.fid, p3.aid != '', p3.fid, p2.aid != '', p2.fid, p1.aid != '', p1.fid, b.fid) AS chain_fid,
    multiIf(r.retried != '', 0, 1) AS leaf
  FROM base b
  LEFT JOIN base p1 ON b.rof = p1.aid
  LEFT JOIN base p2 ON p1.rof = p2.aid
  LEFT JOIN base p3 ON p2.rof = p3.aid
  LEFT JOIN base p4 ON p3.rof = p4.aid
  -- R26 #362: leaf = no other attempt retries this one (the end of a retry_of chain); orders legacy flows
  LEFT JOIN (SELECT DISTINCT rof AS retried FROM base WHERE rof != '') r ON r.retried = b.aid
), c AS (
  SELECT *,
    multiIf(o_raw IN ('completed', 'success'), 'success', o_raw = 'partial', 'partial', o_raw IN ('cancelled', 'canceled'), 'cancelled', 'error') AS o,
    (o = 'cancelled'
      OR ec IN ('authentication', 'llm_auth_invalid', 'invalid_key', 'insufficient_quota', 'llm_not_configured', 'cancelled', 'user_cancelled')
      OR ue IN ('invalid_key', 'insufficient_quota', 'permission_denied')) AS user_hard,
    (user_hard OR ec IN ('connection', 'source_too_short', 'source_no_audio', 'source_unreadable', 'source_blocked', 'source_not_found')) AS user_x,
    (o = 'success' OR NOT user_hard) AS qual_all,
    (o = 'success' OR NOT user_x) AS qual
    , (ifNull(seq, 0), leaf, ts) AS ord
  FROM chained
), flows AS (
  -- per-flow outcome = the LAST attempt in the flow / retry chain
  SELECT chain_fid AS fid, max(ts) AS fts, argMax(o, ord) AS fo, argMax(qual, ord) AS fq, argMax(qual_all, ord) AS fqa,
    -- R26 #362: a flow with no attempt_sequence and more than one chain end has no provable last attempt: unknown
    (countIf(seq IS NOT NULL) = 0 AND sum(leaf) > 1) AS unknown FROM c GROUP BY chain_fid
), d1 AS (
  SELECT toDate(ts) AS d, countIf(o = 'success') AS ok, countIf(qual_all) AS q_all, countIf(qual) AS q_prod,
    countIf(o = 'partial' AND qual) AS partial_n
  FROM c GROUP BY d
), d2 AS (
  SELECT toDate(fts) AS d, countIf(fo = 'success' AND NOT unknown) AS flow_ok, countIf(fqa AND NOT unknown) AS fq_all,
    countIf(fq AND NOT unknown) AS fq_prod, countIf(unknown) AS unknown_n FROM flows GROUP BY d
)
SELECT toString(d1.d) AS dt, d1.ok AS ok,
  round(d1.ok / nullIf(d1.q_all, 0), 3) AS overall_attempt_rate, round(d1.ok / nullIf(d1.q_prod, 0), 3) AS product_attempt_rate,
  round(d2.flow_ok / nullIf(d2.fq_all, 0), 3) AS overall_flow_rate, round(d2.flow_ok / nullIf(d2.fq_prod, 0), 3) AS product_flow_rate,
  round(d1.partial_n / nullIf(d1.q_prod, 0), 3) AS partial_delivery_rate,
  d1.q_all AS q_all, d1.q_prod AS q_prod, d2.flow_ok AS flow_ok, d2.fq_all AS fq_all, d2.fq_prod AS fq_prod,
  d2.unknown_n AS unknown_flows
FROM d1 LEFT JOIN d2 ON d1.d = d2.d
ORDER BY dt;

-- 图 2：按人（person_id）首次合格出片成功率（全量 + 产品）
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
), base AS (
  SELECT
    toString(coalesce(properties.attempt_id, toString(uuid))) AS aid,
    argMax(person_id, timestamp) AS pid,
    max(timestamp) AS ts,
    argMax(toString(properties.outcome), timestamp) AS o_raw,
    argMax(coalesce(toString(properties.error_code), ''), timestamp) AS ec,
    argMax(coalesce(toString(properties.upstream_error_type), ''), timestamp) AS ue
  FROM events
  LEFT JOIN version_releases vr ON vr.app_version = toString(properties.app_version)
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND toString(properties.analytics_environment) = 'production'
    AND toString(properties.runtime) = 'desktop'
    AND timestamp >= toDateTime({date_from}, 'UTC')
    AND timestamp < toDateTime({date_to}, 'UTC')
    AND person_id NOT IN COHORT {internal_cohort_id}
    -- HogQL 未匹配的 LEFT JOIN 得到 '' 而不是 NULL，表外版本（1.5.6 及更早）也要放行。
    AND (vr.app_version IS NULL OR vr.app_version = '' OR (vr.released_at_text != '' AND timestamp >= toDateTime(nullIf(vr.released_at_text, ''), 'UTC')))
  GROUP BY aid
), c AS (
  SELECT *,
    multiIf(o_raw IN ('completed', 'success'), 'success', o_raw = 'partial', 'partial', o_raw IN ('cancelled', 'canceled'), 'cancelled', 'error') AS o,
    (o = 'cancelled'
      OR ec IN ('authentication', 'llm_auth_invalid', 'invalid_key', 'insufficient_quota', 'llm_not_configured', 'cancelled', 'user_cancelled')
      OR ue IN ('invalid_key', 'insufficient_quota', 'permission_denied')) AS user_hard,
    (user_hard OR ec IN ('connection', 'source_too_short', 'source_no_audio', 'source_unreadable', 'source_blocked', 'source_not_found')) AS user_x,
    (o = 'success' OR NOT user_hard) AS qual_all,
    (o = 'success' OR NOT user_x) AS qual
  FROM base
), p AS (
  SELECT pid, argMinIf(o, ts, qual_all) AS f_all, argMinIf(o, ts, qual) AS f_prod,
    countIf(qual_all) > 0 AS has_all, countIf(qual) > 0 AS has_prod
  FROM c GROUP BY pid
)
SELECT countIf(has_all AND f_all = 'success') AS overall_first_ok, countIf(has_all) AS overall_people,
  round(overall_first_ok / nullIf(overall_people, 0), 3) AS overall_first_rate,
  countIf(has_prod AND f_prod = 'success') AS product_first_ok, countIf(has_prod) AS product_people,
  round(product_first_ok / nullIf(product_people, 0), 3) AS product_first_rate
FROM p;

-- 图 3：失败身份（failure_stage × error_code × 归因），按 attempt 去重
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
), base AS (
  SELECT
    toString(coalesce(properties.attempt_id, toString(uuid))) AS aid,
    argMax(toString(properties.outcome), timestamp) AS o_raw,
    argMax(coalesce(toString(properties.error_code), ''), timestamp) AS ec,
    argMax(coalesce(toString(properties.upstream_error_type), ''), timestamp) AS ue,
    argMax(coalesce(toString(properties.failure_stage), '(空)'), timestamp) AS stage
  FROM events
  LEFT JOIN version_releases vr ON vr.app_version = toString(properties.app_version)
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND toString(properties.analytics_environment) = 'production'
    AND toString(properties.runtime) = 'desktop'
    AND timestamp >= toDateTime({date_from}, 'UTC')
    AND timestamp < toDateTime({date_to}, 'UTC')
    AND person_id NOT IN COHORT {internal_cohort_id}
    -- HogQL 未匹配的 LEFT JOIN 得到 '' 而不是 NULL，表外版本（1.5.6 及更早）也要放行。
    AND (vr.app_version IS NULL OR vr.app_version = '' OR (vr.released_at_text != '' AND timestamp >= toDateTime(nullIf(vr.released_at_text, ''), 'UTC')))
  GROUP BY aid
), c AS (
  SELECT *,
    multiIf(o_raw IN ('completed', 'success'), 'success', o_raw = 'partial', 'partial', o_raw IN ('cancelled', 'canceled'), 'cancelled', 'error') AS o,
    (o = 'cancelled'
      OR ec IN ('authentication', 'llm_auth_invalid', 'invalid_key', 'insufficient_quota', 'llm_not_configured', 'cancelled', 'user_cancelled')
      OR ue IN ('invalid_key', 'insufficient_quota', 'permission_denied')) AS user_hard,
    (user_hard OR ec IN ('connection', 'source_too_short', 'source_no_audio', 'source_unreadable', 'source_blocked', 'source_not_found')) AS user_x
  FROM base
)
SELECT stage, if(ec = '', '(空)', ec) AS error_code, o AS outcome,
  multiIf(user_hard, 'user_both', user_x, 'user_product_only', 'product') AS attribution, count() AS attempts
FROM c WHERE o != 'success'
GROUP BY stage, error_code, outcome, attribution
ORDER BY attempts DESC;

-- 图 4：模型请求上游错误（诊断，不是成功率分母）
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
)
SELECT
  properties.provider AS provider,
  properties.upstream_error_type AS upstream_error_type,
  count() AS events
FROM events
LEFT JOIN version_releases vr ON vr.app_version = toString(properties.app_version)
WHERE event = 'llm_request_finished'
  AND toString(properties.analytics_environment) = 'production'
  AND properties.outcome = 'error'
  AND timestamp >= toDateTime({date_from}, 'UTC')
  AND timestamp < toDateTime({date_to}, 'UTC')
  AND person_id NOT IN COHORT {internal_cohort_id}
  -- HogQL 未匹配的 LEFT JOIN 得到 '' 而不是 NULL，表外版本（1.5.6 及更早）也要放行。
  AND (vr.app_version IS NULL OR vr.app_version = '' OR (vr.released_at_text != '' AND timestamp >= toDateTime(nullIf(vr.released_at_text, ''), 'UTC')))
GROUP BY provider, upstream_error_type
ORDER BY events DESC;


-- 图 5：按版本（app_version）按次 / 按流程成功率（全量 + 产品）与 partial-delivery 率
-- 与图 1 同一 base / chained / c；流程归到最后一次 attempt 的版本
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
), base AS (
  SELECT
    toString(coalesce(properties.attempt_id, toString(uuid))) AS aid,
    argMax(toString(coalesce(properties.flow_id, properties.attempt_id, toString(uuid))), timestamp) AS fid,
    argMax(person_id, timestamp) AS pid,
    max(timestamp) AS ts,
    -- R25 #346: the backend receipt's per-project attempt sequence (NULL on rows from before #419)
    max(toInt(properties.attempt_sequence)) AS seq,
    argMax(toString(properties.outcome), timestamp) AS o_raw,
    argMax(coalesce(toString(properties.error_code), ''), timestamp) AS ec,
    argMax(coalesce(toString(properties.upstream_error_type), ''), timestamp) AS ue,
    argMax(coalesce(toString(properties.failure_stage), '(空)'), timestamp) AS stage,
    argMax(toString(properties.app_version), timestamp) AS v,
    argMax(coalesce(toString(properties.retry_of), ''), timestamp) AS rof
  FROM events
  LEFT JOIN version_releases vr ON vr.app_version = toString(properties.app_version)
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND toString(properties.analytics_environment) = 'production'
    AND toString(properties.runtime) = 'desktop'
    AND timestamp >= toDateTime({date_from}, 'UTC')
    AND timestamp < toDateTime({date_to}, 'UTC')
    AND person_id NOT IN COHORT {internal_cohort_id}
    -- HogQL 未匹配的 LEFT JOIN 得到 '' 而不是 NULL，表外版本（1.5.6 及更早）也要放行。
    AND (vr.app_version IS NULL OR vr.app_version = '' OR (vr.released_at_text != '' AND timestamp >= toDateTime(nullIf(vr.released_at_text, ''), 'UTC')))
  GROUP BY aid
), chained AS (
  -- retry chain: follow retry_of up to 4 hops to the chain root, the flow is the root's flow.
  SELECT b.*,
    multiIf(p4.aid != '', p4.fid, p3.aid != '', p3.fid, p2.aid != '', p2.fid, p1.aid != '', p1.fid, b.fid) AS chain_fid,
    multiIf(r.retried != '', 0, 1) AS leaf
  FROM base b
  LEFT JOIN base p1 ON b.rof = p1.aid
  LEFT JOIN base p2 ON p1.rof = p2.aid
  LEFT JOIN base p3 ON p2.rof = p3.aid
  LEFT JOIN base p4 ON p3.rof = p4.aid
  -- R26 #362: leaf = no other attempt retries this one (the end of a retry_of chain); orders legacy flows
  LEFT JOIN (SELECT DISTINCT rof AS retried FROM base WHERE rof != '') r ON r.retried = b.aid
), c AS (
  SELECT *,
    multiIf(o_raw IN ('completed', 'success'), 'success', o_raw = 'partial', 'partial', o_raw IN ('cancelled', 'canceled'), 'cancelled', 'error') AS o,
    (o = 'cancelled'
      OR ec IN ('authentication', 'llm_auth_invalid', 'invalid_key', 'insufficient_quota', 'llm_not_configured', 'cancelled', 'user_cancelled')
      OR ue IN ('invalid_key', 'insufficient_quota', 'permission_denied')) AS user_hard,
    (user_hard OR ec IN ('connection', 'source_too_short', 'source_no_audio', 'source_unreadable', 'source_blocked', 'source_not_found')) AS user_x,
    (o = 'success' OR NOT user_hard) AS qual_all,
    (o = 'success' OR NOT user_x) AS qual
    , (ifNull(seq, 0), leaf, ts) AS ord
  FROM chained
), flows AS (
  SELECT chain_fid AS fid, argMax(v, ord) AS fv, argMax(o, ord) AS fo, argMax(qual, ord) AS fq, argMax(qual_all, ord) AS fqa,
    -- R26 #362: a flow with no attempt_sequence and more than one chain end has no provable last attempt: unknown
    (countIf(seq IS NOT NULL) = 0 AND sum(leaf) > 1) AS unknown FROM c GROUP BY chain_fid
), v1 AS (
  SELECT v, countIf(o = 'success') AS ok, countIf(qual_all) AS q_all, countIf(qual) AS q_prod,
    countIf(o = 'partial' AND qual) AS partial_n
  FROM c GROUP BY v
), v2 AS (
  SELECT fv AS v, countIf(fo = 'success' AND NOT unknown) AS flow_ok, countIf(fqa AND NOT unknown) AS fq_all,
    countIf(fq AND NOT unknown) AS fq_prod, countIf(unknown) AS unknown_n FROM flows GROUP BY fv
)
SELECT v1.v AS app_version, v1.ok AS ok,
  round(v1.ok / nullIf(v1.q_all, 0), 3) AS overall_attempt_rate, round(v1.ok / nullIf(v1.q_prod, 0), 3) AS product_attempt_rate,
  round(v2.flow_ok / nullIf(v2.fq_all, 0), 3) AS overall_flow_rate, round(v2.flow_ok / nullIf(v2.fq_prod, 0), 3) AS product_flow_rate,
  round(v1.partial_n / nullIf(v1.q_prod, 0), 3) AS partial_delivery_rate,
  v1.q_all AS q_all, v1.q_prod AS q_prod, v2.flow_ok AS flow_ok, v2.fq_all AS fq_all, v2.fq_prod AS fq_prod,
  v2.unknown_n AS unknown_flows
FROM v1 LEFT JOIN v2 ON v1.v = v2.v
ORDER BY app_version;

-- 图 6：降级走字幕的成功出片（degrade_reason，不是失败；不进剔除列表），按 attempt 去重
WITH version_releases AS (
  SELECT '1.5.7' AS app_version, {release_1_5_7} AS released_at_text
)
SELECT degrade_reason, count() AS attempts
FROM (
  SELECT
    toString(coalesce(properties.attempt_id, toString(uuid))) AS aid,
    argMax(toString(properties.outcome), timestamp) AS o_raw,
    argMax(coalesce(toString(properties.degrade_reason), ''), timestamp) AS degrade_reason
  FROM events
  LEFT JOIN version_releases vr ON vr.app_version = toString(properties.app_version)
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND toString(properties.analytics_environment) = 'production'
    AND toString(properties.runtime) = 'desktop'
    AND timestamp >= toDateTime({date_from}, 'UTC')
    AND timestamp < toDateTime({date_to}, 'UTC')
    AND person_id NOT IN COHORT {internal_cohort_id}
    -- HogQL 未匹配的 LEFT JOIN 得到 '' 而不是 NULL，表外版本（1.5.6 及更早）也要放行。
    AND (vr.app_version IS NULL OR vr.app_version = '' OR (vr.released_at_text != '' AND timestamp >= toDateTime(nullIf(vr.released_at_text, ''), 'UTC')))
  GROUP BY aid
)
WHERE o_raw IN ('completed', 'success')
  AND degrade_reason IN ('vision_unavailable_subtitle_fallback', 'vision_invalid_subtitle_fallback',
                         'frame_extract_subtitle_fallback', 'source_too_long_subtitle_route')
GROUP BY degrade_reason
ORDER BY attempts DESC;
