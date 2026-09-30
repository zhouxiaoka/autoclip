import { Switch } from 'antd'
import { t } from '../../i18n'
import { Row } from '../../ui'
import { packagingLabel } from './packagingLabel'
import type { Draft, Packaging } from './types'

const TITLE_MAX = { zh: 12, en: 36 }

/**
 * Editing for automatic template packaging. This release only allows the two title lines and
 * the editor tags switch; captions, nameplates and tags themselves come from the template.
 */
export default function PackagingSettings({ draft, patch }: { draft: Draft; patch: (changes: Partial<Draft>) => void }) {
  const packaging = draft.packaging
  if (!packaging) return null
  const max = TITLE_MAX[packaging.audience_language]
  const lines = [packaging.title_lines[0] ?? '', packaging.title_lines[1] ?? '']
  const update = (changes: Partial<Packaging>) => patch({ packaging: { ...packaging, ...changes } })
  const setLine = (index: number, value: string) => {
    const next = [...lines]
    next[index] = value.slice(0, max)
    update({ title_lines: next.filter(line => line.trim()) })
  }
  return <>
    <Row stack label={t('模板')} hint={t('字幕、名牌和版式由模板按发布平台自动生成。')}>
      <span className="studio-muted">{packagingLabel(packaging)}{packaging.fallback ? ` · ${t('包装未能完整生成，已使用原字幕')}` : ''}</span>
    </Row>
    <Row stack label={t('标题')} hint={packaging.template === 'interview_zh' ? t('整条视频顶部显示，第二行为强调色。') : t('开头约 3 秒显示。')}>
      {lines.map((line, index) => <input key={index} className="ac-input" aria-label={t('标题第 {{n}} 行', { n: index + 1 })} maxLength={max}
        value={line} placeholder={index === 0 ? t('第一行') : t('第二行（可选）')} onChange={e => setLine(index, e.target.value)} />)}
    </Row>
    {packaging.template === 'interview_zh' && <Row label={t('评论标签')} hint={t('在关键句出现的编辑点评。')}>
      <Switch size="small" checked={packaging.tags_enabled} disabled={!packaging.tags.length} onChange={checked => update({ tags_enabled: checked })} aria-label={t('评论标签')} />
    </Row>}
  </>
}
