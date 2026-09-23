import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { useEffect, useState } from 'react'
import { Btn, Dialog } from '../../ui'
import { studioApi, errorText } from './api'
import { Draft, Language, languages, draftError } from './types'

interface Props {
  open: boolean
  projectId: string
  draft: Draft
  onClose: () => void
  onCreated: (draft: Draft) => void
}

export default function DraftVariantDialog({ open, projectId, draft, onClose, onCreated }: Props) {
  useTranslation()
  const [title, setTitle] = useState('')
  const [language, setLanguage] = useState<Language>('source')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (open) {
      setTitle(t('{{title}} · 新版本', { title: draft.title.slice(0, 180) }))
      setLanguage(draft.language)
      setError('')
    }
  }, [open])
  const create = async () => {
    const invalid = draftError({ ...draft, title })
    if (invalid) { setError(t(invalid)); return }
    setBusy(true); setError('')
    try {
      const result = await studioApi.duplicate(projectId, draft, title.trim(), language)
      onCreated(result)
    } catch (e) { setError(t(errorText(e))) } finally { setBusy(false) }
  }
  return <Dialog open={open} title={t("另存为新版本")} onClose={() => !busy && onClose()}
    description={t("复制当前编辑内容，原稿与已有导出保留。新版本可单独修改语言和开头，无需重新分析画面。")}
    footer={<div className="studio-actions"><Btn disabled={busy} onClick={onClose}>{t("取消")}</Btn><Btn variant="cta" disabled={busy || !title.trim()} loading={busy} onClick={create}>{t("创建新版本")}</Btn></div>}>
    <fieldset className="studio-fieldset" disabled={busy}>
      <label className="studio-field">{t("新版本名称")}<input value={title} maxLength={200} onChange={e => setTitle(e.target.value)} /></label>
      <label className="studio-field">{t("新版本文字语言")}<select value={language} onChange={e => setLanguage(e.target.value as Language)}>{languages.map(l => <option key={l.value} value={l.value}>{l.value==='source' ? t('原语言') : l.label}</option>)}</select></label>
      <p className="studio-muted">{t("文字会在渲染时翻译；镜头与原声沿用当前设置。")}</p>
    </fieldset>
    {error && <p className="studio-error" role="alert">{error}</p>}
  </Dialog>
}
