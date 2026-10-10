import { flagAssigned, flagEnabled } from '../../analytics/flags'
import { captureBusinessEvent } from '../../analytics/posthog'
import { safeStudioProperties } from '../../analytics/workflow'
import { applyCompletion, browserTransport, noticeView, type NoticeKind } from './completionNotice'

const listeners = new Set<(projectId: string, kind: NoticeKind) => void>()

export function subscribeCompletionNotice(listener: (projectId: string, kind: NoticeKind) => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

/** Flag off: no permission check, no badge, no event. Analytics off still shows the line when a local override is on. */
export function noteWorkspaceCompletion(projectId: string, snapshot: Parameters<typeof noticeView>[0]) {
  if (!projectId || !flagEnabled('notify_on_done')) return
  const assigned = flagAssigned('notify_on_done')
  const track = (name: 'notification_sent' | 'notification_opened', kind: NoticeKind, permission: string) => {
    if (!assigned) return
    captureBusinessEvent(name, safeStudioProperties({ kind, permission }))
  }
  void applyCompletion({
    projectKey: projectId,
    view: noticeView(snapshot),
    enabled: true,
    storage: sessionStorage,
    transport: browserTransport(),
    onKind: kind => { for (const listener of listeners) listener(projectId, kind) },
    onSent: (kind, permission) => track('notification_sent', kind, permission),
    onOpened: (kind, permission) => track('notification_opened', kind, permission),
  }).catch(() => undefined)
}

export function clearCompletionBadge() {
  const clear = browserTransport().setBadge
  if (!clear) return Promise.resolve()
  return Promise.resolve(clear(undefined)).catch(() => undefined)
}

export type { NoticeKind }
