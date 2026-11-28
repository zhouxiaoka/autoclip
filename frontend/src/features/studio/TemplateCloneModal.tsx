import { useEffect, useRef, useState } from 'react'
import { Modal } from 'antd'
import { t } from '../../i18n'
import {
  trackTemplateCloneCompleted,
  trackTemplateCloneRefined,
  trackTemplateCloneSaved,
  trackTemplateCloneStarted,
} from '../../analytics/studio'
import {
  fetchCloneReadiness,
  getTemplateCloneJob,
  refineTemplateClone,
  resolveTemplateAssetUrl,
  revertTemplateClone,
  saveTemplateClone,
  startTemplateClone,
  type CloneJobState,
} from './templateCatalogClient'
import './TemplateCloneModal.css'

const SWATCHES = ['#FFE548', '#34D399', '#2D6BFF', '#FF4D4F'] as const

type Props = {
  open: boolean
  onClose: () => void
  onSaved: (templateId: string) => void
}

export default function TemplateCloneModal({ open, onClose, onSaved }: Props) {
  const [referenceUrl, setReferenceUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [promptHint, setPromptHint] = useState('')
  const [depthMode, setDepthMode] = useState<'auto' | 'on' | 'off'>('auto')
  const [readiness, setReadiness] = useState<{ vision_capable: boolean; model: string }>({ vision_capable: false, model: '' })

  const [job, setJob] = useState<CloneJobState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewLang, setPreviewLang] = useState<'zh' | 'en'>('zh')
  const [comparingRef, setComparingRef] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [nameZh, setNameZh] = useState('')
  const [nameEn, setNameEn] = useState('')
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const startedAtRef = useRef<number>(0)

  useEffect(() => {
    if (!open) return
    void fetchCloneReadiness().then(setReadiness)
  }, [open])

  useEffect(() => {
    if (!open || !job || job.status !== 'running') return
    const timer = window.setInterval(async () => {
      try {
        const next = await getTemplateCloneJob(job.job_id)
        setJob(next)
        if (next.status === 'ready' && next.blueprint) {
          setNameZh(next.blueprint.name_zh || '')
          setNameEn(next.blueprint.name_en || '')
          trackTemplateCloneCompleted({
            outcome: 'success',
            duration_ms: startedAtRef.current ? Math.max(0, Date.now() - startedAtRef.current) : undefined,
          })
        } else if (next.status === 'failed') {
          setError(next.error || t('editing_style.clone.failed'))
          trackTemplateCloneCompleted({
            outcome: 'error',
            duration_ms: startedAtRef.current ? Math.max(0, Date.now() - startedAtRef.current) : undefined,
          })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : t('editing_style.clone.failed'))
      }
    }, 1200)
    return () => window.clearInterval(timer)
  }, [open, job])

  const resetAll = () => {
    setJob(null)
    setError(null)
    setBusy(false)
    setInstruction('')
    setComparingRef(false)
  }

  const handleClose = () => {
    resetAll()
    onClose()
  }

  const handleStart = async () => {
    if (!referenceUrl.trim() && !file && !promptHint.trim()) {
      setError(t('editing_style.clone.input_required'))
      return
    }
    setBusy(true)
    setError(null)
    startedAtRef.current = Date.now()
    const sourceKind = file ? 'file' : referenceUrl.trim() ? 'link' : 'none'
    trackTemplateCloneStarted({ source_kind: sourceKind })
    try {
      const started = await startTemplateClone({
        referenceUrl: referenceUrl.trim(),
        file,
        promptHint: promptHint.trim(),
        depthMode,
      })
      setJob(started)
      if (started.status === 'ready' && started.blueprint) {
        setNameZh(started.blueprint.name_zh || '')
        setNameEn(started.blueprint.name_en || '')
        trackTemplateCloneCompleted({
          outcome: 'success',
          duration_ms: Math.max(0, Date.now() - startedAtRef.current),
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('editing_style.clone.failed'))
      trackTemplateCloneCompleted({
        outcome: 'error',
        duration_ms: Math.max(0, Date.now() - startedAtRef.current),
      })
    } finally {
      setBusy(false)
    }
  }

  const handleRefine = async (opts: { variableOverrides?: Record<string, unknown>; instruction?: string }) => {
    if (!job) return
    setBusy(true)
    setError(null)
    try {
      const updated = await refineTemplateClone(job.job_id, opts)
      setJob(updated)
      trackTemplateCloneRefined({ trigger: opts.instruction ? 'manual' : 'select' })
      if (updated.blueprint) {
        setNameZh(updated.blueprint.name_zh || nameZh)
        setNameEn(updated.blueprint.name_en || nameEn)
      }
      if (opts.instruction) setInstruction('')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('editing_style.clone.failed'))
    } finally {
      setBusy(false)
    }
  }

  const handleRevert = async () => {
    if (!job || !job.can_undo) return
    setBusy(true)
    setError(null)
    try {
      const prev = await revertTemplateClone(job.job_id)
      setJob(prev)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('editing_style.clone.failed'))
    } finally {
      setBusy(false)
    }
  }

  const handleSave = async () => {
    if (!job) return
    setBusy(true)
    setError(null)
    try {
      const saved = await saveTemplateClone(job.job_id, { nameZh: nameZh.trim(), nameEn: nameEn.trim() })
      trackTemplateCloneSaved({ template: saved.installed })
      resetAll()
      onSaved(saved.installed)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('editing_style.clone.failed'))
      setBusy(false)
    }
  }

  const stepNum = !job ? 1 : job.status === 'ready' ? 3 : 2
  const bp = job?.blueprint
  const activeVideoUrl = resolveTemplateAssetUrl(previewLang === 'en' ? (job?.preview_en_url || job?.preview_zh_url) : job?.preview_zh_url)
  const refFrameUrl = job?.frames?.[0] ? resolveTemplateAssetUrl(job.frames[0]) : null

  return (
    <Modal
      open={open}
      onCancel={handleClose}
      footer={null}
      closable={false}
      width={820}
      className="ac-clone-modal"
      destroyOnClose
    >
      <div className="ac-clone-head">
        <div className="ac-clone-head-l">
          <h3>
            {stepNum === 1
              ? t('editing_style.clone.title')
              : stepNum === 2
                ? t('editing_style.clone.generating')
                : t('editing_style.clone.preview_title')}
          </h3>
          <span className="ac-clone-step">{stepNum} / 3</span>
        </div>
        <button type="button" className="ac-clone-close" aria-label="Close" onClick={handleClose}>×</button>
      </div>

      {stepNum === 1 ? (
        <>
          <div className="ac-clone-body">
            <div className="ac-clone-drop">
              <h4>{t('editing_style.clone.drop_title')}</h4>
              <div className="ac-clone-url-row">
                <input
                  className="ac-clone-input"
                  value={referenceUrl}
                  onChange={e => setReferenceUrl(e.target.value)}
                  placeholder="https://..."
                />
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/mp4,video/quicktime,video/webm"
                  style={{ display: 'none' }}
                  onChange={e => setFile(e.target.files?.[0] || null)}
                />
                <button type="button" className="ac-clone-pill" onClick={() => fileInputRef.current?.click()}>
                  {file ? file.name.slice(0, 14) : t('editing_style.clone.pick_file')}
                </button>
              </div>
              <div className="ac-clone-sub">{t('editing_style.clone.platforms')}</div>
            </div>

            <div className="ac-clone-opts">
              <div className="ac-clone-inline">
                <span>{t('editing_style.clone.depth')}</span>
                <div className="ac-clone-seg">
                  {(['auto', 'on', 'off'] as const).map(mode => (
                    <button key={mode} type="button" className={depthMode === mode ? 'is-on' : ''} onClick={() => setDepthMode(mode)}>
                      {t(`editing_style.clone.depth_${mode}`)}
                    </button>
                  ))}
                </div>
              </div>
              <input
                className="ac-clone-input"
                value={promptHint}
                onChange={e => setPromptHint(e.target.value)}
                placeholder={t('editing_style.clone.hint_placeholder')}
              />
            </div>

            {error ? <div className="ac-clone-err">{error}</div> : null}
          </div>

          <div className="ac-clone-foot">
            <span className={`ac-clone-status${readiness.vision_capable ? '' : ' is-warn'}`}>
              <i aria-hidden="true" />
              {readiness.vision_capable
                ? `${readiness.model || 'Vision'} · ${t('editing_style.clone.ready')}`
                : t('editing_style.clone.text_only_hint')}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" className="ac-clone-pill" onClick={handleClose}>{t('editing_style.clone.cancel')}</button>
              <button type="button" className="ac-clone-pill is-primary" disabled={busy} onClick={() => void handleStart()}>
                {t('editing_style.clone.start')}
              </button>
            </div>
          </div>
        </>
      ) : null}

      {stepNum === 2 && job ? (
        <div className="ac-clone-split">
          <div className="ac-clone-stage">
            <div className="ac-clone-frames">
              {(job.frames.length ? job.frames : Array.from({ length: 6 }, () => '')).map((src, i) => (
                <div key={i} className="ac-clone-frame">
                  {src ? <img src={resolveTemplateAssetUrl(src) || ''} alt="" /> : null}
                </div>
              ))}
            </div>
          </div>
          <div className="ac-clone-right">
            <div>
              <ol className="ac-clone-prog">
                <li>
                  <span className={`ac-clone-dot ${job.step === 'extract' ? 'is-active' : 'is-done'}`}>
                    {job.step === 'extract' ? '1' : '✓'}
                  </span>
                  <span>{t('editing_style.clone.step_extract')}</span>
                </li>
                <li>
                  <span className={`ac-clone-dot ${job.step === 'analyze' ? 'is-active' : job.step === 'render' ? 'is-done' : ''}`}>
                    {job.step === 'render' ? '✓' : '2'}
                  </span>
                  <span>{t('editing_style.clone.step_analyze')}</span>
                </li>
                <li>
                  <span className={`ac-clone-dot ${job.step === 'render' ? 'is-active' : ''}`}>3</span>
                  <span>{t('editing_style.clone.step_render')}</span>
                </li>
              </ol>
              {error ? <div className="ac-clone-err" style={{ marginTop: 14 }}>{error}</div> : null}
            </div>
            <div className="ac-clone-save-bar">
              <span />
              <button type="button" className="ac-clone-pill" onClick={resetAll}>{t('editing_style.clone.cancel')}</button>
            </div>
          </div>
        </div>
      ) : null}

      {stepNum === 3 && job && bp ? (
        <div className="ac-clone-split">
          <div className="ac-clone-stage">
            <div className="ac-clone-phone">
              {comparingRef && refFrameUrl ? (
                <img src={refFrameUrl} alt="" />
              ) : activeVideoUrl ? (
                <video key={activeVideoUrl} src={activeVideoUrl} autoPlay loop muted playsInline />
              ) : null}
            </div>
            <div className="ac-clone-stage-bar">
              <div className="ac-clone-stage-seg">
                <button type="button" className={previewLang === 'zh' ? 'is-on' : ''} onClick={() => setPreviewLang('zh')}>{t('editing_style.clone.lang_zh')}</button>
                <button type="button" className={previewLang === 'en' ? 'is-on' : ''} onClick={() => setPreviewLang('en')}>EN</button>
              </div>
              {refFrameUrl ? (
                <button
                  type="button"
                  className="ac-clone-stage-btn"
                  onMouseDown={() => setComparingRef(true)}
                  onMouseUp={() => setComparingRef(false)}
                  onMouseLeave={() => setComparingRef(false)}
                >
                  {t('editing_style.clone.compare')}
                </button>
              ) : null}
            </div>
          </div>

          <div className="ac-clone-right">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              <div>
                <div className="ac-clone-sec-row"><span className="ac-clone-sec-lbl">{t('editing_style.clone.style_vars')}</span></div>
                <div className="ac-clone-vars">
                  <div className="ac-clone-var-cell">
                    <span>{t('editing_style.clone.accent')}</span>
                    <div className="ac-clone-swatches">
                      {SWATCHES.map(hex => (
                        <button
                          key={hex}
                          type="button"
                          className={`ac-clone-sw${bp.accent_color.toUpperCase() === hex ? ' is-on' : ''}`}
                          style={{ background: hex }}
                          disabled={busy}
                          onClick={() => void handleRefine({ variableOverrides: { accent_color: hex } })}
                        />
                      ))}
                    </div>
                  </div>
                  <div className="ac-clone-var-cell">
                    <span>{t('editing_style.clone.font_size')}</span>
                    <div className="ac-clone-seg">
                      {(['S', 'M', 'L'] as const).map(sz => (
                        <button
                          key={sz}
                          type="button"
                          className={bp.font_scale === sz ? 'is-on' : ''}
                          disabled={busy}
                          onClick={() => void handleRefine({ variableOverrides: { font_scale: sz } })}
                        >
                          {sz}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="ac-clone-var-cell">
                    <span>{t('editing_style.clone.depth')}</span>
                    <button
                      type="button"
                      className={`ac-clone-toggle${bp.depth_enabled ? ' is-on' : ''}`}
                      disabled={busy}
                      onClick={() => void handleRefine({ variableOverrides: { depth_enabled: !bp.depth_enabled } })}
                    />
                  </div>
                  <div className="ac-clone-var-cell">
                    <span>{t('editing_style.clone.grain')}</span>
                    <button
                      type="button"
                      className={`ac-clone-toggle${bp.grain_enabled ? ' is-on' : ''}`}
                      disabled={busy}
                      onClick={() => void handleRefine({ variableOverrides: { grain_enabled: !bp.grain_enabled } })}
                    />
                  </div>
                </div>
              </div>

              <div>
                <div className="ac-clone-sec-row">
                  <span className="ac-clone-sec-lbl">{t('editing_style.clone.refine')}</span>
                  {job.can_undo ? (
                    <button type="button" className="ac-clone-pill" style={{ height: 24, padding: '0 10px', fontSize: 11.5 }} disabled={busy} onClick={() => void handleRevert()}>
                      ↩ {t('editing_style.clone.undo')}
                    </button>
                  ) : null}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    className="ac-clone-input"
                    value={instruction}
                    onChange={e => setInstruction(e.target.value)}
                    placeholder={t('editing_style.clone.refine_placeholder')}
                    onKeyDown={e => { if (e.key === 'Enter' && instruction.trim()) void handleRefine({ instruction }) }}
                  />
                  <button type="button" className="ac-clone-pill" disabled={busy || !instruction.trim()} onClick={() => void handleRefine({ instruction })}>
                    {t('editing_style.clone.apply')}
                  </button>
                </div>
              </div>

              <div>
                <div className="ac-clone-sec-row"><span className="ac-clone-sec-lbl">{t('editing_style.clone.name')}</span></div>
                <div className="ac-clone-row2">
                  <input className="ac-clone-input" value={nameZh} onChange={e => setNameZh(e.target.value)} placeholder={t('editing_style.clone.name_zh_ph')} />
                  <input className="ac-clone-input" value={nameEn} onChange={e => setNameEn(e.target.value)} placeholder="English Name" />
                </div>
              </div>

              {error ? <div className="ac-clone-err">{error}</div> : null}
            </div>

            <div className="ac-clone-save-bar">
              <button type="button" className="ac-clone-pill" disabled={busy} onClick={resetAll}>{t('editing_style.clone.redo')}</button>
              <button type="button" className="ac-clone-pill is-primary" disabled={busy} onClick={() => void handleSave()}>
                {t('editing_style.clone.save_use')}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </Modal>
  )
}
