import { t } from '../../i18n'
import { Btn, Icon, Row, StatusDot } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import SpeechRecognitionConfig from '../../components/SpeechRecognitionConfig'
import type { ProviderPreset } from './providerPresets'
import type { ModelSettingsStore } from './useModelSettings'
import ProviderFields from './ProviderFields'
import ModelPicker from './ModelPicker'
import SenseVoiceConfig from './SenseVoiceConfig'
import { mainConnection } from './modelSettingsLogic'
import {
  catalogDraftConnection, connectKind, displayNameOf, findCatalogConnection, isCatalogConnected,
} from './providerCatalogView'

const CAP_KEY: Record<string, string> = {
  language: 'settings.providers.filter.language',
  asr: 'settings.providers.filter.asr',
  tts: 'settings.providers.filter.tts',
  image: 'settings.providers.filter.image',
  music: 'settings.providers.filter.music',
  video: 'settings.providers.filter.video',
}

export default function ProviderDetail({
  preset, m, onBack,
}: {
  preset: ProviderPreset
  m: ModelSettingsStore
  onBack: () => void
}) {
  const { settings, lists, busy, listErrors } = m
  if (!settings) return null
  const kind = connectKind(preset)
  const persisted = findCatalogConnection(settings, preset)
  const connection = persisted || catalogDraftConnection(preset)
  const connected = isCatalogConnected(settings, preset)
  const main = mainConnection(settings)
  const isAnalysis = !!persisted && main?.id === persisted.id
  const list = connection ? lists[connection.id] : undefined
  const models = list?.models.filter(model => model.analysis || model.image || model.asr) || []
  const preview = models.slice(0, 8)
  const hidden = Math.max(0, models.length - preview.length)

  const persistEdit = (patch: Parameters<typeof m.editConnection>[1]) => {
    if (persisted) m.editConnection(persisted, patch)
    else m.ensureCatalogProvider(preset.id, patch)
  }
  const useAsAnalysis = () => {
    if (persisted) m.assignAnalysisConnection(persisted)
    else m.ensureCatalogProvider(preset.id, undefined, true)
  }

  return (
    <div className="ac-provider-detail" data-provider-id={preset.id} data-connect-kind={kind}>
      <button type="button" className="ac-back" onClick={onBack}>
        <Icon.Back />{t('settings.providers.back')}
      </button>
      <header className="ac-provider-detail-head">
        <h3 className="ac-model-section-title">
          {t(displayNameOf(preset))}
          {preset.sponsor && (
            <span className="ac-badge">
              {preset.sponsor.offer
                ? t('settings.providers.badge.sponsor_offer', { offer: t(preset.sponsor.offer) })
                : t('settings.providers.badge.sponsor')}
            </span>
          )}
          {connected && <StatusDot tone="ok" label={preset.auth === 'none' ? t('settings.providers.available') : t('settings.providers.connected')} />}
        </h3>
        <p className="ac-note">{t(preset.hint)}</p>
        <div className="ac-provider-caps">
          {preset.capabilities.map(capability => CAP_KEY[capability] && (
            <span key={capability} className="ac-provider-cap">{t(CAP_KEY[capability])}</span>
          ))}
        </div>
      </header>

      {!connected && kind !== 'local_asr' && (
        <p className="ac-note">{t('settings.providers.unconnected_guide')}</p>
      )}
      {preset.sponsor && <p className="ac-note">{t('settings.providers.one_click_hint')}</p>}
      {(kind === 'legacy' || kind === 'compatible') && <h4 className="ac-provider-models-title">{t('settings.providers.manual_key')}</h4>}

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

      {kind === 'guide' && (
        <div className="ac-empty">
          <b>{t('settings.providers.protocol_guide')}</b>
          {preset.docs_url && (
            <Btn variant="text" size="sm" onClick={() => openExternalLink(preset.docs_url)}>
              {t('settings.providers.docs')}<Icon.External size={12} />
            </Btn>
          )}
        </div>
      )}

      {kind === 'local_asr' && preset.id === 'whisper' && (
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

      {kind === 'local_asr' && preset.id === 'sensevoice' && (
        <>
          {settings.transcription?.provider !== 'sensevoice_local' && (
            <Row label={t('settings.providers.use_sensevoice')} hint={t(preset.hint)}>
              <Btn size="sm" onClick={() => m.selectLocalAsrProvider('sensevoice')}>{t('settings.providers.use_sensevoice')}</Btn>
            </Row>
          )}
          <SenseVoiceConfig />
        </>
      )}

      {kind !== 'local_asr' && kind !== 'guide' && (
        <div className="ac-provider-models">
          <h4 className="ac-provider-models-title">{t('settings.providers.models_preview')}</h4>
          {connection && busy[connection.id] && <p className="ac-note">{t('正在获取可用模型…')}</p>}
          {connection && listErrors[connection.id] && <p className="ac-note">{t('settings.providers.models_empty')}</p>}
          {preview.length > 0 && (
            <ul className="ac-provider-model-list">
              {preview.map(model => (
                <li key={model.id} className="ac-mono">{model.id}</li>
              ))}
            </ul>
          )}
          {hidden > 0 && <p className="ac-note">{t('settings.providers.more_models', { count: hidden })}</p>}
          {connection && !busy[connection.id] && !preview.length && (
            <p className="ac-note">{t('settings.providers.models_empty')}</p>
          )}
        </div>
      )}

      {kind !== 'guide' && kind !== 'local_asr' && connection && preset.capabilities.includes('language') && (
        isAnalysis && settings.analysis
          ? <Row wide label={t('settings.providers.using_for_analysis')} hint={t('已为你选好推荐模型，可随时更换。')}>
              <ModelPicker
                role="analysis"
                model={settings.analysis.model || ''}
                capability={settings.analysis.capability}
                connection={connection}
                list={list}
                busy={!!busy[connection.id]}
                listError={listErrors[connection.id]}
                mode={settings.analysis_mode}
                onChange={value => m.update({ analysis: { connection_id: connection.id, model: value, capability: 'auto' } })}
                onCapability={capability => settings.analysis && m.update({ analysis: { ...settings.analysis, capability } })}
                onRefresh={() => void m.discover(connection, true)}
                actions={<Btn variant="text" size="sm" disabled={!settings.analysis.model} loading={m.testing} onClick={() => void m.test()}>{t('测试连接')}</Btn>}
              />
            </Row>
          : <Row label={t('settings.providers.use_for_analysis')} hint={t('settings.providers.use_for_analysis_hint')}>
              <Btn size="sm" disabled={!connection} onClick={useAsAnalysis}>{t('settings.providers.use_for_analysis')}</Btn>
            </Row>
      )}

      {preset.docs_url && kind !== 'guide' && (
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
      <p className="ac-note">{t('settings.providers.key_local_only')}</p>
    </div>
  )
}
