import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Switch } from 'antd'
import { t } from '../../i18n'
import { Btn, Icon, Row, Section, StatusDot } from '../../ui'
import api, { speechApi } from '../../services/api'
import { useModelSettings, type ModelSettingsStore } from './useModelSettings'
import { isTextOnly, mainConnection, validationTargets, visionFollowLacksCapability, VISION_HINT_KEY, type SaveIssue } from './modelSettingsLogic'
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
import AddCustomProviderDialog from './AddCustomProviderDialog'

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

/**
 * Main AI service: provider, key, model (auto-recommended) and the frame-sampling switch.
 * Shared with the first-run card so both paths behave identically.
 */
export function AIServiceFields({ m, placement, showVisual = true }: { m: ModelSettingsStore; placement: 'settings_model' | 'home_setup'; showVisual?: boolean }) {
  const { settings, lists, busy, listErrors } = m
  const main = settings && mainConnection(settings)
  if (!settings) return null
  // First run: nothing is pre-selected. Key and model rows appear once a provider is chosen.
  if (!main) return <ProviderFields placement={placement} onChoose={p => m.chooseProvider('analysis', p)} onEdit={() => undefined} />
  const list = lists[main.id]
  const model = settings.analysis?.model || ''
  const visionIssue = visionFollowLacksCapability(settings, lists)
  const hint = busy[main.id] && !model ? t('正在获取可用模型…')
    : model && list && !list.preview ? t('已为你选好推荐模型，可随时更换。')
    : t('填写 API Key 后自动选择推荐模型。')
  return <>
    <ProviderFields connection={main} placement={placement} keyHint={m.keyHints[main.id]} onChoose={p => m.chooseProvider('analysis', p)} onEdit={patch => m.editConnection(main, patch)} />
    <Row wide label={t('模型')} hint={hint}>
      <ModelPicker role="analysis" model={model} capability={settings.analysis?.capability} connection={main} list={list} busy={!!busy[main.id]} listError={listErrors[main.id]} mode={settings.analysis_mode}
        invalid={visionIssue}
        onChange={value => m.update({ analysis: { connection_id: main.id, model: value, capability: 'auto', model_source: 'user' } })}
        onCapability={capability => settings.analysis && m.update({ analysis: { ...settings.analysis, capability } })}
        onRefresh={() => void m.discover(main, true)}
        actions={<Btn variant="text" size="sm" disabled={!model} loading={m.testing} onClick={() => void m.test()}>{t('测试连接')}</Btn>} />
    </Row>
    {showVisual && <Row label={t('画面识别')} hint={isTextOnly(settings, lists)
      ? t('当前模型仅支持文字，只能靠字幕切分。游戏画面、口播较少的内容建议换一个多模态模型再开启。')
      : t('抽样几张画面理解动作与场景。游戏画面、口播较少的内容推荐开启，切分更准；费用略高。关闭后只发送字幕。')}>
      <Switch checked={settings.analysis_mode !== 'subtitle'} onChange={m.setVisual} />
    </Row>}
    {showVisual && visionIssue && <p className="ac-note ac-note--error" role="alert">{t(VISION_HINT_KEY)}</p>}
  </>
}

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
    setSelectedId(catalogPreset(requestedProvider)?.id || null)
  }, [requestedProvider])

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
    const result = await m.save()
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
          <div>
            <h2 className="ac-title" style={{ fontSize: 22 }}>{t('settings.providers.title')}</h2>
            <p className="ac-note" style={{ marginTop: 4 }}>{t('settings.providers.subtitle')}</p>
          </div>
        </header>
        <div className="ac-model-section" data-section="default-models">
          <DefaultModels settings={settings} lists={m.lists} onChange={next => m.update(next)} />
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
    {m.error && <p className="studio-error" role="alert">{m.error}</p>}
    <div className="ac-savebar">
      <StatusDot tone={failed ? 'error' : m.dirty ? 'muted' : 'ok'} label={failed ? (validationTargets(settings).some(({ connection }) => connection.validation_status === 'failed') ? t('校验未通过。设置已保存，但开始生成前会拦住。') : t(VISION_HINT_KEY)) : m.dirty ? t('有未保存的更改') : settings.saved ? t('设置已保存') : t('首次使用，保存后生效')} />
      <Btn variant="cta" disabled={m.testing} loading={m.saving} onClick={() => void save()}>{t('保存设置')}</Btn>
    </div>
    <AddCustomProviderDialog open={customOpen} onClose={() => setCustomOpen(false)}
      onSubmit={draft => { m.addCustomProvider(draft); setCustomOpen(false) }} />
  </div>
}
