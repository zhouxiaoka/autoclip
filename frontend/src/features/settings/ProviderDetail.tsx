import { t } from '../../i18n'
import { Btn, Icon, Row, StatusDot } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import SpeechRecognitionConfig from '../../components/SpeechRecognitionConfig'
import type { ProviderPreset } from './providerPresets'
import type { ModelSettingsStore } from './useModelSettings'
import ProviderFields from './ProviderFields'
import SenseVoiceConfig from './SenseVoiceConfig'
import { validationCopy } from './providerAccess'
import {
  catalogDraftConnection, connectKind, displayNameOf, findCatalogConnection, isCatalogConfigured, isCatalogConnected,
  type LocalAsrReady,
} from './providerCatalogView'
import { providerIcon } from './providerIcons'
import { enabledModelIds } from './modelVisibility'

const CAP_KEY: Record<string, string> = {
  language: 'settings.providers.filter.language',
  asr: 'settings.providers.filter.asr',
  tts: 'settings.providers.filter.tts',
  image: 'settings.providers.filter.image',
  music: 'settings.providers.filter.music',
  video: 'settings.providers.filter.video',
}

type DetailModel = { id: string; analysis?: boolean; image?: boolean; asr?: boolean; capability?: string | null; kind?: string }
type GroupKey = 'language' | 'image' | 'asr' | 'audio' | 'video' | 'other'
// Group by the backend `kind` (derived from the provider's /models type metadata); flags only for older backends.
export function modelGroupOf(m: DetailModel): GroupKey {
  if (m.kind && ['language', 'image', 'asr', 'audio', 'video', 'other'].includes(m.kind)) return m.kind as GroupKey
  if (m.asr) return 'asr'
  if (m.image) return 'image'
  if (m.analysis) return 'language'
  return 'other'
}
// Each model lands in exactly one group, so the header count equals the rows. No per-group limits.
const MODEL_GROUP: Array<{ key: GroupKey; title: string; open: boolean }> = [
  { key: 'language', title: '语言', open: true },
  { key: 'image', title: '图像生成', open: true },
  { key: 'asr', title: '语音识别', open: true },
  { key: 'audio', title: '语音合成 / 音频', open: false },
  { key: 'video', title: '视频', open: false },
  { key: 'other', title: '其它类型', open: false },
]

