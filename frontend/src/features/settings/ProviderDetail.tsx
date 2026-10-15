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

const CAP_KEY: Record<string, string> = {
  language: 'settings.providers.filter.language',
  asr: 'settings.providers.filter.asr',
  tts: 'settings.providers.filter.tts',
  image: 'settings.providers.filter.image',
  music: 'settings.providers.filter.music',
  video: 'settings.providers.filter.video',
}

const MODEL_GROUP: Array<{
  key: 'language' | 'asr' | 'image'
  title: string
  pick: (model: { analysis?: boolean; image?: boolean; asr?: boolean; capability?: string }) => boolean
  limit: number
}> = [
  { key: 'language', title: '语言', pick: m => !!m.analysis, limit: 8 },
  { key: 'asr', title: '语音识别', pick: m => !!m.asr, limit: 4 },
  { key: 'image', title: '图像生成', pick: m => !!m.image, limit: 4 },
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
  const models = list?.models.filter(model => model.analysis || model.image || model.asr) || []
  const needsEndpoint = kind === 'needs_endpoint' || (kind === 'guide' && !preset.base_url)
  const canTest = kind === 'legacy' || kind === 'compatible' || needsEndpoint
  const isSponsor = !!preset.sponsor

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
              <span className="count">{connected || models.length ? models.length : t('测通后获取')}</span>
            </h4>
            {connection && busy[connection.id] && <p className="ac-note">{t('正在获取…')}</p>}
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
              <p className="ac-note">{t('测通后在此显示。')}</p>
            )}
          </section>
        )}
      </div>
    </div>
  )
}
