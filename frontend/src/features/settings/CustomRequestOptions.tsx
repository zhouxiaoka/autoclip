import { useRef, useState } from 'react'
import { Input, Select } from 'antd'
import { t } from '../../i18n'
import { Btn, Dialog, Icon, Row } from '../../ui'
import { headerEntriesText, parseHeaderEntries, requestOptionsIssue, type CustomRequestDraft, type HeaderEntry, type ReasoningEffort } from './customRequestOptions'

const EFFORTS: ReasoningEffort[] = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh']
const LABELS = { none: '不推理', minimal: '最小', low: '低', medium: '中', high: '高', xhigh: '极高' }
const COMMON_HEADERS = ['User-Agent', 'X-Client-Name', 'X-Title']
type Props = { value: CustomRequestDraft; onEdit: (patch: Partial<CustomRequestDraft>) => void }
const headerText = (value: CustomRequestDraft) => value._http_headers_text ?? (value.http_headers ? JSON.stringify(value.http_headers) : '')

/** Secret headers remain opaque after saving; only locally entered values are editable. */
export default function CustomRequestOptions({ value, onEdit }: Props) {
  const [open, setOpen] = useState(false)
  const issue = requestOptionsIssue(value)
  return <div className="ac-custom-request-options">
    <div className="ac-request-launcher">
      <Btn size="sm" onClick={() => setOpen(true)}>{t('高级请求设置')}</Btn>
      <span className="ac-request-summary">{value.has_http_headers && !headerText(value).trim() ? t('保留已保存的请求头') : t('请求头、推理强度与附加参数')}</span>
    </div>
    {issue && <p className="ac-note ac-note--error" role="alert">{t('自定义请求设置无效，请检查 JSON 和保留字段。')}</p>}
    {open && <Dialog open onClose={() => setOpen(false)} className="ac-request-dialog" title={t('高级请求设置')}
      footer={<Btn size="sm" variant="cta" onClick={() => setOpen(false)}>{t('完成')}</Btn>}>
      <Btn className="ac-request-close" size="sm" variant="text" onClick={() => setOpen(false)}>{t('关闭')}</Btn>
      <HeaderEditor value={value} onEdit={onEdit} />
      <div className="ac-request-generation">
        <Row wide stack label={t('推理强度')} hint={t('默认不发送 reasoning_effort；支持的取值由服务商决定。')}>
          <select className="ac-input" aria-label={t('推理强度')} value={value.reasoning_effort || ''}
            onChange={e => onEdit({ reasoning_effort: (e.target.value || null) as ReasoningEffort | null })}>
            <option value="">{t('服务商默认')}</option>
            {EFFORTS.map(effort => <option key={effort} value={effort}>{t(LABELS[effort])}</option>)}
          </select>
        </Row>
        <Row wide stack label={t('附加请求参数（JSON）')} hint={t('填写服务商支持的 JSON 对象；不能覆盖模型、消息、流式设置或 token 上限。')}>
          <textarea className="ac-input ac-textarea ac-input--mono" aria-label={t('附加请求参数（JSON）')}
            value={value._extra_body_text ?? (Object.keys(value.extra_body || {}).length ? JSON.stringify(value.extra_body) : '')}
            placeholder='{"thinking": {"type": "enabled"}}'
            onChange={e => onEdit({ _extra_body_text: e.target.value })} />
        </Row>
        {issue === 'body' && <p className="ac-note ac-note--error" role="alert">{t('自定义请求设置无效，请检查 JSON 和保留字段。')}</p>}
      </div>
    </Dialog>}
  </div>
}

