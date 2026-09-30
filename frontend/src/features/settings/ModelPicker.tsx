import { useState, type ReactNode } from 'react'
import { Select } from 'antd'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import type { Capability, Connection, ModelEntry, ModelList, ModelSettings } from './modelSettingsApi'
import { analysisModels } from './modelDefaults'
import { connectionReady, presetKey, type Role } from './modelSettingsLogic'

export function eligibleModels(role: Role, models: ModelEntry[], mode: ModelSettings['analysis_mode']) {
  if (role === 'cover') return models.filter(m => m.image)
  if (role === 'transcription') return models.filter(m => m.asr)
  return analysisModels(models, role === 'vision' ? 'visual' : mode)
}

/**
 * Searchable model list for one role. Custom IDs are allowed where the service cannot enumerate them.
 * Refresh appears only when the list is not the live account list; a discovery error sits next to the field.
 */
export default function ModelPicker({ role, model, capability, connection, list, busy, listError, mode, actions, onChange, onCapability, onRefresh }: {
  role: Role
  model: string
  capability?: Capability
  connection?: Connection
  list?: ModelList
  busy: boolean
  listError?: string
  mode: ModelSettings['analysis_mode']
  actions?: ReactNode
  onChange: (model: string) => void
  onCapability?: (capability: Capability) => void
  onRefresh: () => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const models = list ? eligibleModels(role, list.models, mode) : []
  const custom = search.trim()
  const allowCustom = role !== 'transcription' || connection?.provider === 'compatible'
  const customOption = allowCustom && custom && !models.some(m => m.id === custom) ? [{ value: custom, label: `${t('使用自定义型号')}：${custom}` }] : []
  const tag = (m: ModelEntry) => role === 'analysis' || role === 'vision'
    ? (m.capability ? ` · ${m.capability === 'multimodal' ? t('多模态') : t('仅文字')}` : '')
    : role === 'transcription' && m.asr_note ? ` · ${t(m.asr_note)}` : ''
  const unknownCapability = (role === 'analysis' || role === 'vision') && !!model && !!connection && presetKey(connection) === 'compatible' && !list?.models.find(m => m.id === model)?.capability
  const stale = !!connection && connectionReady(connection) && !busy && (!!listError || !list || list.source !== 'live')
  // The generic preview warning is already covered by the row hint; account-specific warnings stay visible.
  const warning = list?.warning && list.warning !== '公开目录预览，填写 API Key 后确认账号可用模型。' ? t(list.warning) : ''
  return <div style={{ width: '100%' }}>
    <Select aria-label={t(role === 'cover' ? '生图模型' : role === 'transcription' ? '转写模型' : '模型')} disabled={!connection} showSearch value={model || undefined} style={{ width: '100%' }}
      open={open} onDropdownVisibleChange={o => { setOpen(o); if (!o) setSearch('') }} onSearch={setSearch}
      placeholder={busy ? t('正在获取可用模型…') : t(role === 'transcription' && connection?.provider !== 'compatible' ? '选择转写模型' : '选择或搜索模型，也可手动输入模型名')}
      loading={busy} optionFilterProp="value"
      notFoundContent={t(role === 'cover' ? '该服务没有可用的生图模型。' : '暂无可用模型，请检查 API Key 后刷新。')}
      options={[...customOption, ...models.map(m => ({ value: m.id, label: `${m.id}${tag(m)}`, disabled: role === 'transcription' && !m.asr_supported }))]}
      onChange={(value: string) => { onChange(value); setOpen(false) }} />
    {(actions || stale) && <div className="ac-model-control-action">
      {actions}
      {stale && <Btn variant="text" size="sm" onClick={onRefresh}>{t('刷新')}</Btn>}
    </div>}
    {(listError || warning) && <p className="ac-note ac-note--error">{listError || warning}</p>}
    {unknownCapability && onCapability && <Select aria-label={t('自定义模型类型')} style={{ width: '100%', marginTop: 8 }} value={capability || 'auto'}
      options={[{ value: 'auto', label: t('自动识别') }, { value: 'multimodal', label: t('多模态') }, { value: 'text', label: t('仅文字') }]} onChange={onCapability} />}
    {role === 'transcription' && models.length > 0 && !models.some(m => m.asr_supported) && <p className="ac-note">{t('该供应商的 ASR 尚未适配字幕时间戳，请选择阿里云、OpenAI 或本地 Whisper。')}</p>}
    {role === 'transcription' && (list?.preview || models.some(m => m.asr_preview)) && !model && !(warning || listError) && <small className="ac-note">{t('模型目录可预览；实际可用性以账号权限和服务商开通状态为准。')}</small>}
  </div>
}
