import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Select, Switch } from 'antd'
import { t } from '../../i18n'
import { Btn, Row, Section, Segmented, StatusDot } from '../../ui'
import SpeechRecognitionConfig from '../../components/SpeechRecognitionConfig'
import { PROVIDERS, providerPickerOptions, type ProviderKey } from './providers'
import { useModelSettings, type ModelSettingsStore } from './useModelSettings'
import { connectionOf, isTextOnly, mainConnection, presetKey, type SaveIssue } from './modelSettingsLogic'
import ProviderFields from './ProviderFields'
import ModelPicker from './ModelPicker'
import api from '../../services/api'

type SenseVoiceStatus = { status: 'not_installed' | 'installing' | 'ready' | 'error'; message: string }

function SenseVoiceConfig() {
  const [runtime, setRuntime] = useState<SenseVoiceStatus | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    const refresh = async () => {
      try {
        const value = await api.get<unknown, SenseVoiceStatus>('/sensevoice/status')
        if (active) { setRuntime(value); setError('') }
      } catch { if (active) setError(t('暂时无法读取本地模型状态。')) }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  const act = async (remove = false) => {
    setBusy(true)
    try {
      const value = remove ? await api.delete<unknown, SenseVoiceStatus>('/sensevoice')
        : await api.post<unknown, SenseVoiceStatus>('/sensevoice/prepare')
      setRuntime(value); setError('')
    } catch { setError(t('操作失败，请稍后重试。')) }
    finally { setBusy(false) }
  }
  const preparing = runtime?.status === 'installing'
  return <div className="ac-rows">
    <Row label={t('转写模型')} hint={t('支持中文、粤语、英语、日语和韩语，使用词级时间戳生成字幕。')}><span>SenseVoiceSmall</span></Row>
    <Row label={runtime?.status === 'ready' ? t('模型已就绪') : t('准备本地模型')}
      hint={runtime?.status === 'ready' ? t('保存设置后，新任务将使用这个模型。') : t('首次需联网下载组件和模型，请预留至少 8 GB 磁盘空间；准备完成后转写不上传音频。')}>
      {runtime?.status === 'ready' ? <StatusDot tone="ok" label={t('已就绪')} />
        : preparing ? <StatusDot tone="accent" label={t('正在准备组件与模型…')} />
        : <Btn size="sm" disabled={!runtime || busy} onClick={() => void act()}>{t('准备模型')}</Btn>}
    </Row>
    {(error || runtime?.status === 'error') && <p className="ac-note" role="alert">{error || t('模型准备失败，请检查网络和磁盘空间后重试。')}</p>}
    <p className="ac-note">{t('仅安装所需模型，不启用说话人分离。')} <a href="https://huggingface.co/FunAudioLLM/SenseVoiceSmall" target="_blank" rel="noreferrer">{t('模型与许可说明')}</a></p>
    {runtime?.status === 'ready' && <details className="ac-disclosure"><summary>{t('高级')}</summary>
      <Row label={t('删除 SenseVoice 组件与模型')} hint={t('删除后需要重新下载才能使用。')}>
        <Btn variant="danger" size="sm" disabled={busy} onClick={() => void act(true)}>{t('删除')}</Btn>
      </Row>
    </details>}
  </div>
}

const ANCHORS: Record<string, string> = { model: 'ai-model', analysis: 'ai-model', vision: 'ai-model', speech: 'ai-speech', cover: 'ai-cover' }
const issueAnchor = (issue: SaveIssue) => issue.role === 'transcription' ? 'ai-speech' : issue.role === 'cover' ? 'ai-cover' : 'ai-model'

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
  const hint = busy[main.id] && !model ? t('正在获取可用模型…')
    : model && list && !list.preview ? t('已为你选好推荐模型，可随时更换。')
    : t('填写 API Key 后自动选择推荐模型。')
  return <>
    <ProviderFields connection={main} placement={placement} onChoose={p => m.chooseProvider('analysis', p)} onEdit={patch => m.editConnection(main, patch)} />
    <Row wide label={t('模型')} hint={hint}>
      <ModelPicker role="analysis" model={model} capability={settings.analysis?.capability} connection={main} list={list} busy={!!busy[main.id]} listError={listErrors[main.id]} mode={settings.analysis_mode}
        onChange={value => m.update({ analysis: { connection_id: main.id, model: value, capability: 'auto' } })}
        onCapability={capability => settings.analysis && m.update({ analysis: { ...settings.analysis, capability } })}
        onRefresh={() => void m.discover(main, true)}
        actions={<Btn variant="text" size="sm" disabled={!model} loading={m.testing} onClick={() => void m.test()}>{t('测试连接')}</Btn>} />
    </Row>
    {showVisual && <Row label={t('画面识别')} hint={isTextOnly(settings, lists)
      ? t('当前模型仅支持文字，只能靠字幕切分。游戏画面、口播较少的内容建议换一个多模态模型再开启。')
      : t('抽样几张画面理解动作与场景。游戏画面、口播较少的内容推荐开启，切分更准；费用略高。关闭后只发送字幕。')}>
      <Switch checked={settings.analysis_mode !== 'subtitle'} onChange={m.setVisual} />
    </Row>}
  </>
}