export default function ProviderDetail({
  preset, m, asrReady = {}, onBack,
}: {
  preset: ProviderPreset
  m: ModelSettingsStore
  asrReady?: LocalAsrReady
  onBack: () => void
}) {
  const { settings, lists, busy, listErrors } = m
  if (!settings) return null
  const kind = connectKind(preset)
  const persisted = findCatalogConnection(settings, preset)
  const draft = persisted || catalogDraftConnection(preset)
  const connection = draft && {
    ...draft,
    base_url: draft.base_url || preset.base_url || '',
  }
  const connected = isCatalogConnected(settings, preset, asrReady)
  const list = connection ? lists[connection.id] : undefined
  // Only a real (live/cache, non-preview) fetch shows models; catalog/preview reference IDs would mislead.
  const fetched = !!list && list.preview !== true && list.source !== 'catalog'
  const models = fetched ? list!.models : []
  const needsEndpoint = kind === 'needs_endpoint' || (kind === 'guide' && !preset.base_url)
  const canTest = kind === 'legacy' || kind === 'compatible' || needsEndpoint
  const isSponsor = !!preset.sponsor

  // Visibility only: no revalidation, no list reset. Only enabled IDs reach the default-model pickers.
  const enabledSet = persisted && list ? enabledModelIds(settings, persisted, list.models) : new Set<string>()
  const customized = Array.isArray(persisted?.enabled_model_ids)
  const toggleModels = (ids: string[], on: boolean) => {
    if (!persisted) return
    const next = new Set(enabledSet)
    for (const id of ids) { if (on) next.add(id); else next.delete(id) }
    m.update({ connections: settings.connections.map(c => c.id === persisted.id ? { ...c, enabled_model_ids: [...next] } : c) })
  }
  const resetRecommended = () => {
    if (!persisted) return
    m.update({ connections: settings.connections.map(c => c.id === persisted.id ? { ...c, enabled_model_ids: null } : c) })
  }

  const persistEdit = (patch: Parameters<typeof m.editConnection>[1]) => {
    if (persisted) m.editConnection(persisted, patch)
    else m.ensureCatalogProvider(preset.id, patch)
  }

  const onTest = () => {
    if (!connection) return
    void m.testCatalogProvider(preset.id, {
      api_key: connection.api_key,
      base_url: connection.base_url,
      has_key: connection.has_key,
    })
  }

  const showModels = kind !== 'local_asr' && kind !== 'guide'
  const showConnectPanel = kind !== 'local_asr'
  const name = t(displayNameOf(preset))
  const icon = providerIcon(preset.id)
  const testing = m.testing
  const listing = connection && busy[connection.id]
  const status = connection?.validation_status
  const testDisabled = !connection || testing || (
    preset.auth === 'api_key' && !(connection.api_key || '').trim() && !connection.has_key
  ) || (!connection.base_url.trim() && !preset.base_url && preset.protocol !== 'local')

  return (
    <div className="ac-provider-detail" data-provider-id={preset.id} data-connect-kind={kind} data-layout="v6-stack" data-sponsor={isSponsor ? '1' : undefined}>
      <button type="button" className="ac-back" onClick={onBack}>
        <Icon.Back />{t('settings.providers.back')}
      </button>
      <header className="ac-provider-detail-head">
        <h3 className="ac-model-section-title">
          {icon && (
            <span className={`ac-provider-mark has-icon is-${icon.tone} ac-provider-mark--title`} aria-hidden>
              <img src={icon.src} alt="" />
            </span>
          )}
          {name}
          {isSponsor && (
            <span className="ac-badge">
              {preset.sponsor!.offer
                ? t('settings.providers.badge.sponsor_offer', { offer: t(preset.sponsor!.offer) })
                : t('settings.providers.badge.sponsor')}
            </span>
          )}
          {connected && <StatusDot tone="ok" label={preset.auth === 'none' ? t('settings.providers.available') : t('settings.providers.connected')} />}
          {!connected && isCatalogConfigured(settings, preset) && <span className="ac-badge">{t('已配置')}</span>}
        </h3>
        {/* Sponsors: no long hint / marketing. Others keep one short line. */}
        {!isSponsor && <p className="ac-note">{t(preset.hint)}</p>}
        {!isSponsor && (
          <div className="ac-provider-caps">
            {preset.capabilities.map(capability => CAP_KEY[capability] && (
              <span key={capability} className="ac-provider-cap">{t(CAP_KEY[capability])}</span>
            ))}
          </div>
        )}
      </header>

      <div className="ac-provider-detail-stack">
        {showConnectPanel && (
          <section className="ac-provider-detail-card" data-panel="connect">
            {needsEndpoint && (
              <p className="ac-note">{t('请先填写接口地址，再测试连接。')}</p>
            )}

            {(kind === 'legacy' || kind === 'compatible') && connection && (
              <ProviderFields
                connection={connection}
                hideProvider
                placement="settings_model"
                keyHint={persisted ? m.keyHints[persisted.id] : undefined}
                onChoose={() => undefined}
                onEdit={persistEdit}
              />
            )}

            {needsEndpoint && connection && (
              <ProviderFields
                connection={connection}
                hideProvider
                placement="settings_model"
                keyHint={persisted ? m.keyHints[persisted.id] : undefined}
                onChoose={() => undefined}
                onEdit={persistEdit}
              />
            )}

            {kind === 'guide' && !needsEndpoint && (
              <div className="ac-empty">
                <b>{t('settings.providers.protocol_guide')}</b>
                {preset.docs_url && (
                  <Btn variant="text" size="sm" onClick={() => openExternalLink(preset.docs_url)}>
                    {t('settings.providers.docs')}<Icon.External size={12} />
                  </Btn>
                )}
              </div>
            )}

            {canTest && connection && (
              <div className="ac-provider-test-row">
                <Btn size="sm" className="ac-btn--pill" disabled={testDisabled} loading={testing || !!listing} onClick={onTest}>
                  {t('测试连接')}
                </Btn>
                {status === 'failed' && (
                  <p className="ac-note ac-note--error" role="alert">{validationCopy(connection.validation_error_type)}</p>
                )}
                {status === 'transient' && (
                  <p className="ac-note" role="status">{validationCopy(connection.validation_error_type)}</p>
                )}
              </div>
            )}
          </section>
        )}

        {kind === 'local_asr' && (
          <section className="ac-provider-detail-card" data-panel="connect">
            <h4 className="ac-provider-models-title">{t('配置')}</h4>
            {preset.id === 'whisper' && (
              <>
                {settings.transcription?.provider !== 'whisper_local' && (
                  <Row label={t('settings.providers.use_whisper')} hint={t(preset.hint)}>
                    <Btn size="sm" onClick={() => m.selectLocalAsrProvider('whisper')}>{t('settings.providers.use_whisper')}</Btn>
                  </Row>
                )}
                <SpeechRecognitionConfig
                  hideProvider
                  selectedModel={settings.transcription?.provider === 'whisper_local' ? (settings.transcription.model || 'base') : 'base'}
                  onModelChange={m.setTranscriptionLocal}
                />
              </>
            )}
            {preset.id === 'sensevoice' && (
              <>
                {settings.transcription?.provider !== 'sensevoice_local' && (
                  <Row label={t('settings.providers.use_sensevoice')} hint={t(preset.hint)}>
                    <Btn size="sm" onClick={() => m.selectLocalAsrProvider('sensevoice')}>{t('settings.providers.use_sensevoice')}</Btn>
                  </Row>
                )}
                <SenseVoiceConfig />
              </>
            )}
          </section>
        )}

        {showModels && (
          <section className="ac-provider-detail-card" data-panel="models">
            <h4 className="ac-provider-models-title">
              {t('可用模型')}
              <span className="count">{fetched ? (persisted ? `${t('已启用')} ${models.filter(x => enabledSet.has(x.id)).length} / ${models.length}` : models.length) : t('测通后获取')}</span>
            </h4>
            {connection && busy[connection.id] && <p className="ac-note">{t('正在获取…')}</p>}
            {connection && listErrors[connection.id] && <p className="ac-note">{t('settings.providers.models_empty')}</p>}
            {fetched && models.length > 0 && persisted && (
              <p className="ac-note ac-provider-model-hint" data-visibility={customized ? 'custom' : 'recommended'}>
                {customized ? t('已按你的勾选；默认模型只从已勾选里选。') : t('已为你勾选推荐模型，可自行增减；默认模型只从已勾选里选。')}
                {customized && <button type="button" className="ac-link-button" onClick={resetRecommended}>{t('恢复推荐')}</button>}
              </p>
            )}
            {fetched && models.length > 0 && <ModelGroups models={models} enabled={enabledSet} onToggle={persisted ? toggleModels : undefined} />}
            {connection && !busy[connection.id] && !fetched && (
              <p className="ac-note" data-models-hint="pending">{t('填写 API 密钥并测通后，将自动拉取可用模型。')}</p>
            )}
            {connection && !busy[connection.id] && fetched && !models.length && (
              <p className="ac-note">{t('settings.providers.models_empty')}</p>
            )}
          </section>
        )}
      </div>
    </div>
  )
}

