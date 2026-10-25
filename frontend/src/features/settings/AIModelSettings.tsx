import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { Btn, Icon, Row, Section, StatusDot } from '../../ui'
import api, { speechApi } from '../../services/api'
import { useModelSettings, type ModelSettingsStore } from './useModelSettings'
import { mainConnection, validationTargets, visionFollowLacksCapability, VISION_HINT_KEY, type SaveIssue } from './modelSettingsLogic'
import type { Connection, ModelSettings } from './modelSettingsApi'
import ProviderFields from './ProviderFields'
import ModelPicker from './ModelPicker'
import ProviderCatalog from './ProviderCatalog'
import ProviderDetail from './ProviderDetail'
import {
  catalogPreset, customConnectionId, sensevoiceAsrReady, whisperAsrReady,
  type CapabilityFilter, type LocalAsrReady,
} from './providerCatalogView'
import DefaultModels from './DefaultModels'
import {
  applyRequestedCloudTranscription, cloudTranscriptionDiscoverTargets, cloudTranscriptionSavePatch,
  cloudTranscriptionWaitExpired, CLOUD_TRANSCRIPTION_WAIT_MS,
} from './defaultModelSlots'
import AddCustomProviderDialog from './AddCustomProviderDialog'
import { requestClipboardScan, takePendingSelect } from './keyGuideBus'

