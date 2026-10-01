export type Goal = 'content' | 'highlight' | 'promo'
export type Language = 'source' | 'zh' | 'en' | 'ja'
export type SubtitleStyle = 'clean' | 'bold' | 'box' | 'accent'
export const subtitleStyles: { value: SubtitleStyle; label: string }[] = [{ value: 'clean', label: '简洁描边' }, { value: 'bold', label: '粗体大字' }, { value: 'box', label: '底色字幕条' }, { value: 'accent', label: '醒目黄字' }]
export interface SubtitleCue { start: number; end: number; text: string }
export interface FramingStatus { status: 'installed' | 'not_installed' | 'installing' | 'error'; progress: number; message: string; size_mb: number }
export interface AutoFrameResult { window_fraction: number; scenes: { id: string; crop_x: number | null; crop_track: CropPoint[] | null; faces: number; samples: number; shots: number; fit_shots: number; switches: number }[] }
export type FrameMode = 'crop' | 'fit'
/** One shot of a scene: from `start` (seconds into the scene) until the next point. `fit` shows the whole frame. */
export interface CropPoint { start: number; crop_x: number; mode?: FrameMode }
export interface Scene { framing_source?: 'auto' | 'manual' | null; framing_adjusted?: boolean; id: string; label: string; start: number; end: number; evidence: string; crop_x?: number | null; crop_track?: CropPoint[] | null }
/** Index of the track point covering `time` (absolute seconds), or -1 without a track. */
export function shotIndexAt(scene: Scene | undefined, time: number): number {
  const track = scene?.crop_track || []
  if (!scene || !track.length) return -1
  const rel = time - scene.start
  let index = 0
  track.forEach((p, i) => { if (p.start <= rel) index = i })
  return index
}
/** Crop window position for a scene at `time` (absolute seconds): speaker track first, then static values. */
export function cropAt(scene: Scene | undefined, time: number, fallback = .5): number {
  if (!scene) return fallback
  const index = shotIndexAt(scene, time)
  if (index >= 0) return scene.crop_track![index].crop_x
  return scene.crop_x ?? fallback
}
/** How the current shot is shown in a cropped layout. */
export function frameModeAt(scene: Scene | undefined, time: number): FrameMode {
  const index = shotIndexAt(scene, time)
  return index >= 0 ? scene!.crop_track![index].mode || 'crop' : 'crop'
}
/** Update the shot under `time`; a scene without a track gets a single point covering the whole scene. */
export function patchShot(scene: Scene, time: number, changes: Partial<CropPoint>, fallback = .5): Scene {
  const track = scene.crop_track?.length ? scene.crop_track : [{ start: 0, crop_x: scene.crop_x ?? fallback, mode: 'crop' as FrameMode }]
  const index = Math.max(0, shotIndexAt({ ...scene, crop_track: track }, time))
  return { ...scene, crop_track: track.map((p, i) => i === index ? { ...p, ...changes } : p) }
}
export interface Candidate extends Scene { kind: 'visual' | 'legacy' }
export interface CandidateList { duration: number; candidates: Candidate[]; warnings: string[] }
export interface Packaging {
  version: 1; template: 'interview_zh' | 'podcast_en'; audience_language: 'zh' | 'en'; source_language: 'zh' | 'en' | 'other'
  title_lines: string[]; title_accent_line: number
  cues: { start: number; end: number; text: string; original: string }[]
  speakers: { at: number; name: string; role: string }[]
  tags: { at: number; text: string }[]; tags_enabled: boolean
  highlights: { at: number; text: string }[]
  burned_captions: boolean; fallback: boolean
  style?: 'classic' | 'boxed' | 'spotlight' | 'pop' | 'cinematic' | null
  mood?: 'calm' | 'serious' | 'bold' | 'warm' | 'playful' | null
  palette?: 'azure' | 'amber' | 'coral' | 'mint' | 'lemon' | 'rose' | 'lilac' | null
}
export interface Draft {
  id: string; title: string; hook: string; scenes: Scene[]; language: Language
  aspect: 'original' | 'portrait' | 'landscape'; layout: 'fit' | 'crop' | 'blur' | 'window'
  crop_x?: number; title_style?: 'plain' | 'impact' | 'card' | 'comic' | 'neon' | 'arena' | 'editorial' | 'pixel' | 'frosted'
  title_template_version?: 1 | 2 | 3 | 4 | 5 | 6; title_motion?: boolean; title_scale?: number; title_y?: number; title_accent?: string | null
  subtitles: boolean; subtitle_style?: SubtitleStyle; original_audio: boolean; revision: number; updated_at: string; origin: string
  parent_draft_id?: string | null; parent_revision?: number | null
  /** Automatic template packaging; kept as-is on save so edits never drop it. */
  packaging?: Packaging | null
}
export interface RenderJob {
  job_id: string; draft_id: string; title: string; revision: number
  status: 'queued' | 'running' | 'completed' | 'failed'; percent: number; created_at: string; error?: string
  brand_outro?: boolean
  result?: { width: number; height: number; duration: number; warnings: string[]; outro_applied?: boolean }
}
export interface OutputVariant {
  id: string; draft_id: string; draft_revision: number; strategy_id: string; strategy_version: number
  branding: { outro_enabled: boolean; outro_version: string }
  status: 'queued' | 'running' | 'completed' | 'failed' | 'on_demand' | 'preparing'; render_job_id?: string; created_at: string; error?: string
  trimmed_to_sec?: number
  framing?: 'speaker' | 'full_frame' | 'full_frame_pending' | 'full_frame_captions'
  /** Publish kit: copy written for this platform, and a cover designed (or AI-made) after the render. */
  post?: PostCopy | null
  cover?: 'design' | 'ai' | null
  cover_job?: { job_id: string; status: 'queued' | 'running' | 'completed' | 'failed'; error?: string } | null
}
export interface PostCopy { title: string; description: string; tags: string[] }
export interface GenerationState {
  requested_platforms: string[]; branding: { outro_enabled: boolean; outro_version: string }
  auto_start: boolean; status: 'screening' | 'awaiting_confirmation' | 'production' | 'rendering' | 'completed' | 'partial' | 'failed'
  created_at: string; skipped?: { strategy_id: string; reason: string }[]; error?: string; completed_variant_count?: number
}
export interface PlatformStrategySummary {
  id: string; label: string; aspect: 'portrait' | 'landscape' | 'original'; duration_policy: 'short' | 'long' | 'adaptive'
  min_recommended_duration_sec: number | null; max_duration_sec: number | null
  transport: 'download_only' | 'upload_post' | 'bilibili_direct'; transport_platform: string | null
}

