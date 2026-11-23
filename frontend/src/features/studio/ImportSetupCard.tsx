import { trackExperience } from '../../analytics/experience'
import { trackSponsorLinkOpened } from '../../analytics/events'
import { telemetryProvider } from '../../analytics/successRateContract'
import { telemetryId } from '../../analytics/workflow'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { Btn, Icon } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import { useQuickConnect } from '../settings/useQuickConnect'
import { PROVIDERS, recommendedSetupProviders, type ProviderKey } from '../settings/providers'
import {
  NEUTRAL_PROVIDER_COPY,
  isTrustedSponsorId,
  promotionAllowsUpsell,
  promotionRecommends,
  promotionRegisterUrl,
  promotionSetupChoice,
} from '../settings/sponsorPromoState'
import { useSponsorPromo } from '../settings/sponsorPromoWatch'

const STEPS = ['provider', 'key', 'connect'] as const
type Step = (typeof STEPS)[number]

const STEP_LABEL: Record<Step, () => string> = {
  provider: () => t('选择服务商'),
  key: () => t('填写密钥'),
  connect: () => t('连接并保存'),
}

function selectableProvider(id: string | null): ProviderKey | null {
  if (!id) return null
  return (Object.keys(PROVIDERS) as ProviderKey[]).find(key => key === id) || null
}

/**
 * Replaces the import zone until an analysis model is saved.
 * Dismissing the first-run overlay does not unmount this card.
 */
