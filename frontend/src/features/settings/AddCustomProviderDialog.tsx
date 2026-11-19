import { useRef, useState } from 'react'
import { Input, Switch } from 'antd'
import { t } from '../../i18n'
import { Btn, Dialog, Row } from '../../ui'
import { beginExperience } from '../../analytics/experience'
import { modelSettingsApi } from './modelSettingsApi'
import {
  MODEL_TYPES,
  addManualModel,
  draftIssue,
  draftUrlIssue,
  editModel,
  emptyDraft,
  mergeFetched,
  normalizedDraftUrl,
  toggleModel,
  toConnection,
  visibleModels,
  type CustomModelOffer,
  type CustomProviderDraft,
  type ModelType,
} from './customProvider'

const TYPE_LABEL: Record<ModelType, string> = {
  language: '语言',
  asr: '语音识别',
  tts: '语音合成',
  image: '图像生成',
  music: '音乐',
  video: '视频',
}

const ISSUE_COPY = {
  name: '请填写服务商名称',
  url: '请填写接口地址',
  models: '请至少启用一个模型',
  model_id: '请输入模型 ID',
  duplicate: '该模型 ID 已在列表中。',
} as const

/**
 * Add an OpenAI-compatible provider. Fetch /models or type an id; no paste-from-buffer control.
 */
export default function AddCustomProviderDialog({
  open,
  onClose,
  onSubmit,
  onAuto,
}: {
  open: boolean
  onClose: () => void
  onAuto: (draft: CustomProviderDraft) => Promise<{ ok: boolean; error?: string }>
  onSubmit: (draft: CustomProviderDraft) => void
}) {
  const [draft, setDraft] = useState(emptyDraft)
  const [search, setSearch] = useState('')
  const [manualId, setManualId] = useState('')
  const [fetching, setFetching] = useState(false)
  const [fetched, setFetched] = useState(false)
  const [fetchFailed, setFetchFailed] = useState(false)
  const [note, setNote] = useState('')
  const fetchGen = useRef(0)

  const [matching, setMatching] = useState(false)
  const matchingRef = useRef(false)
  const reset = () => {
    fetchGen.current += 1
    setDraft(emptyDraft())
    setSearch('')
    setManualId('')
    setFetching(false)
    setFetched(false)
    setFetchFailed(false)
    setNote('')
  }
  const close = () => { if (!matchingRef.current) { reset(); onClose() } }

  const editCredentials = (patch: Partial<Pick<CustomProviderDraft, 'base_url' | 'api_key'>>) => {
    if (!Object.entries(patch).some(([key, value]) => draft[key as keyof typeof patch] !== value)) return
    fetchGen.current += 1
    setFetching(false)
    setFetched(false)
    setFetchFailed(false)
    setNote('')
    setDraft(current => ({ ...current, ...patch }))
  }

  const fetchModels = async () => {
    if (draftUrlIssue(draft.base_url)) {
      setNote(t(ISSUE_COPY.url))
      return
    }
    const gen = ++fetchGen.current
    setFetching(true)
    setFetchFailed(false)
    setNote('')
    const finish = beginExperience('model_discovery', { placement: 'settings_model', provider: 'compatible', trigger: 'manual' })
    try {
      const result = await modelSettingsApi.fetchList(toConnection({ ...draft, models: draft.models }))
      if (gen !== fetchGen.current) return
      if (result.ok || result.success) {
        const source = 'live'
        finish('completed', { source, preview: false, result_count: result.models.length })
        setDraft(current => mergeFetched(current, result.models))
        setFetched(true)
        setFetchFailed(false)
      } else {
        finish('failed', {}, { response: { status: 0 } })
        setFetchFailed(true)
      }
    } catch {
      if (gen !== fetchGen.current) return
      finish('failed', {}, { response: { status: 0 } })
      setFetchFailed(true)
    } finally {
      if (gen === fetchGen.current) setFetching(false)
    }
  }

  const addManual = () => {
    const result = addManualModel(draft, manualId)
    if (result.issue) { setNote(t(ISSUE_COPY[result.issue])); return }
    setDraft(result.draft)
    setManualId('')
    setNote('')
  }

  const submit = () => {
    const issue = draftIssue(draft)
    if (issue) { setNote(t(ISSUE_COPY[issue])); return }
    onSubmit({ ...draft, base_url: normalizedDraftUrl(draft.base_url), api_key: draft.api_key.trim(), name: draft.name.trim() })
    reset()
  }

  const auto = async () => {
    if (matchingRef.current || draftUrlIssue(draft.base_url)) return
    matchingRef.current = true
    setMatching(true)
    setNote('')
    try {
      const result = await onAuto({
        ...draft, name: draft.name.trim() || new URL(normalizedDraftUrl(draft.base_url)).hostname, models: [],
      })
      if (result.ok) reset()
      else setNote(result.error || t('保存失败，请重试'))
    } finally { matchingRef.current = false; setMatching(false) }
  }

  const models = visibleModels(draft, search)
  const issue = draftIssue(draft)

  return <Dialog open={open} onClose={close} title={t('添加自定义服务商')}
    description={t('自动匹配剪辑、画面理解、转写和封面模型。有云端转写时，音频会发送给这家服务商。')}
    footer={<div className="ac-setup-foot">
      <Btn size="sm" onClick={close}>{t('取消')}</Btn>
      <Btn variant="cta" size="sm" disabled={!!draftUrlIssue(draft.base_url) || fetching} loading={matching} onClick={() => void auto()}>{t('一键配置模型')}</Btn>
    </div>}>
    <fieldset className="ac-model-fields ac-custom-dialog ac-rows" disabled={matching}>
      <Row wide stack label={t('接口地址')} hint={t('OpenAI 兼容')}>
        <input className="ac-input" aria-label={t('接口地址')} value={draft.base_url}
          placeholder="https://example.com/v1"
          onChange={e => editCredentials({ base_url: e.target.value })}
          onBlur={() => editCredentials({ base_url: normalizedDraftUrl(draft.base_url) || draft.base_url })} />
      </Row>
      <Row wide stack label={t('服务密钥（API Key）')} hint={t('API 密钥仅保存在本机')}>
        <Input.Password aria-label="API Key" autoComplete="new-password" value={draft.api_key}
          placeholder={t('sk-…（自建服务可留空）')}
          onChange={e => editCredentials({ api_key: e.target.value })}
          onBlur={e => editCredentials({ api_key: e.target.value.trim() })} />
      </Row>
      <Row wide stack label={t('服务商名称')}>
        <input className="ac-input" aria-label={t('服务商名称')} value={draft.name}
          placeholder={t('可选')}
          onChange={e => setDraft({ ...draft, name: e.target.value })} />
      </Row>
      <details className="studio-details"><summary>{t('手动选择模型')}</summary>
      <div className="ac-custom-toolbar">
        <Btn size="sm" loading={fetching} disabled={fetching} onClick={() => void fetchModels()}>{t('获取模型列表')}</Btn>
        <input className="ac-input" aria-label={t('搜索模型')} value={search} placeholder={t('搜索模型')}
          onChange={e => setSearch(e.target.value)} />
      </div>
      <div className="ac-custom-manual">
        <input className="ac-input" aria-label={t('模型 ID')} value={manualId} placeholder={t('模型 ID')}
          onChange={e => setManualId(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addManual() } }} />
        <Btn size="sm" onClick={addManual}>{t('手动添加模型')}</Btn>
      </div>
      {fetchFailed && <div className="ac-empty"><b>{t('未能获取模型列表。可检查地址和密钥后重试，或手动添加模型 ID。')}</b></div>}
      {!fetchFailed && !models.length && <div className="ac-empty"><b>{fetched || draft.models.length ? t('没有匹配的模型。') : t('还没有模型。先获取列表，或手动添加模型 ID。')}</b></div>}
      {!!models.length && <ul className="ac-custom-models">
        {models.map(model => <ModelRow key={model.id} model={model}
          onToggle={enabled => setDraft(current => toggleModel(current, model.id, enabled))}
          onEdit={patch => setDraft(current => editModel(current, model.id, patch))} />)}
      </ul>}
      <Btn size="sm" disabled={!!issue || fetching} onClick={submit}>{t('添加服务商')}</Btn>
      </details>
      {note && <p className="ac-note" role="alert">{note}</p>}
    </fieldset>
  </Dialog>
}