function TranscriptionSection({ m }: { m: ModelSettingsStore }) {
  const { settings, lists, busy, listErrors } = m
  if (!settings) return null
  const cloud = settings.transcription?.provider === 'cloud'
  const sensevoice = settings.transcription?.provider === 'sensevoice_local'
  const connection = cloud ? connectionOf(settings, 'transcription') : undefined
  const main = mainConnection(settings)
  const options = [
    { label: t('本机运行'), options: [{ value: 'whisper_local', label: t('Whisper · 本地') }, { value: 'sensevoice_local', label: t('SenseVoice · 本地') }] },
    ...providerPickerOptions().map(group => ({ ...group, options: group.options.filter(p => ['openai', 'dashscope', 'infistar', 'api88', 'glm', 'compatible'].includes(p.value)) })).filter(group => group.options.length),
  ]
  return <div id="ai-speech" className="ac-model-section">
    <h3 className="ac-model-section-title">{t('字幕转写')}</h3>
    <p className="ac-note">{t('视频没有字幕时，先把说话声转成字幕。默认在本机免费转写，不上传音频。')}</p>
    <Row wide label={t('转写方式')} hint={t('本地转写免费，首次需下载模型；云端转写无需下载，按用量计费。')}>
      <Select aria-label={t('转写方式')} style={{ width: '100%' }} value={cloud ? connection?.provider : sensevoice ? 'sensevoice_local' : 'whisper_local'} options={options}
        onChange={value => value === 'sensevoice_local' ? m.update({ transcription: { provider: 'sensevoice_local', model: 'SenseVoiceSmall' } }) : value === 'whisper_local' ? m.setTranscriptionLocal(settings.transcription?.model && settings.transcription.provider === 'whisper_local' ? settings.transcription.model : 'base') : m.chooseProvider('transcription', value as ProviderKey)}
        optionRender={option => <span>{option.value === 'whisper_local' ? t('Whisper · 本地') : option.value === 'sensevoice_local' ? t('SenseVoice · 本地') : PROVIDERS[option.value as ProviderKey]?.name}{PROVIDERS[option.value as ProviderKey]?.sponsor && <small style={{ marginLeft: 8, color: 'var(--sub)' }}>{t('赞助')} · {PROVIDERS[option.value as ProviderKey]?.sponsor?.offer}</small>}</span>} />
    </Row>
    {cloud && connection ? <>
      <ProviderFields connection={connection} ariaPrefix={t('转写')} hideProvider placement="settings_model"
        sharedKey={connection.id === main?.id && !!(connection.api_key || connection.has_key)}
        onChoose={p => m.chooseProvider('transcription', p)} onEdit={patch => m.editConnection(connection, patch)} />
      <Row wide label={t('转写模型')} hint={t('将音频发送给所选服务转写，按服务商计费。')}>
        <ModelPicker role="transcription" model={settings.transcription?.model || ''} connection={connection} list={lists[connection.id]} busy={!!busy[connection.id]} listError={listErrors[connection.id]} mode={settings.analysis_mode}
          onChange={model => m.update({ transcription: { provider: 'cloud', connection_id: connection.id, model } })} onRefresh={() => void m.discover(connection, true)} />
      </Row>
    </> : sensevoice ? <SenseVoiceConfig /> : <SpeechRecognitionConfig hideProvider selectedModel={settings.transcription?.model || 'base'} onModelChange={m.setTranscriptionLocal} />}
  </div>
}

