import { useState, type ReactNode } from 'react'
import { Select } from 'antd'
import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import type { Capability, ModelList, ModelSettings } from './modelSettingsApi'
import {
  analysisImageMisconfig, analysisImageMisconfigCopy, applyAnalysisImageFix,
  applyCoverOff, applyFixedSelection, applyLocalTranscription, applySmartSelection, applyVisionFollow,
  collectModelGroups, isFixedSelected, isSmartSelected,
  preferredOffer, PURPOSE_SLOTS, slotSummary, visionWarning, WHISPER_MODELS,
  type PurposeId, type SlotLine,
} from './defaultModelSlots'
import { analysisUsesWeakLocalTimelineModel } from './weakLocalTimeline'
import WeakLocalTimelineNote from './WeakLocalTimelineNote'

function lineText(line: SlotLine): string {
  if (line.kind === 'off') return t('本机排版 · 使用视频帧')
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

function PurposeSelect({ settings, lists, purpose, title, onChange, showSmartChoices = false }: {
  settings: ModelSettings; lists: Record<string, ModelList>; purpose: PurposeId; title: string
  onChange: (next: ModelSettings) => void; showSmartChoices?: boolean
}) {
  const choices: Choice[] = []
  if (purpose === 'vision') choices.push({
    value: 'follow', label: t('与精彩片段分析相同'), selected: !settings.vision, apply: () => applyVisionFollow(settings),
  })
  if (purpose === 'cover') choices.push({
    value: 'off', label: t('本机排版 · 使用视频帧'), selected: slotSummary(settings, lists, 'cover').kind === 'off', apply: () => applyCoverOff(settings),
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
      const accountFailed = settings.connections.find(connection => connection.id === offer.connectionId)?.validation_status === 'failed'
      choices.push({
        value: JSON.stringify(['user', offer.connectionId, modelId]), label,
        hint: accountFailed ? t('模型连接未通过校验。请到「设置 → 服务商与模型」按提示改密钥或地址后再生成。') : offer.connected ? t('已连接') : !offer.selectable ? t('当前模型校验失败，可换一个型号或重新测试。') : t('已配置'),
        selected: isFixedSelected(settings, purpose, modelId, offer), disabled: !offer.selectable,
        apply: () => applyFixedSelection(settings, purpose, modelId, offer.connectionId),
      })
    }
    const preferred = preferredOffer(offers)
    if (preferred && (showSmartChoices || isSmartSelected(settings, purpose, modelId, preferred))) choices.push({
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
  if (purpose === 'analysis' && !choices.length && (!settings.saved || !saved)) {
    return <button type="button" className="ac-link-button" onClick={() => document.getElementById('ai-provider-search')?.focus()}>
      {t('先连接服务商')}
    </button>
  }
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
  const [showSmartChoices, setShowSmartChoices] = useState(false)
  const analysis = settings.analysis
  const analysisList = analysis && lists[analysis.connection_id]
  const analysisEntry = analysisList?.models.find(entry => entry.id === analysis?.model)
  const renderSlot = (slot: typeof PURPOSE_SLOTS[number]) => {
    const warning = slot.id === 'vision' ? visionWarning(settings, lists) : null
    return (
      <div key={slot.id} id={`ai-defaults-${slot.id}`} className="ac-purpose-slot">
        <div className="ac-purpose-card">
          <div className="ac-purpose-heading">
            <label className="ac-purpose-title" htmlFor={`ai-defaults-select-${slot.id}`}>{t(slot.titleKey)}</label>
            <span className="ac-purpose-kind">{t(slot.kindKey)}</span>
          </div>
          <PurposeSelect settings={settings} lists={lists} purpose={slot.id} title={t(slot.titleKey)} onChange={onChange} showSmartChoices={showSmartChoices} />
          {slot.id === 'analysis' && analysis && analysisEntry?.analysis && !analysisEntry.capability && !analysisList?.preview && (
            <label className="ac-note">
              {t('服务商未标明输入类型，可按模型文档选择。')}
              <Select<Capability> aria-label={t('自定义模型类型')} value={analysis.capability}
                options={[{ value: 'auto', label: t('自动识别') }, { value: 'text', label: t('仅文字') }, { value: 'multimodal', label: t('多模态') }]}
                onChange={capability => onChange({ ...settings, analysis: { ...analysis, capability } })} />
            </label>
          )}
          {slot.id === 'transcription' && settings.transcription_needs_repair && <p className="ac-note ac-note--error" role="alert">{t('原转写模型已不受支持，请重新选择转写模型。')}</p>}
          {slot.id === 'cover' && !settings.cover?.model && !settings.prefer_local_cover && (
            <p className="ac-note">{t('封面模型可稍后选择，其他设置可先保存。')}</p>
          )}
          {slot.id === 'cover' && <label className="ac-note">{t('封面制作方式')}
            <select value={settings.cover_design_mode || 'crop_grade_text_only'} onChange={event => onChange({ ...settings,
              cover_design_mode: event.target.value as ModelSettings['cover_design_mode'] })}>
              <option value="crop_grade_text_only">{t('原帧排版')}</option><option value="editorial_edit">{t('模型编辑')}</option>
            </select></label>}
          {slot.id === 'cover' && settings.cover_enabled && settings.cover?.model && (
            <label className="ac-note"><input type="checkbox" checked={settings.allow_send_frame}
              onChange={event => onChange({ ...settings, allow_send_frame: event.target.checked })} /> {t('允许向封面生图模型上传参考帧')}</label>
          )}
          {slot.id === 'cover' && settings.cover_enabled && settings.cover?.model && (settings.cover_design_mode || 'crop_grade_text_only') !== 'editorial_edit' && (
            <p className="ac-note" role="status">{t('当前为「原帧排版」，不会调用所选生图模型；切到「模型编辑」后生效。')}</p>
          )}
          {slot.id === 'cover' && settings.cover_enabled && settings.cover?.model && settings.cover_design_mode === 'editorial_edit' && !settings.allow_send_frame && (
            <p className="ac-note" role="status">{t('已关闭向封面生图模型上传参考帧，将仅使用本机排版，不会调用所选生图模型（不影响画面理解）。')}</p>
          )}
          {slot.id === 'cover' && !settings.cover_enabled && settings.cover?.model && (
            <button type="button" className="ac-link-button" onClick={() => onChange({ ...settings, cover_enabled: true, prefer_local_cover: false, cover_design_mode: 'editorial_edit' })}>
              {t('启用 {{model}}', { model: settings.cover.model })}
            </button>
          )}
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
  }
  return (
    <div id="ai-defaults" className="ac-default-models">
      <div className="ac-default-models-head">
        <h3 className="ac-model-section-title">{t('默认模型')}</h3>
        <button type="button" className="ac-link-button" onClick={() => document.getElementById('ai-provider-search')?.focus()}>
          {t('settings.providers.search')}
        </button>
      </div>
      {settings.connections.map(connection => {
        const list = lists[connection.id]
        return list?.source === 'cache' && list.warning
          ? <p key={connection.id} role="status" className="ac-note">{connection.name} · {t(list.warning)}</p>
          : null
      })}
      <div className="ac-purpose-grid">
        {PURPOSE_SLOTS.map(renderSlot)}
      </div>
      <label className="ac-note" style={{ marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <input type="checkbox" checked={showSmartChoices} onChange={event => setShowSmartChoices(event.target.checked)} />
        {t('高级：显示智能回退选项')}
      </label>
    </div>
  )
}
