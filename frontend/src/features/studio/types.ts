export type Goal = 'content' | 'highlight' | 'promo'
export type Language = 'source' | 'zh' | 'en' | 'ja'
export interface Scene { id: string; label: string; start: number; end: number; evidence: string }
export interface Draft {
  id: string; title: string; hook: string; scenes: Scene[]; language: Language
  aspect: 'original' | 'portrait' | 'landscape'; layout: 'fit' | 'crop' | 'blur'
  subtitles: boolean; original_audio: boolean; revision: number; updated_at: string; origin: string
  parent_draft_id?: string | null; parent_revision?: number | null
}
export interface RenderJob {
  job_id: string; draft_id: string; title: string; revision: number
  status: 'queued' | 'running' | 'completed' | 'failed'; percent: number; created_at: string; error?: string
  result?: { width: number; height: number; duration: number; warnings: string[] }
}
export interface Workspace {
  drafts: Draft[]; events: Scene[]; jobs: RenderJob[]
  analysis: null | { status: 'running' | 'completed' | 'failed'; message?: string; error?: string; coverage?: { note: string; sample_interval: number } }
}
export const languages = [{ value: 'source', label: '原语言' }, { value: 'zh', label: '简体中文' }, { value: 'en', label: 'English' }, { value: 'ja', label: '日本語' }] as const
export const emptyWorkspace: Workspace = { drafts: [], events: [], jobs: [], analysis: null }
export function draftDuration(draft: Draft) { return draft.scenes.reduce((sum, scene) => sum + scene.end - scene.start, 0) }
export function draftError(draft: Draft): string | null {
  if (!draft.title.trim()) return '请填写成片标题'
  if (!draft.scenes.length) return '至少保留一个镜头'
  if (draft.scenes.some(s => !Number.isFinite(s.start) || !Number.isFinite(s.end) || s.start < 0 || s.end - s.start < .1)) return '镜头起止无效，每段至少 0.1 秒'
  if (draftDuration(draft) > 1800) return '单条成片不能超过 30 分钟'
  return null
}
export function moveScene(draft: Draft, index: number, delta: number): Draft {
  const next = index + delta
  if (next < 0 || next >= draft.scenes.length) return draft
  const scenes = [...draft.scenes]
  ;[scenes[index], scenes[next]] = [scenes[next], scenes[index]]
  return { ...draft, scenes }
}
