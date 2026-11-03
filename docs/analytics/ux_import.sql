-- One-click import funnel. Flows are not people. URLs and titles are not in these events.
-- Compare treatment with properties.$feature/one_click_paste_start once PostHog flags exist.
SELECT event,
       properties.trigger AS trigger,
       properties.platform_source AS platform_source,
       properties.transcription_route AS transcription_route,
       count() AS events,
       uniq(tuple(distinct_id, properties.flow_id)) AS flows
FROM events
WHERE timestamp >= now() - INTERVAL 28 DAY
  AND properties.studio_schema_version = 2
  AND event IN ('studio_one_click_started', 'studio_one_click_undone', 'studio_auto_choice_overridden', 'studio_legacy_entry_used')
GROUP BY event, trigger, platform_source, transcription_route
ORDER BY events DESC
