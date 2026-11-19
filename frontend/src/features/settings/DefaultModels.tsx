import type { ReactNode } from 'react'
import { Select } from 'antd'
import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import type { ModelList, ModelSettings } from './modelSettingsApi'
import {
  analysisImageMisconfig, analysisImageMisconfigCopy, applyAnalysisImageFix,
  applyCoverOff, applyFixedSelection, applyLocalTranscription, applySmartSelection, applyVisionFollow,
  collectModelGroups, COMING_SOON, isFixedSelected, isSmartSelected,
  preferredOffer, PURPOSE_SLOTS, slotSummary, visionWarning, WHISPER_MODELS,
  type PurposeId, type SlotLine,
} from './defaultModelSlots'
import { analysisUsesWeakLocalTimelineModel } from './weakLocalTimeline'
import WeakLocalTimelineNote from './WeakLocalTimelineNote'

function lineText(line: SlotLine): string {
  if (line.kind === 'off') return t('关闭 · 使用视频帧')
  if (line.kind === 'empty') return t('搜索模型')
  if (line.kind === 'follow') return t('与精彩片段分析相同')
  if (line.kind === 'local') return t('{{model}} · 本机', { model: line.model })
  if (line.kind === 'smart') return t('{{model}} · 智能选择', { model: line.model })
  return line.provider
    ? t('{{model}} · {{provider}}', { model: line.model, provider: line.provider })
    : (line.model || '')
}

type Choice = {
  value: string
  label: string
  selected: boolean
  hint?: string
  disabled?: boolean
  apply: () => ModelSettings
}

function PurposeSelect({ settings, lists, purpose, title, onChange }: {
  settings: ModelSettings; lists: Record<string, ModelList>; purpose: PurposeId; title: string
  onChange: (next: ModelSettings) => void
}) {
  const choices: Choice[] = []
  if (purpose === 'vision') choices.push({
    value: 'follow', label: t('与精彩片段分析相同'), selected: !settings.vision, apply: () => applyVisionFollow(settings),
  })
  if (purpose === 'cover') choices.push({
    value: 'off', label: t('关闭 · 使用视频帧'), selected: !settings.cover_enabled, apply: () => applyCoverOff(settings),
  })
  if (purpose === 'transcription') {
    for (const model of WHISPER_MODELS) choices.push({
      value: model, label: `${t('本机 Whisper')} · ${model}`,
      selected: settings.transcription?.provider === 'whisper_local' && settings.transcription.model === model,
      apply: () => applyLocalTranscription(settings, 'whisper_local', model),
    })
    choices.push({
      value: 'sensevoice', label: t('本机 SenseVoice'), selected: settings.transcription?.provider === 'sensevoice_local',
      apply: () => applyLocalTranscription(settings, 'sensevoice_local', 'SenseVoiceSmall'),
    })
  }
  for (const { modelId, offers } of collectModelGroups(settings, lists, purpose)) {
    for (const offer of offers) {
      const label = t('{{model}} · {{provider}}', { model: modelId, provider: offer.displayName })
      choices.push({
        value: JSON.stringify(['user', offer.connectionId, modelId]), label,
        hint: offer.connected ? t('已连接') : !offer.selectable ? t('连接校验失败')
          : purpose === 'analysis' ? t('已配置，保存时验证') : t('已配置'),
        selected: isFixedSelected(settings, purpose, modelId, offer), disabled: !offer.selectable,
        apply: () => applyFixedSelection(settings, purpose, modelId, offer.connectionId),
      })
    }
    const preferred = preferredOffer(offers)
    if (preferred) choices.push({
      value: JSON.stringify(['preset', preferred.connectionId, modelId]),
      label: `${modelId} · ${preferred.displayName} · ${t('智能选择')}`,
      selected: isSmartSelected(settings, purpose, modelId, preferred),
      apply: () => applySmartSelection(settings, purpose, modelId, preferred.connectionId),
    })
  }
  const selected = choices.find(option => option.selected)
  const summary = slotSummary(settings, lists, purpose)
  // Keep an existing binding legible while discovering models or after its account list changes.
  const saved = summary.kind !== 'empty' ? { value: 'saved', label: lineText(summary) } : undefined
  return (
    <Select<string, Choice> id={`ai-defaults-select-${purpose}`} aria-label={title} className="ac-purpose-select"
      showSearch optionFilterProp="label" listHeight={248} placeholder={t('搜索模型')}
      value={selected?.value ?? saved?.value} labelRender={({ label }) => label ?? saved?.label}
      // Chromium's native search clear can reopen the menu after Select handles Escape.
      onInputKeyDown={event => { if (event.key === 'Escape') event.preventDefault() }}
      options={choices}
      optionRender={({ data }) => <div className="ac-model-choice"><span>{data.label}</span>{data.hint && <small>{data.hint}</small>}</div>}
      notFoundContent={choices.length ? t('没有匹配的模型。') : t('请在下方的服务商设置中测试连接并启用模型。')}
      onChange={value => {
        const option = choices.find(item => item.value === value)
        if (option && !option.disabled) onChange(option.apply())
      }}
    />
  )
}

