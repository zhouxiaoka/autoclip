import { useEffect, useState } from 'react'
import { projectApi } from '../../services/api'
import { Btn, Dialog, ProgressLine, Row, Segmented } from '../../ui'
import { useClipExport } from './useClipExport'

interface Props {
  open: boolean
  onClose: () => void
  projectId: string
  clipId: string
}

export function ClipExportDialog({ open, onClose, projectId, clipId }: Props) {
  const [preset, setPreset] = useState<'douyin' | 'xiaohongshu' | 'shorts' | 'bilibili' | 'original'>('douyin')
  const [burnSub, setBurnSub] = useState(true)
  const [titleCard, setTitleCard] = useState(true)
  const { exporting, percent, error, result, start, reset } = useClipExport(projectId, clipId)

  useEffect(() => { if (open) reset() }, [open, reset])

  return (
    <Dialog
      open={open}
      onClose={() => !exporting && onClose()}
      title="发布导出"
      description="渲成可直接上传的成片。默认流水线的切片不受影响。"
      footer={
        <div className="right" style={{ marginLeft: 'auto' }}>
          <Btn size="sm" onClick={onClose} disabled={exporting}>取消</Btn>
          {result ? (
            <Btn size="sm" variant="cta" onClick={() => projectApi.downloadExport(projectId, result.jobId)}>
              下载成片
            </Btn>
          ) : (
            <Btn size="sm" variant="cta" loading={exporting} onClick={() => void start({ preset, subtitles: burnSub, title_card: titleCard })}>开始导出</Btn>
          )}
        </div>
      }
    >
      <Row label="平台" hint="画幅与时长按平台规格">
        <Segmented
          size="sm"
          ariaLabel="导出预设"
          value={preset}
          onChange={setPreset}
          options={[
            { value: 'douyin', label: '抖音' },
            { value: 'xiaohongshu', label: '小红书' },
            { value: 'shorts', label: 'Shorts' },
            { value: 'bilibili', label: 'B 站' },
            { value: 'original', label: '原画' },
          ]}
        />
      </Row>
      <Row label="字幕" hint="从原字幕切出本段并烧进画面">
        <Segmented size="sm" value={burnSub ? 'on' : 'off'} onChange={(v) => setBurnSub(v === 'on')}
          options={[{ value: 'on', label: '烧录' }, { value: 'off', label: '不要' }]} />
      </Row>
      <Row label="标题卡" hint="片头约 4 秒显示切片标题">
        <Segmented size="sm" value={titleCard ? 'on' : 'off'} onChange={(v) => setTitleCard(v === 'on')}
          options={[{ value: 'on', label: '显示' }, { value: 'off', label: '不要' }]} />
      </Row>
      {exporting && <div style={{ marginTop: 16 }}><ProgressLine percent={percent} /></div>}
      {error && <p style={{ marginTop: 12, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}
      {result && (
        <p style={{ marginTop: 12, color: 'var(--ac-sub)', fontSize: 13 }}>
          已完成{result.warnings?.length ? ` · ${result.warnings.join('；')}` : ''}
        </p>
      )}
    </Dialog>
  )
}
