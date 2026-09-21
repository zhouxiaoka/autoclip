import { useEffect, useRef, useState } from 'react'
import { Btn, Dialog, fmtDuration } from '../../ui'
import { studioApi, errorText } from './api'
import { Candidate, CandidateList } from './types'

interface Props {
  projectId: string
  mode: 'append' | 'replace'
  onClose: () => void
  onChoose: (candidate: Candidate) => void
}

export default function CandidatePicker({ projectId, mode, onClose, onChoose }: Props) {
  const [data, setData] = useState<CandidateList | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const [selected, setSelected] = useState<Candidate | null>(null)
  const video = useRef<HTMLVideoElement>(null)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    studioApi.candidates(projectId, controller.signal).then(result => {
      if (!controller.signal.aborted) { setData(result); setSelected(result.candidates[0] || null) }
    }).catch(e => { if (!controller.signal.aborted) setError(errorText(e)) }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [projectId, version])
  useEffect(() => {
    if (video.current && selected) { video.current.pause(); video.current.currentTime = selected.start }
  }, [selected?.id])
  return <Dialog open title={mode === 'append' ? '追加一个镜头' : '替换当前镜头'} onClose={onClose}
    description="从当前素材的高光和已有切片中选择。先预览，再加入成片；修改保存后生效。"
    footer={<div className="studio-actions"><Btn onClick={onClose}>取消</Btn><Btn variant="cta" disabled={!selected || loading || !!error} onClick={() => selected && onChoose(selected)}>{mode === 'append' ? '追加到成片' : '替换镜头'}</Btn></div>}>
    {loading ? <p className="studio-muted">加载可用片段…</p> : error ? <div role="alert"><p className="studio-error">{error}</p><Btn onClick={() => setVersion(v => v + 1)}>重试</Btn></div> : <>
      {selected && <><video ref={video} className="studio-candidate-video" controls preload="metadata" src={studioApi.source(projectId)}
        onLoadedMetadata={() => { if (video.current) video.current.currentTime = selected.start }}
        onTimeUpdate={() => { const v = video.current; if (v && v.currentTime >= selected.end) { v.pause(); v.currentTime = selected.start } }} />
        <p className="studio-muted">原片 {selected.start.toFixed(1)}–{selected.end.toFixed(1)} 秒 · {selected.evidence || '请核对镜头起止和玩法完整性。'}</p></>}
      {data?.warnings.map(w => <p className="studio-muted" key={w}>{w}</p>)}
      {!data?.candidates.length && <p className="studio-muted">当前没有可用候选。可返回项目重新分析，或调整已有镜头的起止时间。</p>}
      <div className="studio-candidate-list" role="radiogroup" aria-label="候选片段">{data?.candidates.map(c => <label className="studio-candidate-option" key={c.id}>
        <input type="radio" name="candidate" checked={selected?.id === c.id} onChange={() => setSelected(c)} />
        <span><b>{c.label}</b><small>{c.kind === 'visual' ? '视觉高光' : '已有切片'} · {c.start.toFixed(1)}–{c.end.toFixed(1)} 秒 · {fmtDuration(c.end - c.start)}</small></span>
      </label>)}</div>
    </>}
  </Dialog>
}
