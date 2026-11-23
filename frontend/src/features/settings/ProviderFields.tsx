import { useState } from 'react'
import { Input, Select } from 'antd'
import { t } from '../../i18n'
import { Btn, Row } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import { trackSponsorLinkOpened } from '../../analytics/events'
import { PROVIDERS, contextHintFor, providerPickerOptions, type ProviderKey } from './providers'
import type { Connection } from './modelSettingsApi'
import { presetKey } from './modelSettingsLogic'
import {
  canEditAddress, hintProviderForKey, keyHintCopy, normalizeCompatibleUrl,
  sponsorKeyLink, validationCopy,
} from './providerAccess'
import { offerPastedKey } from './keyGuideWatch'
import { collapseSpaces, normalizeProviderBaseUrl } from './providerUrl'
import { NEUTRAL_PROVIDER_COPY, isTrustedSponsorId, promotionAllowsUpsell, promotionRegisterUrl } from './sponsorPromoState'

const ENDPOINT_ERRORS = new Set(['bad_endpoint', 'connection', 'timeout'])
const KEY_ERRORS = new Set(['invalid_key', 'insufficient_quota', 'permission_denied'])

/**
 * Provider picker + credentials for one connection. Local presets need no key.
 * 「接口地址」is always editable when the preset has (or needs) a Base URL.
 */
