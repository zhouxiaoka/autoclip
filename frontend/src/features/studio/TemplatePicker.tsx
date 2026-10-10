import { useEffect, useRef } from 'react'
import { t } from '../../i18n'
import { trackTemplateOverride, trackTemplatePickerShown } from '../../analytics/studio'
import { telemetryId } from '../../analytics/workflow'
import EditingStylePicker from './EditingStylePicker'
import { HTML_TEMPLATE_CHOICES, chosenTemplate, templateImportFields, type HtmlTemplateChoice } from './editingStyle'

export { HTML_TEMPLATE_CHOICES, chosenTemplate, templateImportFields }
export type { HtmlTemplateChoice }

const COPY: Record<HtmlTemplateChoice, { name: string; hint: string }> = {
  editorial: { name: 'editing_style.editorial.name', hint: 'editing_style.editorial.desc' },
  street: { name: 'editing_style.street.name', hint: 'editing_style.street.desc' },
  classic: { name: 'editing_style.classic.name', hint: 'editing_style.classic.desc' },
}

export default function TemplatePicker({
  value, disabled, onChange, visual = false, sourceKey = null, url, file, sourceKind = 'none',
}: {
  value: string | undefined
  disabled?: boolean
  onChange: (next: HtmlTemplateChoice) => void
  visual?: boolean
  sourceKey?: string | null
  url?: string
  file?: File | null
  sourceKind?: 'link' | 'file' | 'none'
}) {
  const shown = useRef(false)
  useEffect(() => {
    if (visual || shown.current) return
    shown.current = true
    trackTemplatePickerShown({ recommended: 'editorial', reason_code: 'default', flag_variant: 'text', source_kind: sourceKind, latency_ms: 0 })
  }, [visual, sourceKind])
  if (visual) {
    return <EditingStylePicker value={value} disabled={disabled} onChange={onChange} sourceKey={sourceKey} url={url} file={file} />
  }
  const current = chosenTemplate(value)
  const choose = (next: HtmlTemplateChoice) => {
    if (disabled || next === current) return
    trackTemplateOverride({ from_template: current, to_template: next, stage: 'pre_import', input: 'mouse', flow_id: telemetryId() })
    onChange(next)
  }
  return <fieldset className="studio-template-picker">
    <legend>{t('editing_style.title')}</legend>
    <p className="studio-muted">{t('editing_style.text_hint')}</p>
    <div className="studio-template-options">
      {HTML_TEMPLATE_CHOICES.map(id => <button type="button" key={id} className={id === current ? 'studio-template-option is-selected' : 'studio-template-option'} aria-pressed={id === current} disabled={disabled} onClick={() => choose(id)}>
        <b>{t(COPY[id].name)}</b>
        <span>{t(COPY[id].hint)}</span>
      </button>)}
    </div>
  </fieldset>
}
