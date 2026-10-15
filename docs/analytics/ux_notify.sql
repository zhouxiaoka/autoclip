-- Completion notices and edits of automatic choices. Counts and enums only.
SELECT
  event,
  properties.kind AS kind,
  properties.permission AS permission,
  properties.field AS field,
  properties.stage AS stage,
  count() AS events
FROM events
WHERE timestamp > now() - INTERVAL 14 DAY
  AND event IN ('notification_sent', 'notification_opened', 'studio_auto_choice_overridden')
GROUP BY event, kind, permission, field, stage
ORDER BY events DESC
