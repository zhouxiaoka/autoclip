import { trackExperience } from '../../analytics/experience'
import { trackSponsorLinkOpened } from '../../analytics/events'
import { telemetryId } from '../../analytics/workflow'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import { t } from '../../i18n'
import { Btn, Dialog, Icon, StatusDot } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import { useModelSettings } from './useModelSettings'
import { PROVIDERS } from './providers'
import ProviderFields from './ProviderFields'
import { connectionReady, mainConnection, needsSetup } from './modelSettingsLogic'
import {
  FIRST_RUN_CHOICES,
  FIRST_RUN_DEFAULT,
  firstRunPrimaryAction,
  firstRunPrimaryLabel,
  firstRunSponsor,
  type FirstRunChoice,
} from './firstRunGuidance'

const DISMISSED_KEY = 'autoclip.firstRunSetup.dismissed'

const OPTION_COPY: Record<FirstRunChoice, { title: () => string; detail: () => string; badge?: () => string }> = {
  api88: {
    title: () => PROVIDERS.api88.short,
    detail: () => PROVIDERS.api88.sponsor?.description || PROVIDERS.api88.hint,
    badge: () => t('推荐 · 新用户赠送额度'),
  },
  infistar: {
    title: () => PROVIDERS.infistar.short,
    detail: () => PROVIDERS.infistar.sponsor?.description || PROVIDERS.infistar.hint,
    badge: () => PROVIDERS.infistar.sponsor ? `${t('赞助')} · ${PROVIDERS.infistar.sponsor.offer}` : t('赞助'),
  },
  other: {
    title: () => t('其他服务商'),
    detail: () => t('去设置页选择 OpenAI、DeepSeek 等'),
  },
}

/**
 * First-launch chooser: 88API / Infistar / other providers. "Later" hides it for the session;
 * a blocked import can reopen it. One-click opens the sponsor site; deeplink write is L1.
 */
export default function FirstRunSetup({ onStatus, openRequest = 0 }: { onStatus?: (needed: boolean) => void; openRequest?: number }) {
  useTranslation()
  const navigate = useNavigate()
  const m = useModelSettings('home_setup')
  const { settings } = m
  const [open, setOpen] = useState(false)
  const [choice, setChoice] = useState<FirstRunChoice>(FIRST_RUN_DEFAULT)
  const [step, setStep] = useState<'choose' | 'connect'>('choose')
  const initial = useRef<boolean | null>(null)
  if (settings && initial.current === null) initial.current = needsSetup(settings)
  const needed = !!settings && !!initial.current && !settings.saved
  useEffect(() => { if (settings) onStatus?.(needed) }, [settings, needed])
  useEffect(() => {
    if (!needed) { setOpen(false); return }
    let dismissed = false
    try { dismissed = sessionStorage.getItem(DISMISSED_KEY) === '1' } catch { /* restricted storage: just show it */ }
    if (!dismissed) setOpen(true)
  }, [needed])
  useEffect(() => { if (openRequest > 0 && needed) setOpen(true) }, [openRequest])
  const presentation = useRef('')
  const showing = open && needed && !!settings
  useEffect(() => {
    if (!showing) {
      presentation.current = ''
      setStep('choose')
      setChoice(FIRST_RUN_DEFAULT)
      return
    }
    if (!presentation.current) {
      presentation.current = telemetryId()
      trackExperience('setup_presented', { placement: 'home_setup', presentation_id: presentation.current, trigger: openRequest > 0 ? 'import_blocked' : 'initial' })
    }
  }, [showing, openRequest])
  const action = (value: 'later' | 'open_settings' | 'one_click', provider?: 'api88' | 'infistar') =>
    trackExperience('setup_action', { placement: 'home_setup', presentation_id: presentation.current, action: value, ...(provider ? { provider } : {}) })
  if (!settings || !needed) return null

  const later = () => { action('later'); try { sessionStorage.setItem(DISMISSED_KEY, '1') } catch { /* ignore */ } setOpen(false) }
  const goSettings = () => {
    action('open_settings')
    setOpen(false)
    navigate('/settings?section=ai', { state: { settingsEntry: 'home_setup' } })
  }
  const primary = () => {
    const next = firstRunPrimaryAction(choice)
    if (next === 'open_settings') { goSettings(); return }
    const sponsor = firstRunSponsor(choice)
    if (!sponsor) return
    const preset = PROVIDERS[sponsor]
    action('one_click', sponsor)
    if (preset.sponsor) {
      trackSponsorLinkOpened({ sponsor, target: 'register', placement: 'home_setup' })
      openExternalLink(preset.sponsor.registerUrl)
    }
    m.chooseProvider('analysis', sponsor)
    setStep('connect')
  }
  const main = mainConnection(settings)
  const model = settings.analysis?.model
  const fetching = !!main && !!m.busy[main.id] && !model
  const status = fetching ? t('正在获取可用模型…')
    : model ? t('已选好模型：{{model}}', { model })
    : main && connectionReady(main) ? t('请确认 API Key，或直接输入模型名')
    : t('等待 API Key')
  const label = firstRunPrimaryLabel(choice, firstRunSponsor(choice) ? PROVIDERS[firstRunSponsor(choice)!].short : '')
  const connecting = step === 'connect' && !!main

  return <Dialog open={open} onClose={later} title={t('选择 AI 服务商')}
    description={connecting ? t('在浏览器完成注册后，把 API 密钥粘贴到下方。') : undefined}
    footer={<div className="ac-setup-foot">
      {connecting
        ? <Btn variant="text" size="sm" onClick={() => setStep('choose')}>{t('返回')}</Btn>
        : <Btn variant="text" size="sm" onClick={later}>{t('稍后设置')}</Btn>}
      {connecting
        ? <Btn variant="cta" size="sm" loading={m.saving} disabled={fetching} onClick={() => void m.save()}>{t('连接并保存')}</Btn>
        : <Btn variant="cta" size="sm" onClick={primary}>{t(label.key, label.values)}</Btn>}
    </div>}>
    <ConfigProvider theme={{ token: { zIndexPopupBase: 1300 } }}>
      <div className="ac-setup-dialog ac-ai-settings">
        {connecting && main ? <>
          <div className="ac-rows">
            <ProviderFields connection={main} hideProvider placement="home_setup"
              keyHint={m.keyHints[main.id]}
              onChoose={p => m.chooseProvider('analysis', p)} onEdit={patch => m.editConnection(main, patch)} />
          </div>
          {m.error && <p className="studio-error" role="alert">{m.error}</p>}
          <div className="ac-setup-status"><StatusDot tone={fetching ? 'accent' : model ? 'ok' : 'muted'} label={status} /></div>
        </> : <>
          <div className="ac-choice-list" role="radiogroup" aria-label={t('选择 AI 服务商')}>
            {FIRST_RUN_CHOICES.map(id => {
              const copy = OPTION_COPY[id]
              return <button key={id} type="button" role="radio" className="ac-choice" aria-checked={choice === id}
                onClick={() => setChoice(id)}>
                <span className="ac-choice-text">
                  <b>{copy.title()}{copy.badge && <span className="ac-badge">{copy.badge()}</span>}</b>
                  <span>{copy.detail()}</span>
                </span>
                {choice === id && <Icon.Check />}
              </button>
            })}
          </div>
          <p className="ac-note">{t('可随时在设置中更换')}</p>
        </>}
      </div>
    </ConfigProvider>
  </Dialog>
}