function ModelRow({ model, onToggle, onEdit }: {
  model: CustomModelOffer
  onToggle: (enabled: boolean) => void
  onEdit: (patch: Partial<CustomModelOffer>) => void
}) {
  const type = model.types[0] || 'language'
  return <li className="ac-custom-model" data-enabled={model.enabled ? 'true' : 'false'}>
    <label className="ac-custom-model-head">
      <input type="checkbox" checked={model.enabled} onChange={e => onToggle(e.target.checked)} />
      <span>
        <b>{model.display_name || model.id}</b>
        {model.display_name && <small className="ac-mono">{model.id}</small>}
      </span>
    </label>
    {model.enabled && <div className="ac-custom-model-edit">
      <Row wide label={t('显示名称')}>
        <input className="ac-input" aria-label={t('显示名称')} value={model.display_name}
          placeholder={model.id} onChange={e => onEdit({ display_name: e.target.value })} />
      </Row>
      <Row wide label={t('模型类型')}>
        <div className="ac-choice-list ac-choice-list--wrap" role="radiogroup" aria-label={t('模型类型')}>
          {MODEL_TYPES.map(value => (
            <button key={value} type="button" role="radio" className="ac-choice ac-choice--sm"
              aria-checked={type === value} onClick={() => onEdit({ types: [value] })}>
              {t(TYPE_LABEL[value])}
            </button>
          ))}
        </div>
      </Row>
      <Row label={t('多模态视觉')} hint={type === 'language' ? undefined : t('仅语言模型可开启视觉。')}>
        <Switch checked={model.vision} disabled={type !== 'language'} onChange={vision => onEdit({ vision })} />
      </Row>
    </div>}
  </li>
}
