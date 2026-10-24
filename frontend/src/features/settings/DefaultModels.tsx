import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { Icon } from '../../ui'
import type { ModelList, ModelSettings } from './modelSettingsApi'
import {
  applyCoverOff, applyFixedSelection, applyLocalTranscription, applySmartSelection, applyVisionFollow,
  collectModelGroups, COMING_SOON, hiddenNonVisionCount, isFixedSelected, isSmartSelected,
  preferredOffer, PURPOSE_SLOTS, slotSummary, visionWarning, WHISPER_MODELS,
  type ModelGroup, type ModelOffer, type PurposeId, type SlotLine,
} from './defaultModelSlots'

const SMART_HINT = '记下这个型号，只绑定这一家服务商。换服务商请用下面的固定选项。'

function lineText(line: SlotLine): string {
  if (line.kind === 'off') return t('关闭 · 使用视频帧')
  if (line.kind === 'empty') return t('还没有已连接的服务商。请先在下方配置一家。')
  if (line.kind === 'follow') return t('与精彩片段分析相同')
  if (line.kind === 'local') return t('{{model}} · 本机', { model: line.model })
  if (line.kind === 'smart') return t('{{model}} · 智能选择', { model: line.model })
  return line.provider
    ? t('{{model}} · {{provider}}', { model: line.model, provider: line.provider })
    : (line.model || '')
}

function OptionButton({ selected, disabled, label, hint, onClick }: {
  selected: boolean; disabled?: boolean; label: string; hint?: string; onClick: () => void
}) {
  return (
    <button type="button" className="ac-purpose-option" aria-selected={selected} disabled={disabled} onClick={onClick}>
      <span className="ac-purpose-option-label">{label}</span>
      {hint && <span className="ac-purpose-option-hint">{hint}</span>}
      {selected && <Icon.Check size={14} />}
    </button>
  )
}

function ModelGroupBlock({ settings, purpose, group, onChange }: {
  settings: ModelSettings; purpose: PurposeId; group: ModelGroup; onChange: (next: ModelSettings) => void
}) {
  const preferred = preferredOffer(group.offers)
  const many = group.offers.length > 1
  return (
    <div className="ac-purpose-group">
      <div className="ac-purpose-group-head">
        <span className="ac-mono">{group.modelId}</span>
        {many && <span className="ac-purpose-count">{t('{{count}} 个服务商提供', { count: group.offers.length })}</span>}
      </div>
      {preferred?.connectionId && (
        <div className="ac-purpose-smart">
          <OptionButton
            selected={isSmartSelected(settings, purpose, group.modelId, preferred)}
            label={t('智能选择')}
            onClick={() => onChange(applySmartSelection(settings, purpose, group.modelId, preferred.connectionId!))}
          />
          <span className="ac-purpose-help" title={t(SMART_HINT)} aria-label={t('智能选择说明')}><Icon.Help size={14} /></span>
        </div>
      )}
      {group.offers.map(offer => (
        <OfferRow key={`${offer.provider}:${offer.connectionId || ''}`} settings={settings} purpose={purpose} group={group} offer={offer} onChange={onChange} />
      ))}
    </div>
  )
}

function OfferRow({ settings, purpose, group, offer, onChange }: {
  settings: ModelSettings; purpose: PurposeId; group: ModelGroup; offer: ModelOffer; onChange: (next: ModelSettings) => void
}) {
  const disabled = !offer.connected || !offer.connectionId
  return (
    <OptionButton
      selected={!disabled && isFixedSelected(settings, purpose, group.modelId, offer)}
      disabled={disabled}
      label={offer.displayName}
      hint={offer.connected ? t('已连接') : t('未连接')}
      onClick={() => offer.connectionId && onChange(applyFixedSelection(settings, purpose, group.modelId, offer.connectionId))}
    />
  )
}

