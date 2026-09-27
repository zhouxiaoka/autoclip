SELECT event, properties.source_type AS source_type,
       properties.analysis_mode AS analysis_mode, properties.goal_content AS content,
       properties.goal_highlight AS highlight, properties.goal_promo AS promo,
       properties.recommendation_mode AS recommendation_mode,
       count() AS events, uniq(distinct_id) AS devices
FROM events
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND properties.studio_schema_version = 1
  AND properties.analytics_environment = 'production'
  AND event IN ('studio_import_accepted', 'studio_confirm_accepted', 'studio_screen_finished',
    'studio_rewrite_accepted', 'studio_draft_duplicate_accepted', 'social_publish_accepted')
GROUP BY event, source_type, analysis_mode, content, highlight, promo, recommendation_mode
ORDER BY events DESC LIMIT 100
