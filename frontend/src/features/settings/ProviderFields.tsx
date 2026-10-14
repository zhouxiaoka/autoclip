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

const ENDPOINT_ERRORS = new Set(['bad_endpoint', 'console_host', 'connection', 'timeout'])
const KEY_ERRORS = new Set(['invalid_key', 'insufficient_quota', 'group_forbidden'])

/**
 * Provider picker + credentials for one connection. Local presets need no key; only
 * 自定义兼容 / local expose the address. Locked presets hide the URL.
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
      optionRender={option => { const p = PROVIDERS[option.value as ProviderKey]; return <span>{p.name}{p.sponsor && <small style={{ marginLeft: 8, color: 'var(--sub)', fontWeight: 400 }}>{t('赞助')} · {p.sponsor.offer}</small>}</span> }} />
  </Row>
  if (!connection) return <>{picker}</>
  const failed = connection.validation_status === 'failed'
  const errorType = connection.validation_error_type || ''
  const urlInfo = key === 'compatible' ? normalizeCompatibleUrl(connection.base_url) : null
  const liveHint = hintProviderForKey(connection.api_key) || (keyHint as ProviderKey | undefined)
  const showHint = liveHint && liveHint !== key
  const shownError = (urlInfo?.warnings.includes('console_host') && 'console_host') || (failed && errorType) || ''
  const keyLink = sponsorKeyLink(key)
  const addressEditable = canEditAddress(key)
  return <>
    {picker}
    {preset?.sponsor && <div className="ac-sponsor">
      <div className="ac-sponsor-text"><b>{preset.name}<span className="ac-badge">{t('赞助')}</span></b>
        <span>{preset.sponsor.description}</span>
        <small>{t('该链接含推广分成，用于支持项目维护；领取条件以活动页面为准。')}</small></div>
      <div className="ac-sponsor-actions">
        <Btn variant="cta" size="sm" onClick={() => { trackSponsorLinkOpened({ sponsor: preset.sponsor!.id, target: 'register', placement }); openExternalLink(preset.sponsor!.registerUrl) }}>{t('注册并领取体验额度')}</Btn>
        <Btn variant="text" size="sm" onClick={() => { trackSponsorLinkOpened({ sponsor: preset.sponsor!.id, target: 'guide', placement }); openExternalLink(preset.sponsor!.guideUrl) }}>{t('接入说明')}</Btn>
      </div>
    </div>}
    {!preset?.local && (sharedKey && !editShared
      ? <Row wide label={t('服务密钥（API Key）')} hint={t('共用 API Key，无需重复填写。')}>
          <span className="ac-hint">{t('已复用 AI 服务的密钥')}</span>
          <Btn variant="text" size="sm" onClick={() => setEditShared(true)}>{t('修改密钥')}</Btn>
        </Row>
      : <Row wide label={t('服务密钥（API Key）')} hint={preset?.keyUrl
          ? <>{t('在供应商网站创建密钥，复制后粘贴到右侧。')} <a className="ac-link" href={preset.keyUrl} onClick={e => { e.preventDefault(); openExternalLink(preset.keyUrl) }}>{t('获取 API Key')} ↗</a>
            {keyLink && keyLink.href !== preset.keyUrl && <> · <a className="ac-link" href={keyLink.href} onClick={e => { e.preventDefault(); openExternalLink(keyLink.href) }}>{keyLink.label} ↗</a></>}</>
          : t('sk-…（自建服务可留空）')}>
          <Input.Password aria-label={label('API Key')} autoComplete="new-password" value={connection.api_key ?? ''}
            status={failed && KEY_ERRORS.has(errorType) ? 'error' : undefined}
            placeholder={connection.has_key ? t('已配置；留空保留已有密钥') : preset?.placeholder || 'sk-…'}
            onChange={e => onEdit({ api_key: e.target.value.trim() || (connection.has_key ? undefined : '') })}
            onBlur={e => onEdit({ api_key: e.target.value.trim() || (connection.has_key ? undefined : '') })} />
        </Row>)}
    {addressEditable && <Row wide label={t('接口地址')} hint={[preset?.local ? t('本机服务无需 API Key，保持默认地址即可。') : '', contextHintFor(key, connection.base_url)].filter(Boolean).join(' ') || undefined}>
      <Input aria-label={label(t('接口地址'))} value={connection.base_url}
        status={(urlInfo?.warnings.includes('console_host') || (failed && ENDPOINT_ERRORS.has(errorType))) ? 'error' : undefined}
        placeholder={preset?.local?.baseUrl || 'https://example.com/v1'}
        onChange={e => onEdit({ base_url: e.target.value.replace(/\s+/g, '') })}
        onBlur={() => {
          const { url } = normalizeCompatibleUrl(connection.base_url)
          if (url !== connection.base_url) onEdit({ base_url: url })
        }} />
    </Row>}
    {showHint && <p className="ac-note">{keyHintCopy(liveHint)}</p>}
    {shownError && <p className="ac-note ac-note--error" role="alert">{validationCopy(shownError)}</p>}
    {failed && keyLink && KEY_ERRORS.has(errorType) && <p className="ac-note">
      <a className="ac-link" href={keyLink.href} onClick={e => { e.preventDefault(); openExternalLink(keyLink.href) }}>{keyLink.label} ↗</a>
    </p>}
  </>
}
