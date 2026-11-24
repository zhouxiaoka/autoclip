import { useEffect, useState } from 'react'
import { buildApiUrl, isApiReady, waitForApiReady } from '../../utils/apiConfig'
import { HTML_TEMPLATE_CHOICES } from './editingStyle'

export type LocalizedCopy = {
  zh: string
  en: string
  locales?: Record<string, string>
}

export type TemplateCatalogItem = {
  id: string
  name: LocalizedCopy
  desc: LocalizedCopy
  tags: string[]
  category: string
  order: number
  version: string
  source: 'builtin' | 'installed' | 'remote'
  installed: boolean
  removable: boolean
  update_available: boolean
  latest_version: string
  size_bytes?: number
  poster_url: string | null
  preview_mp4_url: string | null
  preview_webm_url: string | null
}

export type TemplateCatalogResponse = {
  templates: TemplateCatalogItem[]
  catalog_url: string | null
  catalog_updated_at: string
  catalog_synced_at: number
}

const BUILTIN_DEFAULTS: TemplateCatalogItem[] = HTML_TEMPLATE_CHOICES.map((id, idx) => ({
  id,
  name: { zh: id, en: id },
  desc: { zh: '', en: '' },
  tags: [],
  category: id,
  order: (idx + 1) * 10,
  version: '1.0.0',
  source: 'builtin',
  installed: true,
  removable: false,
  update_available: false,
  latest_version: '1.0.0',
  poster_url: null,
  preview_mp4_url: null,
  preview_webm_url: null,
}))

let currentItems: TemplateCatalogItem[] = BUILTIN_DEFAULTS
let loadedOnce = false
let inflight: Promise<TemplateCatalogItem[]> | null = null
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

function desktopShell(): boolean {
  return typeof window !== 'undefined' && Boolean(
    (window as Window & { __TAURI__?: unknown; __TAURI_INTERNALS__?: unknown }).__TAURI__
    || (window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__,
  )
}

async function ensureApi(): Promise<void> {
  if (desktopShell() && !isApiReady()) {
    await waitForApiReady(1500)
  }
}

export function resolveTemplateAssetUrl(url: string | null | undefined): string | null {
  if (!url) return null
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/v1/')) return buildApiUrl(url.slice('/api/v1'.length))
  return buildApiUrl(url)
}

export function resolveLocalizedCopy(copy: LocalizedCopy | undefined, locale: string, fallback = ''): string {
  if (!copy) return fallback
  const norm = (locale || 'zh').trim().toLowerCase()
  if (copy.locales?.[norm]) return copy.locales[norm]
  const short = norm.split('-', 1)[0]
  if (copy.locales?.[short]) return copy.locales[short]
  if (short === 'zh') return copy.zh || copy.en || fallback
  return copy.en || copy.zh || fallback
}

function applyResponse(data: Partial<TemplateCatalogResponse> | null | undefined): TemplateCatalogItem[] {
  if (data && Array.isArray(data.templates) && data.templates.length > 0) {
    currentItems = data.templates
    loadedOnce = true
    emit()
  }
  return currentItems
}

export async function fetchTemplateCatalog(force = false): Promise<TemplateCatalogItem[]> {
  if (!force && loadedOnce) return currentItems
  if (!force && inflight) return inflight
  const run = (async () => {
    try {
      await ensureApi()
      const res = await fetch(buildApiUrl('/studio/templates'))
      if (!res.ok) return currentItems
      const data = await res.json() as TemplateCatalogResponse
      return applyResponse(data)
    } catch {
      return currentItems
    } finally {
      inflight = null
    }
  })()
  inflight = run
  return run
}

export async function syncTemplateCatalog(): Promise<TemplateCatalogItem[]> {
  await ensureApi()
  const res = await fetch(buildApiUrl('/studio/templates/sync?force=true'), { method: 'POST' })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'sync failed')
  }
  return applyResponse(await res.json())
}

export async function installRemoteTemplate(templateId: string): Promise<TemplateCatalogItem[]> {
  await ensureApi()
  const res = await fetch(buildApiUrl(`/studio/templates/${encodeURIComponent(templateId)}/install`), { method: 'POST' })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'install failed')
  }
  return applyResponse(await res.json())
}

export async function uninstallUserTemplate(templateId: string): Promise<TemplateCatalogItem[]> {
  await ensureApi()
  const res = await fetch(buildApiUrl(`/studio/templates/${encodeURIComponent(templateId)}`), { method: 'DELETE' })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'uninstall failed')
  }
  return applyResponse(await res.json())
}

export function resetTemplateCatalogForTests(): void {
  currentItems = BUILTIN_DEFAULTS
  loadedOnce = false
  inflight = null
  emit()
}

export function useTemplateCatalog(): {
  items: TemplateCatalogItem[]
  installed: TemplateCatalogItem[]
  remote: TemplateCatalogItem[]
} {
  const [items, setItems] = useState<TemplateCatalogItem[]>(() => currentItems)

  useEffect(() => {
    const onChange = () => setItems(currentItems)
    listeners.add(onChange)
    if (typeof fetch === 'function') {
      void fetchTemplateCatalog()
    }
    return () => { listeners.delete(onChange) }
  }, [])

  return {
    items,
    installed: items.filter(item => item.installed),
    remote: items.filter(item => !item.installed),
  }
}
