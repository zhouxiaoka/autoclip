import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import { featureSnapshot, flagEnabled } from '../../analytics/flags'
import { telemetryId } from '../../analytics/workflow'
import { studioApi } from './api'
import { submissionBlock } from './importReadiness'
import { batchImportBody, BatchImportQueue, hasImportOperationRandom, isBatchProjectId, type BatchItem } from './batchImportQueue'
import PlatformPicker from './PlatformPicker'
import ImportPreferences from './ImportPreferences'
import { templateImportFields } from './TemplatePicker'
import { hasSuccessHistory } from './platformMemory'
import type { GenerationState } from './types'

export const batchSession = new BatchImportQueue()
const guard = (event: BeforeUnloadEvent) => {
  if (!batchSession.items.some(item => ['waiting', 'blocked', 'uploading', 'unknown'].includes(item.status))) return
  event.preventDefault(); event.returnValue = ''
}
// The guard outlives the route, just like the in-memory File objects. A restart requires re-selection.
if (typeof window !== 'undefined') window.addEventListener('beforeunload', guard)

function duration(file: File): Promise<number | null> {
  return new Promise(resolve => {
    let url = '', done = false
    const video = document.createElement('video')
    const finish = (seconds: number | null) => {
      if (done) return; done = true
      clearTimeout(timer); video.onloadedmetadata = null; video.onerror = null
      video.removeAttribute('src'); video.load()
      if (url) URL.revokeObjectURL(url)
      resolve(seconds)
    }
    const timer = setTimeout(() => finish(null), 5000)
    video.onloadedmetadata = () => finish(Number.isFinite(video.duration) && video.duration > 0 ? video.duration : null)
    video.onerror = () => finish(null)
    try { url = URL.createObjectURL(file); video.preload = 'metadata'; video.src = url }
    catch { finish(null) }
  })
}

