import { t } from '../../i18n'
import { trackTemplateOverride } from '../../analytics/studio'
import { telemetryId } from '../../analytics/workflow'

export const HTML_TEMPLATE_CHOICES = ['editorial', 'street', 'classic'] as const
export type HtmlTemplateChoice = (typeof HTML_TEMPLATE_CHOICES)[number]
export const DEFAULT_HTML_TEMPLATE: HtmlTemplateChoice = 'editorial'

const COPY: Record<HtmlTemplateChoice, { name: string; hint: string }> = {
  editorial: { name: '杂志风', hint: '坐姿访谈、演讲，衬线标题。' },
  street: { name: '街头快剪', hint: '街访、快问快答，短字幕。' },
  classic: { name: '经典包装', hint: '沿用现在的字幕包装。' },
}

export function chosenTemplate(value: string | undefined): HtmlTemplateChoice {
  return value === 'street' || value === 'classic' ? value : DEFAULT_HTML_TEMPLATE
}

/** Import fields for the HTML template. The flag-off path sends nothing. */
export function templateImportFields(enabled: boolean, value: string | undefined): { html_template?: HtmlTemplateChoice } {
  if (!enabled) return {}
  return { html_template: chosenTemplate(value) }
}

export default function TemplatePicker({ value, disabled, onChange }: { value: string | undefined; disabled?: boolean; onChange: (next: HtmlTemplateChoice) => void }) {
  const current = chosenTemplate(value)
  const choose = (next: HtmlTemplateChoice) => {
    if (disabled || next === current) return
    trackTemplateOverride({ from_template: current, to_template: next, stage: 'pre_import', flow_id: telemetryId() })
    onChange(next)
  }
  return <fieldset className="studio-template-picker">
    <legend>{t('包装模板')}</legend>
    <p className="studio-muted">{t('导入时选定。得分靠前的成片用这个模板，其余用经典包装。')}</p>
    <div className="studio-template-options">
      {HTML_TEMPLATE_CHOICES.map(id => <button type="button" key={id} className={id === current ? 'studio-template-option is-selected' : 'studio-template-option'} aria-pressed={id === current} disabled={disabled} onClick={() => choose(id)}>
        <b>{t(COPY[id].name)}</b>
        <span>{t(COPY[id].hint)}</span>
      </button>)}
    </div>
  </fieldset>
}
