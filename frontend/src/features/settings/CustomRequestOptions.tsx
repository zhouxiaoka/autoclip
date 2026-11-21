import { Input } from 'antd'
import { t } from '../../i18n'
import { Btn, Row } from '../../ui'
import { requestOptionsIssue, type CustomRequestDraft, type ReasoningEffort } from './customRequestOptions'

const EFFORTS: ReasoningEffort[] = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh']
const LABELS = { none: '不推理', minimal: '最小', low: '低', medium: '中', high: '高', xhigh: '极高' }

/** Optional gateway settings; password input avoids displaying header credentials. */
export default function CustomRequestOptions({ value, onEdit }: {
  value: CustomRequestDraft
  onEdit: (patch: Partial<CustomRequestDraft>) => void
}) {
  const issue = requestOptionsIssue(value)
  return <details className="ac-custom-request-options">
    <summary>{t('高级请求设置')}</summary>
    <p className="ac-note">{t('仅在服务商要求时填写。推理强度和附加参数用于此连接的文字与视觉请求。')}</p>
    <Row wide label={t('HTTP Headers（JSON）')} hint={t('填写字符串键值对。已保存的值不会返回；留空保留，{} 清空。')}>
      <Input.Password aria-label={t('HTTP Headers（JSON）')} autoComplete="new-password"
        value={value._http_headers_text ?? (value.http_headers ? JSON.stringify(value.http_headers) : '')}
        placeholder={value.has_http_headers ? t('已保存；留空则不改') : '{"X-Workspace": "value"}'}
        status={issue === 'headers' ? 'error' : undefined}
        onChange={e => onEdit({ _http_headers_text: e.target.value })} />
      {value.has_http_headers && <Btn size="sm" variant="text" onClick={() => onEdit({ _http_headers_text: '{}' })}>{t('清空 HTTP Headers')}</Btn>}
    </Row>
    <Row wide label={t('推理强度')} hint={t('默认不发送 reasoning_effort；支持的取值由服务商决定。')}>
      <select className="ac-input" aria-label={t('推理强度')} value={value.reasoning_effort || ''}
        onChange={e => onEdit({ reasoning_effort: (e.target.value || null) as ReasoningEffort | null })}>
        <option value="">{t('服务商默认')}</option>
        {EFFORTS.map(effort => <option key={effort} value={effort}>{t(LABELS[effort])}</option>)}
      </select>
    </Row>
    <Row wide label={t('附加请求参数（JSON）')} hint={t('填写服务商支持的 JSON 对象；不能覆盖模型、消息、流式设置或 token 上限。')}>
      <textarea className="ac-input" rows={3} aria-label={t('附加请求参数（JSON）')}
        value={value._extra_body_text ?? (Object.keys(value.extra_body || {}).length ? JSON.stringify(value.extra_body) : '')}
        placeholder='{"thinking": {"type": "enabled"}}'
        onChange={e => onEdit({ _extra_body_text: e.target.value })} />
    </Row>
    {issue && <p className="ac-note ac-note--error" role="alert">{t('自定义请求设置无效，请检查 JSON 和保留字段。')}</p>}
  </details>
}
