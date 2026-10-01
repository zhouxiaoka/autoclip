import { useState } from 'react'
import { Input, Select } from 'antd'
import { t } from '../../i18n'
import { Btn, Row } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import { trackSponsorLinkOpened } from '../../analytics/events'
import { PROVIDERS, providerPickerOptions, type ProviderKey } from './providers'
import type { Connection } from './modelSettingsApi'
import { presetKey } from './modelSettingsLogic'

/**
 * Provider picker + credentials for one connection. Local presets need no key; compatible/local expose the address.
 * Without a connection (first run) only the picker renders, with nothing pre-selected.
 */
export default function ProviderFields({ connection, ariaPrefix = '', hideProvider, sharedKey, placement, onChoose, onEdit }: {
  connection?: Connection
  ariaPrefix?: string
  hideProvider?: boolean
  /** The key is reused from the main AI service; offer an explicit "edit" instead of a second field. */
  sharedKey?: boolean
  placement: 'settings_model' | 'home_setup'
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
          ? <>{t('在供应商网站创建密钥，复制后粘贴到右侧。')} <a className="ac-link" href={preset.keyUrl} onClick={e => { e.preventDefault(); openExternalLink(preset.keyUrl) }}>{t('获取 API Key')} ↗</a></>
          : t('sk-…（自建服务可留空）')}>
          <Input.Password aria-label={label('API Key')} autoComplete="new-password" value={connection.api_key ?? ''}
            placeholder={connection.has_key ? t('已配置；留空保留已有密钥') : preset?.placeholder || 'sk-…'}
            onChange={e => onEdit({ api_key: e.target.value || (connection.has_key ? undefined : '') })} />
        </Row>)}
    {(key === 'compatible' || key === 'dashscope' || preset?.local) && <Row wide label={t('接口地址')} hint={preset?.local ? t('本机服务无需 API Key，保持默认地址即可。') : key === 'dashscope' ? t('使用百炼专属接入地址时填写，留空用默认地址。') : undefined}>
      <Input aria-label={label(t('接口地址'))} value={connection.base_url} placeholder={preset?.local?.baseUrl || (key === 'dashscope' ? 'https://dashscope.aliyuncs.com/api/v1' : 'https://example.com/v1')} onChange={e => onEdit({ base_url: e.target.value })} />
    </Row>}
  </>
}
