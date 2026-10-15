import { t } from '../../i18n'
import { Btn, Icon, Row, StatusDot } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import SpeechRecognitionConfig from '../../components/SpeechRecognitionConfig'
import type { ProviderPreset } from './providerPresets'
import type { ModelSettingsStore } from './useModelSettings'
import ProviderFields from './ProviderFields'
import EndpointProviderSetup from './EndpointProviderSetup'
import SenseVoiceConfig from './SenseVoiceConfig'
import {
  catalogDraftConnection, connectKind, displayNameOf, findCatalogConnection, isCatalogConfigured, isCatalogConnected,
  type LocalAsrReady,
} from './providerCatalogView'

const CAP_KEY: Record<string, string> = {
  language: 'settings.providers.filter.language',
  asr: 'settings.providers.filter.asr',
  tts: 'settings.providers.filter.tts',
  image: 'settings.providers.filter.image',
  music: 'settings.providers.filter.music',
  video: 'settings.providers.filter.video',
}

/** 与目录筛选词一致；括号内是默认模型用途，方便小白对照。 */
const MODEL_GROUP: Array<{
  key: 'language' | 'asr' | 'image'
  title: string
  pick: (model: { analysis?: boolean; image?: boolean; asr?: boolean; capability?: string }) => boolean
  limit: number
}> = [
  { key: 'language', title: '语言 · 精彩片段分析 / 画面理解', pick: m => !!m.analysis, limit: 8 },
  { key: 'asr', title: '语音识别 · 语音转字幕', pick: m => !!m.asr, limit: 4 },
  { key: 'image', title: '图像生成 · 封面生成', pick: m => !!m.image, limit: 4 },
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
  const connection = persisted || catalogDraftConnection(preset)
  const connected = isCatalogConnected(settings, preset, asrReady)
  const list = connection ? lists[connection.id] : undefined
  const models = list?.models.filter(model => model.analysis || model.image || model.asr) || []

  const persistEdit = (patch: Parameters<typeof m.editConnection>[1]) => {
    if (persisted) m.editConnection(persisted, patch)
    else m.ensureCatalogProvider(preset.id, patch)
  }

  const showModelsPanel = kind !== 'local_asr' && kind !== 'guide' && kind !== 'needs_endpoint'
  const showConnectPanel = kind !== 'local_asr'
  const name = t(displayNameOf(preset))

  return (
    <div className="ac-provider-detail" data-provider-id={preset.id} data-connect-kind={kind} data-layout="v6-stack">
      <button type="button" className="ac-back" onClick={onBack}>
        <Icon.Back />{t('settings.providers.back')}
      </button>
      <header className="ac-provider-detail-head">
        <h3 className="ac-model-section-title">
          {name}
          {preset.sponsor && (
            <span className="ac-badge">
              {preset.sponsor.offer
                ? t('settings.providers.badge.sponsor_offer', { offer: t(preset.sponsor.offer) })
                : t('settings.providers.badge.sponsor')}
            </span>
          )}
          {connected && <StatusDot tone="ok" label={preset.auth === 'none' ? t('settings.providers.available') : t('settings.providers.connected')} />}
          {!connected && isCatalogConfigured(settings, preset) && <span className="ac-badge">{t('已配置')}</span>}
        </h3>
        <p className="ac-note">{t(preset.hint)}</p>
        <div className="ac-provider-caps">
          {preset.capabilities.map(capability => CAP_KEY[capability] && (
            <span key={capability} className="ac-provider-cap">{t(CAP_KEY[capability])}</span>
          ))}
        </div>
      </header>

      <div className="ac-provider-detail-stack">
        {showConnectPanel && (
          <section className="ac-provider-detail-card" data-panel="connect">
            <h4 className="ac-provider-models-title">{t('连接')}</h4>
            {!connected && <p className="ac-note">{t('settings.providers.unconnected_guide')}</p>}
            {preset.sponsor && <p className="ac-note">{t('settings.providers.one_click_hint')}</p>}

            {kind === 'legacy' && connection && (
              <ProviderFields
                connection={connection}
                hideProvider
                placement="settings_model"
                keyHint={persisted ? m.keyHints[persisted.id] : undefined}
                onChoose={() => undefined}
                onEdit={persistEdit}
              />
            )}

            {kind === 'compatible' && connection && (
              <>
                <p className="ac-note">{t('settings.providers.compat_guide')}</p>
                <ProviderFields
                  connection={connection}
                  hideProvider
                  placement="settings_model"
                  keyHint={persisted ? m.keyHints[persisted.id] : undefined}
                  onChoose={() => undefined}
                  onEdit={persistEdit}
                />
              </>
            )}

            {(kind === 'guide' || kind === 'needs_endpoint') && (
              <div className="ac-empty">
                <b>{t(kind === 'needs_endpoint' ? 'settings.providers.needs_endpoint_guide' : 'settings.providers.protocol_guide')}</b>
                {preset.docs_url && (
                  <Btn variant="text" size="sm" onClick={() => openExternalLink(preset.docs_url)}>
                    {t('settings.providers.docs')}<Icon.External size={12} />
                  </Btn>
                )}
              </div>
            )}

            {(kind === 'needs_endpoint' || (kind === 'guide' && !preset.base_url)) && connection && (
              <EndpointProviderSetup connection={connection} onEdit={persistEdit} m={m} />
            )}

            <p className="ac-note ac-provider-key-hint">{t('settings.providers.key_local_only')}</p>
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

        {showModelsPanel && (
          <section className="ac-provider-detail-card" data-panel="models">
            <h4 className="ac-provider-models-title">
              {t('可用模型')}
              <span className="count">{connected || models.length ? models.length : t('连接后显示')}</span>
            </h4>
            {connection && busy[connection.id] && <p className="ac-note">{t('正在获取可用模型…')}</p>}
            {connection && listErrors[connection.id] && <p className="ac-note">{t('settings.providers.models_empty')}</p>}
            {MODEL_GROUP.map(group => {
              const rows = models.filter(group.pick).slice(0, group.limit)
              if (!rows.length) return null
              return (
                <div key={group.key} className="ac-provider-model-block">
                  <p className="ac-provider-model-group">{t(group.title)}</p>
                  <ul className="ac-provider-model-list">
                    {rows.map(model => (
                      <li key={model.id} className="ac-mono">
                        {model.id}
                        {group.key === 'language' && model.capability === 'multimodal' && (
                          <span className="ac-provider-cap">{t('视觉')}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
            {connection && !busy[connection.id] && !models.length && (
              <p className="ac-note">{t('settings.providers.models_empty')}</p>
            )}
            <p className="ac-note ac-provider-models-foot">
              {t('连接后可在上方「默认模型」中选择。')}
            </p>
          </section>
        )}
      </div>

      {preset.docs_url && kind !== 'guide' && kind !== 'needs_endpoint' && (
        <p className="ac-note">
          <a
            className="ac-link"
            href={preset.docs_url}
            onClick={event => { event.preventDefault(); openExternalLink(preset.docs_url) }}
          >
            {t('settings.providers.docs')} ↗
          </a>
        </p>
      )}
    </div>
  )
}