export interface Workspace {
  schema_version?: number; plan?: ImportPlan
  drafts: Draft[]; events: Scene[]; jobs: RenderJob[]; output_variants?: OutputVariant[]; generation?: GenerationState
  analysis: null | { status: 'running' | 'awaiting_confirmation' | 'completed' | 'failed'; phase?: 'screening' | 'production' | 'rendering'; message?: string; percent?: number; error?: string; coverage?: { duration?:number; note: string; sample_interval: number }; outcome?: 'completed' | 'partial' | 'failed' }
}
export const languages = [{ value: 'source', label: '原语言' }, { value: 'zh', label: '简体中文' }, { value: 'en', label: 'English' }, { value: 'ja', label: '日本語' }] as const
export const emptyWorkspace: Workspace = { drafts: [], events: [], jobs: [], analysis: null }
export function draftDuration(draft: Draft) { return draft.scenes.reduce((sum, scene) => sum + scene.end - scene.start, 0) }
export function draftError(draft: Draft, sourceDuration?: number): string | null {
  if (!draft.title.trim()) return '请填写成片标题'
  if (!draft.scenes.length) return '至少保留一个镜头'
  if (draft.scenes.length > 30) return '单条成片最多 30 个镜头'
  if (draft.scenes.some(s => !Number.isFinite(s.start) || !Number.isFinite(s.end) || s.start < 0 || s.end - s.start < .1)) return '镜头起止无效，每段至少 0.1 秒'
  if (sourceDuration !== undefined && draft.scenes.some(s => s.end > sourceDuration + .05)) return '镜头终点超出原视频时长'
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

export function applyCandidate(draft: Draft, candidate: Candidate, target: number | 'append', newId: string): Draft {
  const scene: Scene = { id: newId, label: candidate.label, start: candidate.start, end: candidate.end, evidence: candidate.evidence }
  if (target !== 'append' && (target < 0 || target >= draft.scenes.length)) throw new Error('要替换的镜头已不存在')
  const scenes = target === 'append' ? [...draft.scenes, scene] : draft.scenes.map((s, i) => i === target ? scene : s)
  const result = { ...draft, scenes }
  const invalid = draftError(result)
  if (invalid) throw new Error(invalid)
  return result
}

/** Phone-friendly defaults: fill the frame and use large captions. The title look only changes when there is an opening title. */
export function portraitDesign(draft: Draft): Draft {
  const withTitle = draft.hook.trim() ? { title_style: 'comic' as const, title_template_version: 6 as const } : {}
  return {...draft, aspect:'portrait', layout:'crop', crop_x:draft.crop_x ?? .5, subtitle_style: 'bold', ...withTitle}
}

export interface ImportOptions {
  goal: 'auto' | Goal; language: Language; aspect: Draft['aspect'] | null
  duration: number | null; instruction: string
  portrait_style?: 'auto' | 'interview' | 'podcast'
}
export type AnalysisMode = 'subtitle' | 'visual'
export interface AnalysisPreferences { analysis_mode: AnalysisMode | 'auto'; allow_visual_screening: boolean }
export interface ImportPlan {
  aspect?: Draft['aspect']
  recommended_analysis?: AnalysisMode; confirmed_analysis?: AnalysisMode

  id: string; source_duration?:number; suggested_goals: Goal[]; selected_goals?: Goal[]
  mode: 'ai' | 'manual' | 'fallback' | 'local'; content_type: string; reason: string; confidence: number
  preferences: {goal: Goal; language: Language; aspect: Draft['aspect']; duration: number}
  overrides: ImportOptions
}
export const defaultImportOptions: ImportOptions = {goal:'auto', language:'source', aspect:null, duration:null, instruction:'', portrait_style:'auto'}
export const goalLabels = {auto:'AI 自动匹配', content:'内容切片', highlight:'精彩高光', promo:'推广成片'} as const