export default function ProviderFields({ connection, ariaPrefix = '', hideProvider, sharedKey, placement, keyHint, onChoose, onEdit }: {
  connection?: Connection
  ariaPrefix?: string
  hideProvider?: boolean
  /** The key is reused from the main AI service; offer an explicit "edit" instead of a second field. */
  sharedKey?: boolean
  placement: 'settings_model' | 'home_setup'
  keyHint?: string | null
  onChoose: (provider: ProviderKey) => void
  onEdit: (patch: Partial<Connection>) => void
}) {
  const [editShared, setEditShared] = useState(false)
  const key = connection ? presetKey(connection) : undefined
  const preset = key ? PROVIDERS[key] : undefined
  const label = (text: string) => ariaPrefix ? `${ariaPrefix} · ${text}` : text
  const picker = !hideProvider && <Row wide label={t('提供商')} hint={preset?.hint || t('国内直连、国际服务和本机免费模型都可以选；不确定就从「推荐」开始。')}>
    <Select aria-label={label(t('提供商'))} value={key} placeholder={t('选择一家 AI 服务')} showSearch optionFilterProp="search" style={{ width: '100%' }} options={providerPickerOptions()}
      onChange={onChoose}
      optionRender={option => { const p = PROVIDERS[option.value as ProviderKey]; const upsell = p.sponsor && promotionAllowsUpsell(p.sponsor.id); return <span>{p.name}{upsell && <small style={{ marginLeft: 8, color: 'var(--sub)', fontWeight: 400 }}>{t('赞助')} · {p.sponsor!.offer}</small>}</span> }} />
  </Row>
  if (!connection) return <>{picker}</>
  const failed = connection.validation_status === 'failed'
  const transient = connection.validation_status === 'transient'
  const errorType = connection.validation_error_type || ''
  const urlInfo = key === 'compatible' ? normalizeCompatibleUrl(connection.base_url) : null
  const liveHint = hintProviderForKey(connection.api_key) || (keyHint as ProviderKey | undefined)
  const showHint = liveHint && liveHint !== key
  const shownError = (urlInfo?.warnings.includes('console_host') && 'console_host') || ((failed || transient) && errorType) || ''
  const keyLink = sponsorKeyLink(key)
  const editKey = (value: string) => {
    const next = value.trim()
    if (next !== (connection.api_key ?? '')) onEdit({ api_key: next || (connection.has_key ? undefined : '') })
  }
  const addressEditable = canEditAddress(key)
  const officialHostsOnly = key === 'deepseek' || key === 'gemini' || key === 'api88' || key === 'infistar'
  return <>
    {picker}
    {!preset?.local && (sharedKey && !editShared
      ? <Row wide label={t('API 密钥')} hint={t('与上方 AI 服务共用，一般不用改。')}>
          <span className="ac-hint">{t('已复用密钥')}</span>
          <Btn variant="text" size="sm" onClick={() => setEditShared(true)}>{t('修改密钥')}</Btn>
        </Row>
      : <Row wide label={t('API 密钥')} hint={
          preset?.sponsor
            ? (promotionAllowsUpsell(preset.sponsor.id) ? undefined : t(NEUTRAL_PROVIDER_COPY))
            : preset?.keyUrl
              ? <>{t('在官网创建后粘贴到这里。')} <a className="ac-link" href={preset.keyUrl} onClick={e => { e.preventDefault(); openExternalLink(preset.keyUrl) }}>{t('获取 API Key')} ↗</a>
                {keyLink && keyLink.href !== preset.keyUrl && <> · <a className="ac-link" href={keyLink.href} onClick={e => { e.preventDefault(); openExternalLink(keyLink.href) }}>{keyLink.label} ↗</a></>}
                {preset.referralUrl && <> · <a className="ac-link" data-author-referral="1" href={preset.referralUrl} onClick={e => { e.preventDefault(); trackSponsorLinkOpened({ sponsor: key || connection.provider, target: 'referral', placement }); openExternalLink(preset.referralUrl!) }}>{t('作者推荐链接')} ↗</a></>}</>
              : t('自建服务可留空')
        }>
          <Input.Password aria-label={label(t('API 密钥'))} autoComplete="new-password" value={connection.api_key ?? ''}
            status={failed && KEY_ERRORS.has(errorType) ? 'error' : undefined}
            placeholder={connection.has_key ? t('已保存；留空则不改') : preset?.placeholder || 'sk-…'}
            onPaste={event => {
              const text = event.clipboardData?.getData('text') || ''
              if (text && offerPastedKey(text, key || connection.provider, connection.base_url)) event.preventDefault()
            }}
            onChange={e => editKey(e.target.value)}
            onBlur={e => editKey(e.target.value)} />
          {connection.has_key && connection.api_key_masked && !connection.api_key && (
            <span className="ac-hint" data-testid="masked-api-key">{t('当前已保存密钥：{{masked}}', { masked: connection.api_key_masked })}</span>
          )}
          {(() => {
            const promo = isTrustedSponsorId(connection.provider) ? connection.provider : null
            const href = promo ? promotionRegisterUrl(promo, preset?.sponsor?.registerUrl || '') : null
            if (!promo || !href) return null
            return (
            <span className="ac-sponsor-inline" data-sponsor={promo}>
              <Btn
                size="sm"
                className="ac-btn--pill"
                onClick={() => {
                  const next = promotionRegisterUrl(promo, preset?.sponsor?.registerUrl || '')
                  if (!next) return
                  trackSponsorLinkOpened({ sponsor: promo, target: 'register', placement })
                  openExternalLink(next)
                }}
              >
                {t('settings.providers.one_click')}<span aria-hidden>↗</span>
              </Btn>
            </span>
            )
          })()}
        </Row>)}
    {addressEditable && <Row wide label={t('接口地址')} hint={[
      officialHostsOnly ? t('此服务商使用官方接口。第三方地址请在「添加服务商」中配置。')
        : preset?.local ? t('本机服务用默认地址即可。')
        : connection.base_url ? t('已填默认，可改。')
        : t('请填写，一般以 /v1 结尾。'),
      contextHintFor(key, connection.base_url),
    ].filter(Boolean).join(' ') || undefined}>
      <Input aria-label={label(t('接口地址'))} value={connection.base_url}
        status={(urlInfo?.warnings.includes('console_host') || (failed && ENDPOINT_ERRORS.has(errorType))) ? 'error' : undefined}
        placeholder={preset?.local?.baseUrl || (key === 'dashscope' ? 'https://dashscope.aliyuncs.com/api/v1' : 'https://example.com/v1')}
        onChange={e => onEdit({ base_url: collapseSpaces(e.target.value) })}
        onBlur={() => {
          const stripped = key === 'compatible' ? normalizeCompatibleUrl(connection.base_url).url : connection.base_url
          const url = normalizeProviderBaseUrl(stripped, key)
          if (url !== connection.base_url) onEdit({ base_url: url })
        }} />
    </Row>}
    {showHint && <p className="ac-note">{keyHintCopy(liveHint)}</p>}
    {shownError && <p className={transient ? 'ac-note' : 'ac-note ac-note--error'} role={transient ? 'status' : 'alert'}>{validationCopy(shownError)}</p>}
    {failed && keyLink && KEY_ERRORS.has(errorType) && <p className="ac-note">
      <a className="ac-link" href={keyLink.href} onClick={e => { e.preventDefault(); openExternalLink(keyLink.href) }}>{keyLink.label} ↗</a>
    </p>}
  </>
}
