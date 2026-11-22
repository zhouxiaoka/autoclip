import { useRef, useState } from 'react'
import type { ModelEntry } from './modelSettingsApi'
import { t } from '../../i18n'
import { Btn, Icon, Row, StatusDot } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import SpeechRecognitionConfig from '../../components/SpeechRecognitionConfig'
import type { ProviderPreset } from './providerPresets'
import type { ModelSettingsStore } from './useModelSettings'
import ProviderFields from './ProviderFields'
import SenseVoiceConfig from './SenseVoiceConfig'
import { validationCopy } from './providerAccess'
import TrialRunPanel from './TrialRunPanel'
import {
  catalogDraftConnection, connectKind, displayNameOf, findCatalogConnection, isCatalogConfigured, isCatalogConnected,
  type LocalAsrReady,
} from './providerCatalogView'
import { providerIcon } from './providerIcons'
import ProviderQualityMarks from './providerQualityMarks'
import { enabledModelIds } from './modelVisibility'
import { NEUTRAL_PROVIDER_COPY, promotionAllowsUpsell, promotionRegisterUrl } from './sponsorPromoState'

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
  const editingConnectionId = useRef<string | undefined>(undefined)
  if (!settings) return null
  const kind = connectKind(preset)
  // Editing base_url may move the connection out of the catalog preset match,
  // so keep tracking the same connection by id during editing.
  const persisted = editingConnectionId.current
    ? settings.connections.find(row => row.id === editingConnectionId.current)
    : findCatalogConnection(settings, preset)
  const connection = persisted && !persisted.base_url && !editingConnectionId.current && preset.base_url
    ? { ...persisted, base_url: preset.base_url }
    : persisted || catalogDraftConnection(preset)
  const connected = isCatalogConnected(settings, preset, asrReady, persisted)
  const list = connection ? lists[connection.id] : undefined
  // Only a real (live/cache, non-preview) fetch shows models; catalog/preview reference IDs would mislead.
  const fetched = !!list && list.preview !== true && list.source !== 'catalog'
  const models = fetched ? list!.models : []
  const needsEndpoint = kind === 'needs_endpoint' || (kind === 'guide' && !preset.base_url)
  const canTest = kind === 'legacy' || kind === 'compatible' || needsEndpoint
  const packagedRegister = preset.sponsor?.register_url || ''
  const showPromo = promotionAllowsUpsell(preset.id) && (!!preset.sponsor || !!promotionRegisterUrl(preset.id, packagedRegister))

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
    if (persisted) {
      if (patch.base_url !== undefined) editingConnectionId.current = persisted.id
      m.editConnection(persisted, patch)
    } else {
      editingConnectionId.current = m.ensureCatalogProvider(preset.id, patch)
    }
  }

  const onTest = () => {
    if (!connection) return
    void m.testCatalogProvider(preset.id, connection, 'quick')
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
  ) || !connection.base_url.trim()

  return (
    <div className="ac-provider-detail" data-provider-id={preset.id} data-connect-kind={kind} data-layout="v6-stack" data-sponsor={showPromo ? '1' : undefined}>
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
          {showPromo && (
            <span className="ac-badge" data-promo="sponsor">
              {preset.sponsor?.offer
                ? t('settings.providers.badge.sponsor_offer', { offer: t(preset.sponsor.offer) })
                : t('settings.providers.badge.sponsor')}
            </span>
          )}
          {connected && <StatusDot tone="ok" label={preset.auth === 'none' ? t('settings.providers.available') : t('settings.providers.connected')} />}
          {!connected && isCatalogConfigured(settings, preset, persisted) && <span className="ac-badge">{t('已配置')}</span>}
        </h3>
        {/* Active promotion hides the long hint. A removed or stopped sponsor keeps the neutral caps. */}
        {!showPromo && <p className="ac-note">{t(preset.sponsor ? NEUTRAL_PROVIDER_COPY : preset.hint)}</p>}
        <ProviderQualityMarks preset={preset} />
        {!showPromo && (
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
                <p className="ac-note">{t('settings.providers.test_cost')}</p>
                {persisted && <p className="ac-note">{t('自动匹配剪辑、画面理解、转写和封面模型。有云端转写时，音频会发送给这家服务商。')}</p>}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                  {persisted ? (
                    <Btn variant="cta" size="sm" disabled={testDisabled || m.saving} loading={m.saving} onClick={() => void m.configureProvider(persisted)}>
                      {t('测试并启用')}
                    </Btn>
                  ) : (
                    <Btn variant="cta" size="sm" className="ac-btn--pill" disabled={testDisabled} loading={(testing && m.testingKind === 'quick') || !!listing} onClick={onTest}>
                      {t('快速测试')}
                    </Btn>
                  )}
                  {testing && m.testingKind === 'trial' && (
                    <Btn size="sm" variant="text" onClick={() => m.cancelTrial()}>{t('取消试跑')}</Btn>
                  )}
                </div>
                <details className="ac-provider-advanced" data-testid="provider-advanced-actions">
                  <summary className="ac-note">{t('更多操作')}</summary>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginTop: 8 }}>
                    {persisted && (
                      <Btn size="sm" className="ac-btn--pill" disabled={testDisabled} loading={(testing && m.testingKind === 'quick') || !!listing} onClick={onTest}>
                        {t('快速测试')}
                      </Btn>
                    )}
                    <Btn size="sm" className="ac-btn--pill" disabled={testDisabled} loading={testing && m.testingKind === 'trial'} onClick={() => void m.testCatalogProvider(preset.id, connection, 'trial')}>
                      {t('试跑一段')}
                    </Btn>
                    {persisted && persisted.has_key && m.clearConnectionKey && (
                      <Btn size="sm" variant="text" disabled={m.saving} onClick={() => void m.clearConnectionKey(persisted.id)}>
                        {t('清除已保存密钥')}
                      </Btn>
                    )}
                    {persisted && m.removeConnection && (
                      <Btn size="sm" variant="danger" disabled={m.saving} onClick={() => {
                        void m.removeConnection(persisted.id).then(() => onBack())
                      }}>
                        {t('删除此服务商')}
                      </Btn>
                    )}
                  </div>
                </details>
                {status === 'failed' && (
                  <p className="ac-note ac-note--error" role="alert">{validationCopy(connection.validation_error_type)}</p>
                )}
                {status === 'transient' && (
                  <p className="ac-note" role="status">{validationCopy(connection.validation_error_type)}</p>
                )}
                {m.testWarning?.id === connection.id && status !== 'failed' && (
                  <p className="ac-note" role="status">{m.testWarning.text}</p>
                )}
                <TrialRunPanel
                  result={(m.lastTrialByConnection || {})[connection.id]}
                  trialStatus={connection.trial_status}
                />
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
              <span className="count">{fetched ? (persisted ? `${t('在选择器显示')} ${models.filter(x => enabledSet.has(x.id)).length} / ${models.length}` : models.length) : t('测通后获取')}</span>
              {persisted && (persisted.api_key || persisted.has_key) && (
                <Btn variant="text" size="sm" disabled={!!listing} onClick={() => void m.discover(persisted, true)}>{t('刷新')}</Btn>
              )}
            </h4>
            {connection && busy[connection.id] && <p className="ac-note">{t('正在获取…')}</p>}
            {list?.source === 'cache' && list.warning && <p role="status" className="ac-note">{t(list.warning)}</p>}
            {connection && listErrors[connection.id] && <p className="ac-note">{t('settings.providers.models_empty')}</p>}
            {fetched && models.length > 0 && persisted && (
              <p className="ac-note ac-provider-model-hint" data-visibility={customized ? 'custom' : 'recommended'}>
                {t('勾选要在选择器中显示的型号。隐藏型号后，已选用途仍会使用它。')}
                {customized && <button type="button" className="ac-link-button" onClick={resetRecommended}>{t('恢复推荐')}</button>}
              </p>
            )}
            {fetched && models.length > 0 && <ModelGroups models={models} enabled={enabledSet} onToggle={persisted ? toggleModels : undefined} onDeclare={persisted ? (id, role) => m.declareModel(persisted, id, role) : undefined} />}
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

function ModelGroups({ models, enabled: on, onToggle, onDeclare }: {
  models: ModelEntry[]
  onDeclare?: (id: string, role: 'analysis' | 'vision' | 'cover' | '') => void
  enabled: Set<string>
  onToggle?: (ids: string[], enabled: boolean) => void
}) {
  const [search, setSearch] = useState('')
  const query = search.trim().toLowerCase()
  return (
    <>
      <input type="search" aria-label={t('搜索模型')} placeholder={t('搜索模型')} value={search} onChange={event => setSearch(event.target.value)} />
      {query && !models.some(model => model.id.toLowerCase().includes(query)) && <p className="ac-note">{t('没有匹配的模型。')}</p>}
      {MODEL_GROUP.map(group => {
        const rows = models.filter(model => modelGroupOf(model) === group.key && model.id.toLowerCase().includes(query)).sort((a, b) => Number(on.has(b.id)) - Number(on.has(a.id)))
        if (!rows.length) return null
        const enabled = rows.filter(model => on.has(model.id)).length
        const renderRow = (model: ModelEntry) => (
          <li key={model.id} className={`ac-mono${!on.has(model.id) && onToggle ? ' is-hidden' : ''}`} data-model-id={model.id}>
            {onToggle
              ? <label className="ac-provider-model-check">
                  <input type="checkbox" checked={on.has(model.id)} aria-label={`${t('在选择器显示')} ${model.id}`} onChange={event => onToggle([model.id], event.target.checked)} />
                  <span>{model.id}</span>
                </label>
              : model.id}
            {!!model.manual_roles?.length && onDeclare && (
              <select aria-label={`${t('指定模型用途')} ${model.id}`}
                value={model.capability_source === 'custom' ? (model.image ? 'cover' : model.capability === 'multimodal' ? 'vision' : 'analysis') : ''}
                onChange={event => onDeclare(model.id, event.target.value as 'analysis' | 'vision' | 'cover' | '')}>
                <option value="">{t('未指定用途')}</option>
                {model.manual_roles.map(role => <option key={role} value={role}>{t(role === 'cover' ? '封面生成' : role === 'vision' ? '画面理解' : '精彩片段分析')}</option>)}
              </select>
            )}
            {group.key === 'language' && model.capability === 'multimodal' && (
              <span className="ac-provider-cap">{t('视觉')}</span>
            )}
          </li>
        )
        return (
          <details key={group.key} className="ac-provider-model-block" data-model-group={group.key} open={!!query || group.open || (!!onToggle && enabled > 0)}>
            <summary className="ac-provider-model-group">
              {t(group.title)}<span className="count">{onToggle ? `${enabled}/${rows.length}` : rows.length}</span>
              {onToggle && (
                <span className="ac-provider-model-bulk">
                  <button type="button" disabled={enabled === rows.length} onClick={event => { event.preventDefault(); onToggle(rows.map(m => m.id), true) }}>{t('全部显示')}</button>
                  <button type="button" disabled={enabled === 0} onClick={event => { event.preventDefault(); onToggle(rows.map(m => m.id), false) }}>{t('全部隐藏')}</button>
                </span>
              )}
            </summary>
            {group.key === 'other' && <p className="ac-note">{t('服务商未标明输入类型，可按模型文档选择。')}</p>}
            {(onToggle ? rows.filter(model => on.has(model.id)) : rows).length > 0 && (
              <ul className="ac-provider-model-list" data-model-rows="enabled">
                {(onToggle ? rows.filter(model => on.has(model.id)) : rows).map(model => renderRow(model))}
              </ul>
            )}
            {onToggle && rows.length > enabled && (
              <details open={query ? true : undefined} className="ac-provider-model-off" data-model-rows="disabled">
                <summary>{t('已隐藏')}<span className="count">({rows.length - enabled})</span></summary>
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