function useLocalAsrReady(settings: ModelSettings | null): LocalAsrReady {
  const [ready, setReady] = useState<LocalAsrReady>({})
  useEffect(() => {
    if (!settings) return
    let alive = true
    const load = async () => {
      try {
        const [runtime, models] = await Promise.all([speechApi.getRuntimeStatus(), speechApi.getModels()])
        let sense: { status?: string } | null = null
        try { sense = await api.get('/sensevoice/status') } catch { sense = null }
        if (!alive) return
        const selected = settings.transcription?.provider === 'whisper_local' ? (settings.transcription.model || 'base') : 'base'
        setReady({
          whisper: whisperAsrReady(runtime, models, selected),
          sensevoice: sensevoiceAsrReady(sense),
        })
      } catch { /* keep last known readiness */ }
    }
    void load()
    const timer = window.setInterval(() => void load(), 15000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [settings?.transcription?.provider, settings?.transcription?.model])
  return ready
}

const ANCHORS: Record<string, string> = {
  model: 'ai-defaults', analysis: 'ai-defaults-analysis', vision: 'ai-defaults-vision',
  speech: 'ai-defaults-transcription', cover: 'ai-defaults-cover',
}
const issueAnchor = (issue: SaveIssue) => (
  `ai-defaults-${issue.role}`
)

function CustomGatewayRepair({ connection, m, onBack }: { connection: Connection; m: ModelSettingsStore; onBack: () => void }) {
  const { settings, lists, busy, listErrors } = m
  if (!settings) return null
  const main = mainConnection(settings)
  const isAnalysis = main?.id === connection.id
  const list = lists[connection.id]
  return (
    <div className="ac-provider-detail" data-provider-id="compatible" data-connect-kind="compatible">
      <button type="button" className="ac-back" onClick={onBack}>
        <Icon.Back />{t('settings.providers.back')}
      </button>
      <h3 className="ac-model-section-title">{connection.name || t('自定义 OpenAI 兼容接口')}</h3>
      <p className="ac-note">{t('settings.providers.repair_custom_hint')}</p>
      <ProviderFields
        connection={connection}
        placement="settings_model"
        keyHint={m.keyHints[connection.id]}
        onChoose={p => m.chooseProvider('analysis', p)}
        onEdit={patch => m.editConnection(connection, patch)}
      />
      {isAnalysis && settings.analysis
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
              onChange={value => m.update({ analysis: { connection_id: connection.id, model: value, capability: 'auto', model_source: 'user' } })}
              onCapability={capability => settings.analysis && m.update({ analysis: { ...settings.analysis, capability } })}
              onRefresh={() => void m.discover(connection, true)}
              actions={<Btn variant="text" size="sm" disabled={!settings.analysis.model} loading={m.testing} onClick={() => void m.test()}>{t('测试连接')}</Btn>}
            />
          </Row>
        : <Row label={t('settings.providers.use_for_analysis')} hint={t('settings.providers.use_for_analysis_hint')}>
            <Btn size="sm" onClick={() => m.assignAnalysisConnection(connection)}>{t('settings.providers.use_for_analysis')}</Btn>
          </Row>}
    </div>
  )
}

export default function AIModelSettings({ requestedSection, requestedProvider = '' }: { requestedSection: string; requestedProvider?: string }) {
  useTranslation()
  const m = useModelSettings()
  const { settings } = m
  const asrReady = useLocalAsrReady(settings)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<CapabilityFilter>('all')
  const [moreOpen, setMoreOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(() => catalogPreset(requestedProvider)?.id || null)
  const selected = catalogPreset(selectedId)
  const customSelected = settings?.connections.find(connection => connection.id === customConnectionId(selectedId))

  useEffect(() => {
    const preset = catalogPreset(requestedProvider)
    if (preset) setSelectedId(preset.id)
  }, [requestedProvider])
  useEffect(() => {
    const pending = takePendingSelect()
    if (pending) setSelectedId(pending)
  }, [settings])

  const cloudChoice = useRef(false)
  const cloudPending = useRef(false)
  const cloudDiscover = useRef(false)
  const cloudWaitStarted = useRef<number | null>(null)
  const [cloudTimedOut, setCloudTimedOut] = useState(false)
  const [cloudChecking, setCloudChecking] = useState(false)
  const [cloudNote, setCloudNote] = useState<{ provider: string; model: string } | null>(null)
  const lists = m.lists
  useEffect(() => {
    if (requestedProvider !== 'cloud' || !settings || cloudDiscover.current) return
    cloudDiscover.current = true
    for (const connection of cloudTranscriptionDiscoverTargets(settings)) {
      if (!lists[connection.id]) void m.discover(connection, false, 'manual')
    }
  }, [requestedProvider, settings, lists])
  useEffect(() => {
    if (!settings || cloudChoice.current) return
    const result = applyRequestedCloudTranscription(requestedProvider, settings, lists, { timedOut: cloudTimedOut })
    if (result.kind === 'idle') { setCloudChecking(false); return }
    if (result.kind === 'wait') {
      setCloudChecking(true)
      if (cloudWaitStarted.current == null) cloudWaitStarted.current = Date.now()
      const started = cloudWaitStarted.current
      if (cloudTranscriptionWaitExpired(started, Date.now())) { setCloudTimedOut(true); return }
      const timer = window.setTimeout(() => setCloudTimedOut(true), CLOUD_TRANSCRIPTION_WAIT_MS - (Date.now() - started))
      return () => window.clearTimeout(timer)
    }
    cloudChoice.current = true
    setCloudChecking(false)
    if (result.kind === 'selected') {
      const transcription = result.settings.transcription
      const note = { provider: result.providerLabel, model: result.model }
      m.update({ transcription })
      void m.save({ transcription }).then(saved => {
        if (saved.ok && !saved.validationFailed) setCloudNote(note)
      })
    } else {
      cloudPending.current = true
      setSelectedId('dashscope')
    }
  }, [requestedProvider, settings, lists, cloudTimedOut])

  const [customOpen, setCustomOpen] = useState(false)
  useEffect(() => {
    const anchor = ANCHORS[requestedSection]
    if (!settings || !anchor || selectedId) return
    const timer = window.setTimeout(() => document.getElementById(anchor)?.scrollIntoView({ block: 'start' }), 0)
    return () => window.clearTimeout(timer)
  }, [requestedSection, !!settings, selectedId])

  const openProvider = (id: string) => {
    setSelectedId(id)
  }
  const closeProvider = () => setSelectedId(null)

  if (!settings) return <Section title={t('settings.providers.title')}><p className="ac-note">{m.error || t('加载中…')}</p>{m.error && <Btn onClick={() => void m.load()}>{t('重试')}</Btn>}</Section>
  const save = async () => {
    const patch = cloudTranscriptionSavePatch(cloudPending.current, settings, m.lists)
    const result = await m.save(patch)
    if (result.ok && !result.validationFailed && patch?.transcription?.provider === 'cloud' && patch.transcription.model) {
      cloudPending.current = false
      const chosen = applyRequestedCloudTranscription('cloud', { ...settings, ...patch }, m.lists)
      if (chosen.kind === 'selected') setCloudNote({ provider: chosen.providerLabel, model: chosen.model })
    }
    if (result.issue) document.getElementById(issueAnchor(result.issue))?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    else if (result.validationFailed) document.getElementById('ai-defaults')?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }
  const visionFailed = visionFollowLacksCapability(settings, m.lists)
  const failed = validationTargets(settings).some(({ connection }) => connection.validation_status === 'failed') || visionFailed
  return <div className="ac-ai-settings" data-layout="v6">
    {settings.migration_warnings?.includes('cover_configuration_invalid') && <p role="alert" className="ac-note">{t('旧版封面配置无效，请在封面设置中重新选择服务。原配置文件已保留。')}</p>}
    {settings.migration_warnings?.includes('purpose_reset_to_recommended') && <p role="alert" className="ac-note">{t('部分用途无法按原样迁移。API Key 已保留，相关模型已改为推荐默认。此提示只出现一次。')}</p>}
    {settings.migration_warnings?.includes('preset_catalog_updated') && <p role="alert" className="ac-note">{t('服务商推荐列表已更新。已保存的连接不会改动，新连接会使用新的推荐。')}</p>}
    {settings.migration_warnings?.some(code => ['settings_configuration_invalid', 'analysis_configuration_invalid', 'vision_configuration_invalid', 'transcription_configuration_invalid'].includes(code)) && <p role="alert" className="ac-note">{t('部分 AI 配置无法读取，请重新选择服务并填写密钥。原配置已保留，保存修正时会备份损坏的文件。')}</p>}
    <fieldset className="ac-model-fields" disabled={m.saving || m.testing}>
      {customSelected ? <CustomGatewayRepair connection={customSelected} m={m} onBack={closeProvider} />
        : selected ? <ProviderDetail preset={selected} m={m} asrReady={asrReady} onBack={closeProvider} /> : <>
        <header className="ac-settings-ai-head">
          <p className="ac-note">{t('settings.providers.subtitle')}</p>
          <Btn variant="text" size="sm" onClick={() => requestClipboardScan()}>{t('settings.key_guide.detect')}</Btn>
        </header>
        <div className="ac-model-section" data-section="default-models">
          <DefaultModels
            settings={settings}
            lists={m.lists}
            onChange={next => m.update(next)}
            transcriptionNote={<>
              {cloudChecking && <p className="ac-note" role="status">{t('正在检查可用的云端转写…')}</p>}
              {cloudNote && <p className="ac-note" role="status">{t('已改用 {{provider}} 的 {{model}} 做云端转写。音频会上传到云端。', cloudNote)}</p>}
            </>}
          />
        </div>
        <ProviderCatalog
          settings={settings}
          query={query}
          filter={filter}
          moreOpen={moreOpen}
          selectedId={selectedId}
          asrReady={asrReady}
          onQuery={setQuery}
          onFilter={setFilter}
          onToggleMore={() => setMoreOpen(open => !open)}
          onOpen={openProvider}
          onAdd={() => setCustomOpen(true)}
        />
        <details className="ac-disclosure ac-model-section"><summary>{t('高级')}</summary>
          <Row label={t('文本分块大小')}><input aria-label={t('文本分块大小')} className="ac-input" type="number" min={1000} max={10000} step={500} value={settings.chunk_size} onChange={e => m.update({ chunk_size: Number(e.target.value) })} /></Row>
          <Row label={t('最低评分阈值')}><input aria-label={t('最低评分阈值')} className="ac-input" type="number" min={.1} max={1} step={.05} value={settings.min_score_threshold} onChange={e => m.update({ min_score_threshold: Number(e.target.value) })} /></Row>
          <Row label={t('每个合集最多切片')}><input aria-label={t('每个合集最多切片')} className="ac-input" type="number" min={1} max={20} value={settings.max_clips_per_collection} onChange={e => m.update({ max_clips_per_collection: Number(e.target.value) })} /></Row>
        </details>
      </>}
    </fieldset>
    {settings.analysis && settings.model_substitutions?.filter(item => item.purpose === 'analysis' && item.saved_model === settings.analysis?.model).map(item => (
      <p className="ac-note" role="status" key={item.replacement}>
        {t('分析模型 {{saved}} 当前不可用，这次已改用 {{replacement}}。', { saved: item.saved_model, replacement: item.replacement })}
        {' '}
        <Btn variant="text" size="sm" disabled={m.saving} onClick={() => void m.save({ analysis: { ...settings.analysis!, model: item.replacement } })}>{t('保存这个模型')}</Btn>
      </p>
    ))}
    {m.error && <p className="studio-error" role="alert">{m.error}</p>}
    <div className="ac-savebar">
      <StatusDot tone={failed ? 'error' : m.dirty ? 'muted' : 'ok'} label={failed ? (validationTargets(settings).some(({ connection }) => connection.validation_status === 'failed') ? t('校验未通过。设置已保存，但开始生成前会拦住。') : t(VISION_HINT_KEY)) : m.dirty ? t('有未保存的更改') : settings.saved ? t('设置已保存') : t('首次使用，保存后生效')} />
      <Btn variant="cta" size="sm" className="ac-btn--pill" disabled={m.testing} loading={m.saving} onClick={() => void save()}>{t('保存设置')}</Btn>
    </div>
    <AddCustomProviderDialog open={customOpen} onClose={() => setCustomOpen(false)}
      onSubmit={draft => { m.addCustomProvider(draft); setCustomOpen(false) }} />
  </div>
}