export default function BatchVideoImport({ onClose, onImported }: { onClose: () => void; onImported: () => Promise<void> }) {
  useTranslation()
  const navigate = useNavigate()
  const [, refresh] = useState(0)
  const [agreed, setAgreed] = useState(false)
  const [longAgreed, setLongAgreed] = useState(false)
  const [error, setError] = useState('')
  const [states, setStates] = useState<Record<string, GenerationState['status']>>({})
  const queue = batchSession
  const settings = queue.settings!
  useEffect(() => {
    const unsubscribe = queue.subscribe(() => refresh(value => value + 1))
    return () => { unsubscribe(); queue.pause() }
  }, [queue])
  useEffect(() => {
    let active = true
    for (const item of queue.items.filter(value => value.status === 'waiting' && value.duration === null)) {
      void duration(item.file).then(seconds => { if (active) queue.change(item.id, { duration: seconds }) })
    }
    return () => { active = false }
  }, [queue])
  useEffect(() => {
    let active = true, inFlight = false
    let controller: AbortController | null = null
    const poll = async () => {
      if (inFlight) return
      inFlight = true; controller = new AbortController()
      const signal = controller.signal
      const timeout = setTimeout(() => controller?.abort(), 10000)
      const submitted = queue.items.filter(item => item.status === 'submitted' && item.projectId)
      try { await Promise.all(submitted.map(async item => {
        try {
          const workspace = await studioApi.get(item.projectId!, signal)
          if (active && workspace.generation?.status) setStates(previous => ({ ...previous, [item.projectId!]: workspace.generation!.status }))
        } catch { /* A failed read is not a failed production or permission to re-import. */ }
      })) } finally { clearTimeout(timeout); inFlight = false }
    }
    void poll()
    const timer = setInterval(() => void poll(), 5000)
    return () => { active = false; controller?.abort(); clearInterval(timer) }
  }, [queue])

  const start = async () => {
    if (!agreed || queue.running) return
    if (!settings.platforms.length) { setError('batchImport.platforms'); return }
    if (settings.platforms.includes('youtube_long') && !longAgreed) { setError('batchImport.longConfirm'); return }
    setError('')
    await queue.start(async (item, snapshot) => {
      // Each file has its own window decision. Unknown metadata never means automatic whole-file consent.
      const first = !hasSuccessHistory() && (item.duration === null || item.duration > 1800)
      if (item.window === 'review' && first) return { status: 'blocked', issue: 'batchImport.windowRequired' }
      if (snapshot.platforms.every(platform => platform === 'youtube_long') && item.duration !== null && item.duration < 180) {
        return { status: 'blocked', issue: 'batchImport.tooShort' }
      }
      let report
      try { report = await studioApi.readiness() }
      catch { return { status: 'blocked', issue: 'batchImport.readinessUnknown' } }
      if (!report?.checks?.analysis || !report.checks.transcription || !report.checks.visual || !report.checks.ffmpeg) {
        return { status: 'blocked', issue: 'batchImport.readinessUnknown' }
      }
      if (report.batch_import_receipts !== true) return { status: 'blocked', issue: 'batchImport.backendUpgradeRequired' }
      const reason = submissionBlock(report, !!item.subtitle, true, { source: 'file' })
      if (reason) return { status: 'blocked', issue: `batchImport.${reason}` }
      if (!queue.maySubmit()) return { status: 'blocked', issue: 'batchImport.paused' }
      if (!hasImportOperationRandom()) return { status: 'blocked', issue: 'batchImport.secureRandomUnavailable' }
      const template = templateImportFields(flagEnabled('pkg_templates_v1'), snapshot.options.html_template, undefined).html_template
      const body = batchImportBody(item, snapshot, telemetryId(), featureSnapshot(), template)
      try {
        const receipt = await studioApi.import(body)
        // Invalid/lost receipts may already have created a project; initial upload cannot be replayed safely.
        if (!isBatchProjectId(receipt?.project_id)) return { status: 'unknown', issue: 'batchImport.unknownHint' }
        void onImported().catch(() => undefined)
        return { projectId: receipt.project_id }
      } catch (error) {
        const response = (error as { response?: { status?: number; data?: { detail?: { import_state?: unknown } } } } | null)?.response
        if (response?.data?.detail?.import_state === 'unknown') return { status: 'unknown', issue: 'batchImport.unknownHint' }
        if (typeof response?.status === 'number') return { status: 'failed', issue: 'batchImport.failedHint' }
        return { status: 'unknown', issue: 'batchImport.unknownHint' }
      }
    })
  }
  const chooseSubtitle = (item: BatchItem, picked?: File) => {
    if (!picked) return
    if (!picked.name.toLowerCase().endsWith('.srt') || !picked.size || picked.size > 2 * 1024 * 1024) {
      setError('batchImport.subtitleInvalid'); return
    }
    setError(''); queue.change(item.id, { subtitle: picked })
  }
  const editable = (item: BatchItem) => !queue.running && ['waiting', 'blocked'].includes(item.status)
  return <section className="ac-creative-import" aria-labelledby="batch-import-title">
    <h1 id="batch-import-title" className="ac-title">{t('batchImport.title')}</h1>
    <p className="studio-muted">{t('batchImport.hint')}</p>
    <p className="studio-muted" role="note">{t('batchImport.lifecycle')}</p>
    <div className="studio-import-box">
      <PlatformPicker value={settings.platforms} disabled={queue.running} onChange={platforms => {
        if (queue.running) return
        settings.platforms = [...platforms]; setAgreed(false); setLongAgreed(false); queue.notify()
      }} />
      <details className="studio-details"><summary>{t('batchImport.options')}</summary>
        <fieldset disabled={queue.running} style={{ border: 0, padding: 0, margin: 0 }}>
          <ImportPreferences value={settings.options} onChange={options => {
            if (queue.running) return
            settings.options = { ...options, source_window: null }; setAgreed(false); queue.notify()
          }} />
        </fieldset>
      </details>
      <ol className="batch-import-list">
        {queue.items.map(item => <li key={item.id} data-batch-id={item.id} className="studio-file" style={{ flexWrap: 'wrap', marginBlock: 12 }}>
          <strong style={{ overflowWrap: 'anywhere' }}>{item.file.name}</strong>
          <span role="status">{t(`batchImport.status.${item.status}`)}{item.projectId && states[item.projectId] ? ` · ${t(`batchImport.production.${states[item.projectId]}`)}` : ''}</span>
          {item.issue && <p className="studio-error" role="alert">{t(item.issue)}</p>}
          {editable(item) && <>
            <label className="studio-field">{t('batchImport.window')}
              <select value={item.window} onChange={event => queue.change(item.id, { window: event.target.value as BatchItem['window'] })}>
                <option value="review">{t('batchImport.windowAuto')}</option><option value="first">{t('batchImport.windowFirst')}</option><option value="full">{t('batchImport.windowFull')}</option>
              </select>
            </label>
            <label className="studio-link">{item.subtitle ? item.subtitle.name : t('batchImport.subtitle')}<input type="file" aria-label={t('batchImport.subtitle')} accept=".srt" onChange={event => { chooseSubtitle(item, event.target.files?.[0]); event.target.value = '' }} /></label>
            {item.subtitle && <Btn size="sm" onClick={() => queue.change(item.id, { subtitle: null })}>{t('batchImport.removeSubtitle')}</Btn>}
          </>}
          {['waiting', 'blocked'].includes(item.status) && <Btn size="sm" onClick={() => queue.cancel(item.id)}>{t('batchImport.cancelItem')}</Btn>}
          {item.projectId && <Btn size="sm" onClick={() => { queue.pause(); navigate(`/project/${item.projectId}`) }}>{t('batchImport.project')}</Btn>}
        </li>)}
      </ol>
      <label className="studio-field"><span><input type="checkbox" checked={agreed} disabled={queue.running} onChange={event => setAgreed(event.target.checked)} /> {t('batchImport.consent')}</span></label>
      {settings.platforms.includes('youtube_long') && <label className="studio-field"><span><input type="checkbox" checked={longAgreed} disabled={queue.running} onChange={event => setLongAgreed(event.target.checked)} /> {t('batchImport.longConfirm')}</span></label>}
      {error && <p className="studio-error" role="alert">{t(error)}</p>}
      <div className="studio-actions">
        <Btn variant="cta" loading={queue.running} disabled={!agreed || queue.running || !queue.items.some(item => ['waiting', 'blocked'].includes(item.status))} onClick={() => void start()}>{t('batchImport.start')}</Btn>
        {queue.running && <Btn onClick={queue.pause}>{t('batchImport.pause')}</Btn>}
        <Btn disabled={queue.running} onClick={() => navigate('/settings?section=ai&return_import=1')}>{t('batchImport.settings')}</Btn>
        <Btn disabled={queue.running} onClick={() => { queue.clear(); onClose() }}>{t('batchImport.clear')}</Btn>
      </div>
    </div>
  </section>
}