function ModelGroups({ models, enabled: on, onToggle }: {
  models: Array<DetailModel>
  enabled: Set<string>
  onToggle?: (ids: string[], enabled: boolean) => void
}) {
  return (
    <>
      {MODEL_GROUP.map(group => {
        const rows = models.filter(model => modelGroupOf(model) === group.key).sort((a, b) => Number(on.has(b.id)) - Number(on.has(a.id)))
        if (!rows.length) return null
        const enabled = rows.filter(model => on.has(model.id)).length
        const renderRow = (model: DetailModel) => (
          <li key={model.id} className={`ac-mono${!on.has(model.id) && onToggle ? ' is-hidden' : ''}`} data-model-id={model.id}>
            {onToggle
              ? <label className="ac-provider-model-check">
                  <input type="checkbox" checked={on.has(model.id)} aria-label={`${t('启用')} ${model.id}`} onChange={event => onToggle([model.id], event.target.checked)} />
                  <span>{model.id}</span>
                </label>
              : model.id}
            {group.key === 'language' && model.capability === 'multimodal' && (
              <span className="ac-provider-cap">{t('视觉')}</span>
            )}
          </li>
        )
        return (
          <details key={group.key} className="ac-provider-model-block" data-model-group={group.key} open={group.open || (!!onToggle && enabled > 0)}>
            <summary className="ac-provider-model-group">
              {t(group.title)}<span className="count">{onToggle ? `${enabled}/${rows.length}` : rows.length}</span>
              {onToggle && (
                <span className="ac-provider-model-bulk">
                  <button type="button" disabled={enabled === rows.length} onClick={event => { event.preventDefault(); onToggle(rows.map(m => m.id), true) }}>{t('全部启用')}</button>
                  <button type="button" disabled={enabled === 0} onClick={event => { event.preventDefault(); onToggle(rows.map(m => m.id), false) }}>{t('全部停用')}</button>
                </span>
              )}
            </summary>
            {(onToggle ? rows.filter(model => on.has(model.id)) : rows).length > 0 && (
              <ul className="ac-provider-model-list" data-model-rows="enabled">
                {(onToggle ? rows.filter(model => on.has(model.id)) : rows).map(model => renderRow(model))}
              </ul>
            )}
            {onToggle && rows.length > enabled && (
              <details className="ac-provider-model-off" data-model-rows="disabled">
                <summary>{t('未启用')}<span className="count">({rows.length - enabled})</span></summary>
                <ul className="ac-provider-model-list">
                  {rows.filter(model => !on.has(model.id)).map(model => renderRow(model))}
                </ul>
              </details>
            )}
          </details>
        )
      })}
    </>
  )
}