export default function DefaultModels({ settings, lists, onChange, transcriptionNote = null }: {
  settings: ModelSettings
  lists: Record<string, ModelList>
  onChange: (next: ModelSettings) => void
  transcriptionNote?: ReactNode
}) {
  useTranslation()
  return (
    <div id="ai-defaults" className="ac-default-models">
      <div className="ac-default-models-head">
        <h3 className="ac-model-section-title">{t('默认模型')}</h3>
        <button type="button" className="ac-link-button" onClick={() => document.getElementById('ai-provider-search')?.focus()}>
          {t('settings.providers.search')}
        </button>
      </div>
      <div className="ac-purpose-grid">
        {PURPOSE_SLOTS.map(slot => {
          const warning = slot.id === 'vision' ? visionWarning(settings, lists) : null
          return (
            <div key={slot.id} id={`ai-defaults-${slot.id}`} className="ac-purpose-slot">
              <div className="ac-purpose-card">
                <div className="ac-purpose-heading">
                  <label className="ac-purpose-title" htmlFor={`ai-defaults-select-${slot.id}`}>{t(slot.titleKey)}</label>
                  <span className="ac-purpose-kind">{t(slot.kindKey)}</span>
                </div>
                <PurposeSelect settings={settings} lists={lists} purpose={slot.id} title={t(slot.titleKey)} onChange={onChange} />
              </div>
              {slot.id === 'transcription' && transcriptionNote}
              {warning && (
                <p className="ac-note ac-note--error" role="alert">
                  {warning === 'follow'
                    ? t('画面理解跟随的模型没有视觉能力。可以保存，开始生成前会拦住。')
                    : t('画面理解所选模型没有视觉能力。可以保存，开始生成前会拦住。')}
                </p>
              )}
              {slot.id === 'analysis' && analysisUsesWeakLocalTimelineModel(settings) && <WeakLocalTimelineNote />}
              {slot.id === 'analysis' && (() => {
                const fix = analysisImageMisconfig(settings)
                if (!fix) return null
                return (
                  <div className="ac-note ac-note--error" role="alert" data-testid="analysis-image-misconfig">
                    <p>{analysisImageMisconfigCopy(fix.model, fix.recommend)}</p>
                    {fix.recommend && (
                      <button
                        type="button"
                        className="ac-link-button"
                        data-testid="analysis-image-fix"
                        onClick={() => onChange(applyAnalysisImageFix(settings, fix))}
                      >
                        {t('改用 {{recommend}}', { recommend: fix.recommend })}
                      </button>
                    )}
                  </div>
                )
              })()}
            </div>
          )
        })}
      </div>
      <p className="ac-purpose-soon">
        <span>{t('即将支持')}</span>
        {COMING_SOON.map(label => <span key={label}>{t(label)}</span>)}
      </p>
    </div>
  )
}
