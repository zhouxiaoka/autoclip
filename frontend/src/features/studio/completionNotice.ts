/** Completion notices for one generation. The first snapshot only records it,
 * so opening an already finished project stays quiet. Later changes notify once. */

export type NoticeKind = 'first_clip' | 'all_done' | 'failed'
export type NoticePermission = 'granted' | 'denied' | 'default'

export type NoticeView = {
  createdAt: string
  status: string
  completed: number
}

export type NoticeMemory = {
  createdAt: string
  sent: NoticeKind[]
}

export type NoticeHandle = { onclick?: (handler: () => void) => void }

export type NoticeTransport = {
  permission: () => NoticePermission | Promise<NoticePermission>
  notify: (copy: string) => NoticeHandle | null | Promise<NoticeHandle | null>
  setBadge?: (count?: number) => void | Promise<void>
}

const NOTICE_KEY = 'autoclip.notices.v1'

export const NOTICE_COPY: Record<NoticeKind, string> = {
  first_clip: '第一条成片已经做好',
  all_done: '成片已经全部做好',
  failed: '这次制作没有完成',
}

export function noticeCopy(kind: NoticeKind): string {
  return NOTICE_COPY[kind]
}

export function noticeView(snapshot: {
  generation?: { created_at?: string; status?: string } | null
  output_variants?: { status?: string }[] | null
} | null | undefined): NoticeView | null {
  const generation = snapshot?.generation
  if (!generation?.created_at || !generation.status) return null
  const completed = (snapshot?.output_variants || []).filter(item => item.status === 'completed').length
  return { createdAt: generation.created_at, status: generation.status, completed }
}

/** At most one kind per update. A finished run replaces the first-clip ping. */
export function nextNotices(memory: NoticeMemory | null, view: NoticeView): { memory: NoticeMemory; kinds: NoticeKind[] } {
  if (!view.createdAt) return { memory: memory ?? { createdAt: '', sent: [] }, kinds: [] }
  if (!memory || memory.createdAt !== view.createdAt) {
    return { memory: { createdAt: view.createdAt, sent: [] }, kinds: [] }
  }
  const sent = new Set(memory.sent)
  const kinds: NoticeKind[] = []
  const ended = view.status === 'completed' || view.status === 'partial' || view.status === 'failed'
  if (!ended && view.completed > 0 && !sent.has('first_clip')) kinds.push('first_clip')
  if ((view.status === 'completed' || view.status === 'partial') && !sent.has('all_done')) kinds.push('all_done')
  if (view.status === 'failed' && !sent.has('failed')) kinds.push('failed')
  const deliver = kinds.filter(kind => kind === 'first_clip' ? !kinds.some(item => item !== 'first_clip') : true)
  for (const kind of kinds) sent.add(kind)
  if (deliver.some(kind => kind !== 'first_clip')) sent.add('first_clip')
  const order: NoticeKind[] = ['first_clip', 'all_done', 'failed']
  return { memory: { createdAt: view.createdAt, sent: order.filter(kind => sent.has(kind)) }, kinds: deliver }
}

function readMemory(storage: { getItem: (key: string) => string | null }, projectKey: string): NoticeMemory | null {
  try {
    const all = JSON.parse(storage.getItem(NOTICE_KEY) || '{}') as Record<string, NoticeMemory>
    const item = all?.[projectKey]
    if (!item || typeof item.createdAt !== 'string' || !Array.isArray(item.sent)) return null
    return item
  } catch {
    return null
  }
}

function writeMemory(storage: { getItem: (key: string) => string | null; setItem: (key: string, value: string) => void }, projectKey: string, memory: NoticeMemory) {
  let all: Record<string, NoticeMemory> = {}
  try { all = JSON.parse(storage.getItem(NOTICE_KEY) || '{}') } catch { all = {} }
  if (!all || typeof all !== 'object') all = {}
  all[projectKey] = memory
  storage.setItem(NOTICE_KEY, JSON.stringify(all))
}

function asPermission(value: string): NoticePermission {
  return value === 'granted' || value === 'denied' ? value : 'default'
}

export async function applyCompletion(input: {
  projectKey: string
  view: NoticeView | null
  enabled: boolean
  storage: { getItem: (key: string) => string | null; setItem: (key: string, value: string) => void }
  transport: NoticeTransport
  onKind?: (kind: NoticeKind) => void
  onSent?: (kind: NoticeKind, permission: NoticePermission) => void
  onOpened?: (kind: NoticeKind, permission: NoticePermission) => void
}): Promise<NoticeKind | null> {
  if (!input.enabled || !input.projectKey || !input.view) return null
  const next = nextNotices(readMemory(input.storage, input.projectKey), input.view)
  try { writeMemory(input.storage, input.projectKey, next.memory) } catch { /* the in-app line can still show */ }
  const kind = next.kinds[0] || null
  if (!kind) return null
  input.onKind?.(kind)
  let permission: NoticePermission = 'default'
  try { permission = asPermission(await input.transport.permission()) } catch { permission = 'default' }
  let shown = false
  if (permission === 'granted') {
    try {
      const handle = await input.transport.notify(noticeCopy(kind))
      shown = !!handle
      handle?.onclick?.(() => input.onOpened?.(kind, 'granted'))
      if (shown) await input.transport.setBadge?.(1)
    } catch { shown = false }
  }
  if (shown || permission !== 'granted') input.onSent?.(kind, permission)
  return kind
}

/** Web Notification inside the desktop webview. Dock badge only when Tauri is present. */
export function browserTransport(): NoticeTransport {
  return {
    permission() {
      try {
        const value = typeof Notification === 'undefined' ? 'default' : Notification.permission
        return asPermission(value)
      } catch { return 'default' }
    },
    notify(copy) {
      const note = new Notification(copy)
      return {
        onclick: handler => {
          note.onclick = () => {
            try { window.focus() } catch { /* focus is optional */ }
            handler()
          }
        },
      }
    },
    async setBadge(count) {
      const desktop = typeof window !== 'undefined' && !!((window as unknown as { __TAURI_INTERNALS__?: unknown; __TAURI__?: unknown }).__TAURI_INTERNALS__ || (window as unknown as { __TAURI__?: unknown }).__TAURI__)
      if (!desktop) return
      const { getCurrentWindow } = await import('@tauri-apps/api/window')
      await getCurrentWindow().setBadgeCount(count)
    },
  }
}