function PurposePanel({ settings, lists, purpose, onChange }: {
  settings: ModelSettings; lists: Record<string, ModelList>; purpose: PurposeId; onChange: (next: ModelSettings) => void
}) {
  const [query, setQuery] = useState('')
  const groups = useMemo(() => {
    const all = collectModelGroups(settings, lists, purpose)
    const needle = query.trim().toLowerCase()
    return needle ? all.filter(group => group.modelId.toLowerCase().includes(needle)) : all
  }, [settings, lists, purpose, query])
  const hidden = purpose === 'vision' ? hiddenNonVisionCount(lists) : 0
  const warning = purpose === 'vision' ? visionWarning(settings, lists) : null
  return (
    <div className="ac-purpose-panel" role="region" aria-label={t('搜索模型')}>
      {purpose === 'vision' && (
        <OptionButton selected={!settings.vision} label={t('与精彩片段分析相同')} onClick={() => onChange(applyVisionFollow(settings))} />
      )}
      {purpose === 'cover' && (
        <OptionButton selected={!settings.cover_enabled} label={t('关闭 · 使用视频帧')} onClick={() => onChange(applyCoverOff(settings))} />
      )}
      {purpose === 'transcription' && (
        <>
          {WHISPER_MODELS.map(model => (
            <OptionButton
              key={model}
              selected={settings.transcription?.provider === 'whisper_local' && settings.transcription.model === model}
              label={`${t('本机 Whisper')} · ${model}`}
              onClick={() => onChange(applyLocalTranscription(settings, 'whisper_local', model))}
            />
          ))}
          <OptionButton
            selected={settings.transcription?.provider === 'sensevoice_local'}
            label={t('本机 SenseVoice')}
            onClick={() => onChange(applyLocalTranscription(settings, 'sensevoice_local', 'SenseVoiceSmall'))}
          />
        </>
      )}
      {groups.length > 0 && (
        <input className="ac-input ac-purpose-search" value={query} onChange={event => setQuery(event.target.value)} placeholder={t('搜索模型')} aria-label={t('搜索模型')} />
      )}
      {groups.map(group => (
        <ModelGroupBlock key={group.modelId} settings={settings} purpose={purpose} group={group} onChange={onChange} />
      ))}
      {purpose !== 'transcription' && !groups.length && (
        <p className="ac-note">{t('还没有已连接的服务商。请先在下方配置一家。')}</p>
      )}
      {purpose === 'vision' && hidden > 0 && (
        <p className="ac-note">{t('已隐藏 {{count}} 个不支持视觉的模型', { count: hidden })}</p>
      )}
      {warning && (
        <p className="ac-note ac-note--error" role="alert">
          {warning === 'follow'
            ? t('画面理解跟随的模型没有视觉能力。可以保存，开始生成前会拦住。')
            : t('画面理解所选模型没有视觉能力。可以保存，开始生成前会拦住。')}
        </p>
      )}
    </div>
  )
}

export default function DefaultModels({ settings, lists, onChange, transcriptionNote = null }: {
  settings: ModelSettings
  lists: Record<string, ModelList>
  onChange: (next: ModelSettings) => void
  transcriptionNote?: ReactNode
}) {
  useTranslation()
  const [open, setOpen] = useState<PurposeId | null>(null)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onPointer = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(null)
    }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(null) }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [])
  return (
    <div id="ai-defaults" className="ac-default-models" ref={root}>
      <h3 className="ac-model-section-title">{t('默认模型')}</h3>
      <div className="ac-purpose-grid">
        {PURPOSE_SLOTS.map(slot => {
          const line = slotSummary(settings, lists, slot.id)
          const warning = slot.id === 'vision' ? visionWarning(settings, lists) : null
          return (
            <div key={slot.id} id={`ai-defaults-${slot.id}`} className="ac-purpose-slot">
              <button
                type="button"
                className="ac-purpose-card"
                aria-expanded={open === slot.id}
                aria-controls={`ai-defaults-panel-${slot.id}`}
                onClick={() => setOpen(current => current === slot.id ? null : slot.id)}
              >
                <span className="ac-purpose-title">{t(slot.titleKey)}</span>
                <span className="ac-purpose-kind">{t(slot.kindKey)}</span>
                <span className="ac-purpose-line ac-mono">{lineText(line)}</span>
              </button>
              {slot.id === 'transcription' && transcriptionNote}
              {warning && open !== slot.id && (
                <p className="ac-note ac-note--error" role="alert">
                  {warning === 'follow'
                    ? t('画面理解跟随的模型没有视觉能力。可以保存，开始生成前会拦住。')
                    : t('画面理解所选模型没有视觉能力。可以保存，开始生成前会拦住。')}
                </p>
              )}
              {open === slot.id && (
                <div id={`ai-defaults-panel-${slot.id}`}>
                  <PurposePanel settings={settings} lists={lists} purpose={slot.id} onChange={next => { onChange(next) }} />
                </div>
              )}
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