function CoverSection({ m }: { m: ModelSettingsStore }) {
  const { settings, lists, busy, listErrors } = m
  if (!settings) return null
  const main = mainConnection(settings)
  const connection = connectionOf(settings, 'cover') || main
  const separate = !!settings.cover && settings.cover.connection_id !== main?.id
  const mainHasImage = !!lists[main?.id || '']?.models.some(x => x.image)
  return <div id="ai-cover" className="ac-model-section">
    <h3 className="ac-model-section-title">{t('封面')}</h3>
    <p className="ac-note">{t('默认用成片里嘉宾最清晰的画面自动设计封面，免费、秒出。想要更有设计感可以改用 AI 生成，生图服务和模型由你自己选择，按所选服务计费。')}</p>
    <Row wide label={t('封面来源')}>
      <Segmented ariaLabel={t('封面来源')} value={settings.cover_enabled ? 'ai' : 'frame'} options={[{ value: 'frame', label: t('自动设计（免费）') }, { value: 'ai', label: t('AI 生成') }]} onChange={value => m.setCoverEnabled(value === 'ai')} />
    </Row>
    {settings.cover_enabled && !main && <p className="ac-note">{t('先在上面选择一家 AI 服务，生图模型会自动选好。')}</p>}
    {settings.cover_enabled && main && <>
      <Row label={t('封面使用其他服务')} hint={separate || mainHasImage || !lists[main?.id || ''] ? t('默认与 AI 服务共用 API Key，无需重复填写。') : t('{{name}} 没有生图模型，可以为封面单独选一家服务。', { name: PROVIDERS[presetKey(main!)]?.name || main?.provider })}>
        <Switch checked={separate} onChange={m.setCoverSeparate} />
      </Row>
      {separate && connection && <ProviderFields connection={connection} ariaPrefix={t('封面')} placement="settings_model" onChoose={p => m.chooseProvider('cover', p)} onEdit={patch => m.editConnection(connection, patch)} />}
      {connection && <Row wide label={t('生图模型')} hint={t('已自动选择推荐的生图模型，可更换。')}>
        <ModelPicker role="cover" model={settings.cover?.model || ''} connection={connection} list={lists[connection.id]} busy={!!busy[connection.id]} listError={listErrors[connection.id]} mode={settings.analysis_mode}
          onChange={model => m.setCoverModel(connection.id, model)} onRefresh={() => void m.discover(connection, true)} />
      </Row>}
      <Row label={t('参考视频画面')} hint={t('开启后会把一张视频截图发送给封面模型，生成的封面更贴近内容。')}>
        <Switch checked={settings.allow_send_frame} onChange={value => m.update({ allow_send_frame: value })} />
      </Row>
    </>}
  </div>
}

export default function AIModelSettings({ requestedSection }: { requestedSection: string }) {
  useTranslation()
  const m = useModelSettings()
  const { settings } = m
  useEffect(() => {
    const anchor = ANCHORS[requestedSection]
    if (!settings || !anchor) return
    const timer = window.setTimeout(() => document.getElementById(anchor)?.scrollIntoView({ block: 'start' }), 0)
    return () => window.clearTimeout(timer)
  }, [requestedSection, !!settings])

  if (!settings) return <Section title={t('AI 模型')}><p className="ac-note">{m.error || t('加载中…')}</p>{m.error && <Btn onClick={() => void m.load()}>{t('重试')}</Btn>}</Section>
  const save = async () => {
    const result = await m.save()
    if (result.issue) document.getElementById(issueAnchor(result.issue))?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }
  return <div className="ac-ai-settings">
    <fieldset className="ac-model-fields" disabled={m.saving}>
      <div id="ai-model" className="ac-model-section">
        <h3 className="ac-model-section-title">{t('AI 服务')}</h3>
        <p className="ac-note">{t('选一家服务、填好 API Key，模型会自动选好。字幕转写和封面默认沿用这把 Key。')}</p>
        <AIServiceFields m={m} placement="settings_model" />
      </div>
      <TranscriptionSection m={m} />
      <CoverSection m={m} />
      <details className="ac-disclosure ac-model-section"><summary>{t('高级')}</summary>
        <Row label={t('文本分块大小')}><input aria-label={t('文本分块大小')} className="ac-input" type="number" min={1000} max={10000} step={500} value={settings.chunk_size} onChange={e => m.update({ chunk_size: Number(e.target.value) })} /></Row>
        <Row label={t('最低评分阈值')}><input aria-label={t('最低评分阈值')} className="ac-input" type="number" min={.1} max={1} step={.05} value={settings.min_score_threshold} onChange={e => m.update({ min_score_threshold: Number(e.target.value) })} /></Row>
        <Row label={t('每个合集最多切片')}><input aria-label={t('每个合集最多切片')} className="ac-input" type="number" min={1} max={20} value={settings.max_clips_per_collection} onChange={e => m.update({ max_clips_per_collection: Number(e.target.value) })} /></Row>
      </details>
    </fieldset>
    {m.error && <p className="studio-error" role="alert">{m.error}</p>}
    <div className="ac-savebar">
      <StatusDot tone={m.dirty ? 'muted' : 'ok'} label={m.dirty ? t('有未保存的更改') : settings.saved ? t('设置已保存') : t('首次使用，保存后生效')} />
      <Btn variant="cta" loading={m.saving} onClick={() => void save()}>{t('保存设置')}</Btn>
    </div>
  </div>
}