export default function ImportSetupCard({ onExample, exampleBusy = false, keptMaterial = false }: {
  onExample?: () => void
  exampleBusy?: boolean
  keptMaterial?: boolean
}) {
  const translation = useTranslation() as { i18n?: { language?: string } } | void
  const language = translation && translation.i18n ? translation.i18n.language : undefined
  const promo = useSponsorPromo()
  const navigate = useNavigate()
  const connect = useQuickConnect('import_card')
  const [step, setStep] = useState<Step>('provider')
  const [provider, setProvider] = useState<ProviderKey | null>(() => selectableProvider(promotionSetupChoice(recommendedSetupProviders())))
  const recommended = recommendedSetupProviders()
  const providers = provider && !recommended.includes(provider) ? [...recommended, provider] : recommended
  const touched = useRef(false)
  const lockedProvider = useRef<ProviderKey | null>(null)
  useEffect(() => {
    if (lockedProvider.current || touched.current || step !== 'provider') return
    setProvider(selectableProvider(promotionSetupChoice(recommendedSetupProviders())))
  }, [promo, step, language])
  const [apiKey, setApiKey] = useState('')
  const presentation = useRef('')
  useEffect(() => {
    if (presentation.current) return
    presentation.current = telemetryId()
    trackExperience('setup_presented', {
      placement: 'import_card',
      presentation_id: presentation.current,
      trigger: 'initial',
    })
  }, [])
  const done = (name: Step) => {
    trackExperience('setup_step_done', {
      placement: 'import_card',
      step: name,
      presentation_id: presentation.current,
      provider: telemetryProvider(provider),
    })
  }
  const identity = lockedProvider.current || provider
  const preset = identity ? PROVIDERS[identity] : undefined
  const index = STEPS.indexOf(step)
  const canContinue = !!provider && providers.includes(provider)
  const next = () => {
    if (step === 'provider') {
      if (!canContinue || !provider) return
      lockedProvider.current = provider
      touched.current = true
      connect.selectProvider(provider)
      done('provider')
      setStep('key')
      return
    }
    if (step === 'key') {
      const key = apiKey.trim()
      if (!key) return
      connect.setKey(key)
      done('key')
      setStep('connect')
    }
  }
  const back = () => {
    if (step === 'key') {
      lockedProvider.current = null
      setApiKey('')
    }
    setStep(STEPS[index - 1])
  }
  const save = async () => {
    const result = await connect.connect()
    if (result.ok && !result.validationFailed) done('connect')
  }
  const promoId = (id: string | null | undefined): string | null =>
    isTrustedSponsorId(id) ? id! : null
  const keyHref = () => {
    const sponsor = promoId(identity)
    if (!sponsor) return null
    return promotionRegisterUrl(sponsor, preset?.sponsor?.registerUrl || '')
  }
  const openKey = () => {
    const sponsor = promoId(identity)
    const href = sponsor ? promotionRegisterUrl(sponsor, preset?.sponsor?.registerUrl || '') : null
    if (!sponsor || !href) return
    trackSponsorLinkOpened({ sponsor, target: 'register', placement: 'import_card' })
    openExternalLink(href)
  }

  return <div className="ac-import-setup">
    <div>
      <h2>{t('先连接 AI 服务')}</h2>
      <p className="studio-muted">{t('选一个推荐服务商，填入密钥并保存。完成后就可以导入视频。')}</p>
    </div>
    <ol className="ac-import-steps">
      {STEPS.map((name, at) => <li key={name} data-current={name === step ? 'true' : undefined} data-done={at < index ? 'true' : undefined}>{at + 1} {STEP_LABEL[name]()}</li>)}
    </ol>
    {step === 'provider' && <div className="ac-choice-list" role="radiogroup" aria-label={t('选择服务商')} data-setup-empty={providers.length ? undefined : '1'}>
      {providers.map(id => {
        const row = PROVIDERS[id]
        return <button key={id} type="button" role="radio" className="ac-choice" aria-checked={provider === id} onClick={() => { touched.current = true; setProvider(id) }}>
          <span className="ac-choice-text">
            <b>{row.short}{promotionRecommends(id) && <span className="ac-badge">{t('推荐')}</span>}{row.sponsor && !promotionRecommends(id) && promotionAllowsUpsell(id) && <span className="ac-badge">{row.sponsor.offer}</span>}</b>
            <span>{row.sponsor && promotionAllowsUpsell(id) ? row.sponsor.description : row.sponsor ? t(NEUTRAL_PROVIDER_COPY) : row.hint}</span>
          </span>
          {provider === id && <Icon.Check />}
        </button>
      })}
    </div>}
    {step === 'key' && <label className="studio-field">
      {t('API 密钥')}
      <input type="password" autoComplete="new-password" aria-label={t('API 密钥')} placeholder={preset?.placeholder || 'sk-…'} value={apiKey} onChange={event => setApiKey(event.target.value)} />
      {keyHref() && <button type="button" className="studio-link" onClick={openKey}>{t('获取 API Key')}</button>}
    </label>}
    {step === 'connect' && <div>
      <p className="studio-muted">{t('自动匹配剪辑、画面理解、转写和封面模型。有云端转写时，音频会发送给这家服务商。')}</p>
      <p className="studio-muted">{preset?.short}</p>
      {connect.error && <p className="studio-error" role="alert">{connect.error}</p>}
    </div>}
    {keptMaterial && <p className="studio-muted">{t('刚才的链接或文件会留着，连上之后可以继续导入。')}</p>}
    <div className="ac-import-setup-foot">
      <div className="ac-import-setup-side">
        {index > 0 && <Btn variant="text" size="sm" onClick={back}>{t('返回')}</Btn>}
        <button type="button" className="studio-link" disabled={exampleBusy} onClick={() => onExample?.()}>{t('先用示例视频看看效果')}</button>
        {step === 'provider' && <button type="button" className="studio-link" onClick={() => navigate('/settings?section=ai&return_import=1', { state: { settingsEntry: 'home_setup' } })}>{t('去设置选择其他服务商')}</button>}
      </div>
      {step === 'connect'
        ? <Btn variant="cta" size="sm" loading={connect.saving} disabled={!connect.settings} onClick={() => void save()}>{t('一键配置模型')}</Btn>
        : <Btn variant="cta" size="sm" disabled={!connect.settings || (step === 'provider' && !canContinue) || (step === 'key' && !apiKey.trim())} onClick={next}>{t('下一步')}</Btn>}
    </div>
  </div>
}
