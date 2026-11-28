import { useEffect, useState } from 'react'
import { getLocale } from '../../i18n'
import { buildApiUrl, isApiReady, waitForApiReady } from '../../utils/apiConfig'
import { HTML_TEMPLATE_CHOICES } from './editingStyle'

export type LocalizedCopy = {
  zh: string
  en: string
  locales?: Record<string, string>
}

export type TemplateVariableSpec = {
  key: string
  kind: 'color' | 'number' | 'boolean' | 'select'
  label: LocalizedCopy
  default: string | number | boolean
  min?: number | null
  max?: number | null
  options?: string[]
}

export type TemplateCatalogItem = {
  id: string
  name: LocalizedCopy
  desc: LocalizedCopy
  tags: string[]
  category: string
  order: number
  featured?: boolean
  version: string
  source: 'builtin' | 'installed' | 'remote'
  installed: boolean
  removable: boolean
  update_available: boolean
  latest_version: string
  badge?: string | null
  size_bytes?: number
  variables?: TemplateVariableSpec[]
  user_vars?: Record<string, string | number | boolean>
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
      const locale = encodeURIComponent(getLocale())
      const res = await fetch(buildApiUrl(`/studio/templates?locale=${locale}`))
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
  const locale = encodeURIComponent(getLocale())
  const res = await fetch(buildApiUrl(`/studio/templates/sync?force=true&locale=${locale}`), { method: 'POST' })
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

export async function importLocalTemplateArchive(file: File): Promise<{ installed: string; templates: TemplateCatalogItem[] }> {
  await ensureApi()
  const body = new FormData()
  body.append('archive', file, file.name || 'template.zip')
  const res = await fetch(buildApiUrl('/studio/templates/import'), { method: 'POST', body })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'import failed')
  }
  const data = await res.json() as TemplateCatalogResponse & { installed: string }
  return { installed: data.installed, templates: applyResponse(data) }
}

export type CloneBlueprint = {
  name_zh: string
  name_en: string
  desc_zh: string
  desc_en: string
  accent_color: string
  text_color: string
  caption_motion: string
  header_style: string
  font_style: string
  font_scale: 'S' | 'M' | 'L'
  depth_enabled: boolean
  grain_enabled: boolean
  category: string
}

export type CloneJobState = {
  job_id: string
  status: 'running' | 'ready' | 'failed'
  step: 'extract' | 'analyze' | 'render' | 'ready'
  error: string | null
  frames: string[]
  blueprint: CloneBlueprint | null
  revision: number
  can_undo: boolean
  template_id: string | null
  preview_zh_url: string | null
  preview_en_url: string | null
  poster_url: string | null
}

export async function fetchCloneReadiness(): Promise<{ vision_capable: boolean; model: string }> {
  try {
    await ensureApi()
    const res = await fetch(buildApiUrl('/studio/templates/clone/readiness'))
    if (!res.ok) return { vision_capable: false, model: '' }
    return await res.json()
  } catch {
    return { vision_capable: false, model: '' }
  }
}

export async function startTemplateClone(opts: {
  referenceUrl?: string
  file?: File | null
  previewFile?: File | null
  promptHint?: string
  depthMode?: 'auto' | 'on' | 'off'
}): Promise<CloneJobState> {
  await ensureApi()
  const body = new FormData()
  if (opts.referenceUrl) body.append('reference_url', opts.referenceUrl)
  if (opts.promptHint) body.append('prompt_hint', opts.promptHint)
  body.append('depth_mode', opts.depthMode || 'auto')
  if (opts.file) body.append('file', opts.file, opts.file.name || 'reference.mp4')
  if (opts.previewFile) body.append('preview_file', opts.previewFile, opts.previewFile.name || 'preview.mp4')
  const res = await fetch(buildApiUrl('/studio/templates/clone'), { method: 'POST', body })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'clone failed')
  }
  return await res.json()
}

export async function getTemplateCloneJob(jobId: string): Promise<CloneJobState> {
  await ensureApi()
  const res = await fetch(buildApiUrl(`/studio/templates/clone/${encodeURIComponent(jobId)}`))
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'poll failed')
  }
  return await res.json()
}

export async function refineTemplateClone(
  jobId: string,
  opts: { variableOverrides?: Record<string, unknown>; instruction?: string },
): Promise<CloneJobState> {
  await ensureApi()
  const res = await fetch(buildApiUrl(`/studio/templates/clone/${encodeURIComponent(jobId)}/refine`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      variable_overrides: opts.variableOverrides ?? null,
      instruction: opts.instruction ?? '',
    }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'refine failed')
  }
  return await res.json()
}

export async function revertTemplateClone(jobId: string): Promise<CloneJobState> {
  await ensureApi()
  const res = await fetch(buildApiUrl(`/studio/templates/clone/${encodeURIComponent(jobId)}/revert`), { method: 'POST' })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'revert failed')
  }
  return await res.json()
}

export async function saveTemplateClone(
  jobId: string,
  opts: { nameZh?: string; nameEn?: string },
): Promise<{ installed: string; templates: TemplateCatalogItem[] }> {
  await ensureApi()
  const res = await fetch(buildApiUrl(`/studio/templates/clone/${encodeURIComponent(jobId)}/save`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name_zh: opts.nameZh ?? null, name_en: opts.nameEn ?? null }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'save failed')
  }
  const data = await res.json() as TemplateCatalogResponse & { installed: string }
  return { installed: data.installed, templates: applyResponse(data) }
}

export async function updateTemplateVars(
  templateId: string,
  vars: Record<string, string | number | boolean>,
): Promise<Record<string, string | number | boolean>> {
  await ensureApi()
  const res = await fetch(buildApiUrl(`/studio/templates/${encodeURIComponent(templateId)}/vars`), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vars }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail || 'update vars failed')
  }
  const data = await res.json() as { vars: Record<string, string | number | boolean> }
  currentItems = currentItems.map(it => it.id === templateId ? { ...it, user_vars: data.vars } : it)
  emit()
  return data.vars
}

export function exportTemplateUrl(templateId: string): string {
  return buildApiUrl(`/studio/templates/${encodeURIComponent(templateId)}/export`)
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