export function HeaderEditor({ value, onEdit }: Props) {
  const text = headerText(value)
  const nextId = useRef(0)
  const row = (entry: HeaderEntry) => ({ ...entry, id: nextId.current++ })
  const [rows, setRows] = useState<Array<HeaderEntry & { id: number }>>(() => {
    try { const entries = text.trim() ? parseHeaderEntries(text) : []; return (entries.length ? entries : [{ name: '', value: '' }, { name: '', value: '' }]).map(row) }
    catch { return [{ name: '', value: '' }, { name: '', value: '' }].map(row) }
  })
  const [importing, setImporting] = useState(false)
  const [importText, setImportText] = useState('')
  const [feedback, setFeedback] = useState('')
  const invalid = requestOptionsIssue({ _http_headers_text: text }) === 'headers'
  let imported: HeaderEntry[] | null = null
  try { imported = parseHeaderEntries(importText) } catch { /* Import accepts objects, not the API's null/preserve sentinel. */ }
  const importInvalid = imported === null || requestOptionsIssue({ _http_headers_text: importText }) === 'headers'
  const copyable = !!text.trim() && !invalid && rows.some(row => row.name || row.value)
  const names = new Set(rows.map(row => row.name.toLowerCase()))

  const update = (next: typeof rows) => {
    setRows(next)
    setFeedback('')
    const filled = next.filter(row => row.name || row.value)
    // Deleting untouched placeholders must not clear opaque saved credentials.
    const empty = text.trim() || rows.some(row => row.name || row.value) ? '{}' : ''
    onEdit({ _http_headers_text: filled.length ? headerEntriesText(filled) : empty })
  }
  const edit = (index: number, patch: Partial<HeaderEntry>) => update(rows.map((row, i) => i === index ? { ...row, ...patch } : row))
  const importHeaders = () => {
    if (importInvalid || imported === null) return
    const entries = imported
    setRows(entries.map(row))
    onEdit({ _http_headers_text: headerEntriesText(entries) })
    setImportText('')
    setImporting(false)
    setFeedback('')
  }
  const copy = async () => {
    if (!copyable) return
    try {
      await navigator.clipboard.writeText(headerEntriesText(parseHeaderEntries(text)))
      setFeedback(t('已复制请求头 JSON'))
    } catch { setFeedback(t('无法复制，请检查浏览器剪贴板权限。')) }
  }
  const clear = () => { setRows([]); setFeedback(''); onEdit({ _http_headers_text: '{}' }) }

  return <section className="ac-request-headers" aria-label={t('请求头')}>
    <div className="ac-request-toolbar">
      <h4>{t('请求头')}</h4>
      <div className="ac-request-actions">
        <Select className="ac-request-common" popupClassName="ac-request-common-menu" aria-label={t('添加常用请求头')} value={null} placeholder={t('添加常用请求头')}
          options={COMMON_HEADERS.map(name => ({ value: name, label: name, disabled: names.has(name.toLowerCase()) }))}
          onChange={(name: string) => { if (!names.has(name.toLowerCase())) update([...rows, row({ name, value: '' })]) }} />
        <Btn size="sm" variant="text" onClick={() => { setImporting(!importing); setImportText('') }}>{t('导入 JSON')}</Btn>
        <Btn size="sm" variant="text" disabled={!copyable} onClick={() => void copy()}
          title={t('复制仅包含本次填写的请求头，不包含已保存的秘密值。')}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V4H4v12h4" /></svg>
          {t('复制请求头 JSON')}
        </Btn>
      </div>
    </div>
    {value.has_http_headers && <div className="ac-request-saved">
      <p>{t('已保存的请求头不会回传；新填写内容会替换整组请求头。')}</p>
      <Btn size="sm" variant="text" onClick={clear}>{t('清空 HTTP Headers')}</Btn>
    </div>}
    {importing && <div className="ac-request-import">
      <Input.Password aria-label={t('HTTP Headers（JSON）')} autoComplete="new-password" value={importText}
        placeholder='{"X-Client-Name": "AutoClip"}' status={importText && importInvalid ? 'error' : undefined}
        onChange={e => setImportText(e.target.value)} />
      <div className="ac-request-import-actions">
        <Btn size="sm" variant="text" onClick={() => { setImporting(false); setImportText('') }}>{t('取消导入')}</Btn>
        <Btn size="sm" disabled={importInvalid} onClick={importHeaders}>{t('导入并替换')}</Btn>
      </div>
      {importText && importInvalid && <p className="ac-note ac-note--error" role="alert">{t('请求头格式无效：请填写不重复的名称和字符串值。')}</p>}
    </div>}
    <div className="ac-request-header-list">
      {rows.map((row, index) => <div className="ac-request-header-row" key={row.id}>
        <input className="ac-input" aria-label={`${t('请求头名称')} ${index + 1}`} placeholder={t('名称')}
          spellCheck={false} autoComplete="off" value={row.name} aria-invalid={invalid || undefined}
          onChange={e => edit(index, { name: e.target.value })} />
        <Input.Password aria-label={`${t('请求头值')} ${index + 1}`} autoComplete="new-password" placeholder={t('值')}
          value={row.value} status={invalid ? 'error' : undefined} onChange={e => edit(index, { value: e.target.value })} />
        <Btn size="sm" variant="text" className="ac-request-delete" aria-label={`${t('删除请求头')} ${index + 1}`}
          onClick={() => update(rows.filter((_, i) => i !== index))}><Icon.Close size={16} /></Btn>
      </div>)}
    </div>
    <Btn className="ac-request-add" size="sm" onClick={() => update([...rows, row({ name: '', value: '' })])}><Icon.Plus size={15} />{t('添加请求头')}</Btn>
    {invalid && <p className="ac-note ac-note--error" role="alert">{t('请求头格式无效：请填写不重复的名称和字符串值。')}</p>}
    {feedback && <p className="ac-request-feedback" role="status">{feedback}</p>}
  </section>
}
