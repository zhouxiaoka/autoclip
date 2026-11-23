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
import { useQuickConnect } from './useQuickConnect'
import { PROVIDERS } from './providers'
import ModelPicker from './ModelPicker'
import ProviderFields from './ProviderFields'
import { connectionReady, mainConnection, needsSetup } from './modelSettingsLogic'
import { setClipboardBannerSuppressed } from './keyGuideBus'
import { readSponsorPromo, subscribeSponsorPromo } from './sponsorPromoWatch'
import {
  NEUTRAL_PROVIDER_COPY,
  promotionAllowsUpsell,
  promotionRecommends,
  promotionRegisterUrl,
  readPromoSnapshot,
  resolvePromoSlice,
  subscribePromoSnapshot,
} from './sponsorPromoState'
import {
  FIRST_RUN_CHOICES,
  FIRST_RUN_DEFAULT,
  firstRunOtherDefault,
  firstRunPrimaryAction,
  firstRunPrimaryLabel,
  firstRunSponsor,
} from './firstRunGuidance'


function optionTitle(id: string): (() => string) | null {
  if (id === 'other') return () => t('其他服务商')
  if (!firstRunSponsor(id) || !PROVIDERS[id as keyof typeof PROVIDERS]) return null
  return () => PROVIDERS[id as keyof typeof PROVIDERS].short
}

function choiceDetail(id: string, otherName: string): string {
  if (id === 'other') return t('建议先连接 {{name}}', { name: otherName })
  const preset = PROVIDERS[id as keyof typeof PROVIDERS]
  if (preset?.sponsor && promotionAllowsUpsell(id)) return preset.sponsor.description
  if (preset?.sponsor) return t(NEUTRAL_PROVIDER_COPY)
  return preset?.hint || ''
}

/** Latest accepted choices. A locked selection stays even after it leaves the promotion. */
function choicesFor(latest: readonly string[], selected: string, locked: boolean): string[] {
  const shown = [...latest]
  if (locked && selected && !shown.includes(selected)) {
    const other = shown.indexOf('other')
    if (other === -1) shown.push(selected)
    else shown.splice(other, 0, selected)
  }
  return shown
}

/** The welcome screen opens this chooser when the user starts their own video. */
export default function FirstRunSetup({ onStatus, openRequest = 0 }: { onStatus?: (needed: boolean) => void; openRequest?: number }) {
  const navigate = useNavigate()
  const m = useQuickConnect('home_setup')
  const { settings } = m
  const [open, setOpen] = useState(false)
  const [choice, setChoice] = useState<string>(FIRST_RUN_DEFAULT)
  const choiceRef = useRef(choice)
  const [choices, setChoices] = useState<readonly string[]>(FIRST_RUN_CHOICES)
  const [notices, setNotices] = useState<Record<string, Record<string, string>>>({})
  const touched = useRef(false)
  const frozen = useRef(false)
  const stepRef = useRef<'choose' | 'connect'>('choose')
  const [step, setStep] = useState<'choose' | 'connect'>('choose')
  const initial = useRef<boolean | null>(null)
  if (settings && initial.current === null) initial.current = needsSetup(settings)
  const [connectingAttempt, setConnectingAttempt] = useState(false)
  const needed = !!settings && !!initial.current && (!settings.saved || connectingAttempt)
  const saveConnection = async (manual = false) => {
    setConnectingAttempt(true)
    const result = manual ? await m.save() : await m.connect()
    if (result.ok && !result.validationFailed) setConnectingAttempt(false)
  }
  useEffect(() => { if (settings) onStatus?.(needed) }, [settings, needed])
  useEffect(() => {
    if (!needed) setOpen(false)
  }, [needed])
  useEffect(() => { if (openRequest > 0 && needed) setOpen(true) }, [openRequest])
  const presentation = useRef('')
  const showing = open && needed && !!settings
  useEffect(() => {
    if (!showing || step !== 'connect') return
    setClipboardBannerSuppressed(true)
    return () => setClipboardBannerSuppressed(false)
  }, [showing, step])
  const translation = useTranslation() as { i18n?: { language?: string } } | void
  const language = translation && translation.i18n ? translation.i18n.language : undefined
  const languageRef = useRef(language)
  languageRef.current = language
  const applyPromoRef = useRef<(() => void) | null>(null)
  useEffect(() => {
    if (!showing) {
      presentation.current = ''
      touched.current = false
      frozen.current = false
      stepRef.current = 'choose'
      setStep('choose')
      choiceRef.current = FIRST_RUN_DEFAULT
      setChoice(FIRST_RUN_DEFAULT)
      setChoices(FIRST_RUN_CHOICES)
      setNotices({})
      applyPromoRef.current = null
      return
    }
    if (!presentation.current) {
      presentation.current = telemetryId()
      trackExperience('setup_presented', { placement: 'home_setup', presentation_id: presentation.current, trigger: openRequest === 1 ? 'initial' : 'import_blocked' })
    }
    const apply = () => {
      const applied = readSponsorPromo()
      const snap = readPromoSnapshot()
      const resolved = resolvePromoSlice(snap, languageRef.current) || resolvePromoSlice(applied, languageRef.current)
      const nextChoices = resolved?.choices
      if (!nextChoices) return
      setNotices(snap?.notices || applied?.notices || {})
      const locked = touched.current || frozen.current || stepRef.current !== 'choose'
      setChoices(choicesFor(nextChoices, choiceRef.current, locked))
      if (locked) return
      const nextDefault = resolved?.defaultChoice || FIRST_RUN_DEFAULT
      choiceRef.current = nextDefault
      setChoice(nextDefault)
    }
    applyPromoRef.current = apply
    apply()
    const stopPromo = subscribeSponsorPromo(apply)
    const stopSnap = subscribePromoSnapshot(apply)
    return () => { applyPromoRef.current = null; stopPromo(); stopSnap() }
  }, [showing, openRequest])
  useEffect(() => {
    if (showing) applyPromoRef.current?.()
  }, [showing, language])
  const otherDefault = firstRunOtherDefault(language)
  const noticeLanguage = (language || 'zh').toLowerCase().split('-')[0]
  const otherName = PROVIDERS[otherDefault].short
  const action = (value: 'later' | 'open_settings' | 'one_click' | 'connect_recommended', provider?: string) =>
    trackExperience('setup_action', { placement: 'home_setup', presentation_id: presentation.current, action: value, ...(provider ? { provider } : {}) })
  if (!settings || !needed) return null

  // Only the overlay closes. The import zone stays on the setup card until analysis is actually saved.
  const later = () => { if (m.saving) return; setConnectingAttempt(false); action('later'); setOpen(false) }
  const goSettings = () => {
    action('open_settings')
    setOpen(false)
    navigate('/settings?section=ai&return_import=1', { state: { settingsEntry: 'home_setup' } })
  }
  const primary = () => {
    frozen.current = true
    touched.current = true
    const next = firstRunPrimaryAction(choice)
    if (next === 'open_settings') { goSettings(); return }
    if (next === 'connect_recommended') {
      action('connect_recommended', otherDefault)
      m.chooseProvider('analysis', otherDefault)
      stepRef.current = 'connect'
      setStep('connect')
      return
    }
    const sponsor = firstRunSponsor(choice) as keyof typeof PROVIDERS | null
    if (!sponsor || !PROVIDERS[sponsor]) return
    action('one_click', sponsor)
    const snap = readPromoSnapshot()
    const packaged = !snap || snap.source === 'bundled' ? (PROVIDERS[sponsor].sponsor?.registerUrl || '') : ''
    const href = promotionRegisterUrl(sponsor, packaged)
    if (href) {
      trackSponsorLinkOpened({ sponsor, target: 'register', placement: 'home_setup' })
      openExternalLink(href)
    }
    m.chooseProvider('analysis', sponsor)
    stepRef.current = 'connect'
    setStep('connect')
  }
  const main = mainConnection(settings)
  const model = settings.analysis?.model
  const status = !main || !connectionReady(main) ? t('请先粘贴服务商的 API 密钥')
    : t('自动匹配剪辑、画面理解、转写和封面模型。有云端转写时，音频会发送给这家服务商。')
  const sponsorId = firstRunSponsor(choice) as keyof typeof PROVIDERS | null
  const snapNow = readPromoSnapshot()
  const packagedNow = !snapNow || snapNow.source === 'bundled' ? (sponsorId && PROVIDERS[sponsorId] ? PROVIDERS[sponsorId].sponsor?.registerUrl || '' : '') : ''
  const liveLink = sponsorId ? promotionRegisterUrl(sponsorId, packagedNow) : null
  const sponsorName = choice === 'other' ? otherName : (sponsorId && PROVIDERS[sponsorId] ? PROVIDERS[sponsorId].short : '')
  const label = choice !== 'other' && sponsorId && !liveLink
    ? { key: '下一步' }
    : firstRunPrimaryLabel(choice, sponsorName)
  const connecting = step === 'connect' && !!main

  return <Dialog open={open} onClose={later} title={t('选择 AI 服务商')}
    description={connecting ? (choice === 'other' || !liveLink ? t('把 API 密钥粘贴到下方即可。') : t('在浏览器完成注册后，把 API 密钥粘贴到下方。')) : undefined}
    footer={<div className="ac-setup-foot">
      {connecting
        ? <Btn variant="text" size="sm" disabled={m.saving} onClick={() => setStep('choose')}>{t('返回')}</Btn>
        : <Btn variant="text" size="sm" onClick={later}>{t('稍后设置')}</Btn>}
      {connecting
        ? <Btn variant="cta" size="sm" loading={m.saving} disabled={!main || !connectionReady(main)} onClick={() => void saveConnection()}>{t('一键配置模型')}</Btn>
        : <Btn variant="cta" size="sm" onClick={primary}>{t(label.key, label.values)}</Btn>}
    </div>}>
    <ConfigProvider theme={{ token: { zIndexPopupBase: 1300 } }}>
      <div className="ac-setup-dialog ac-ai-settings">
        {connecting && main ? <>
          <fieldset className="ac-model-fields" disabled={m.saving}>
            <ProviderFields connection={main} hideProvider placement="home_setup"
              keyHint={m.keyHints[main.id]}
              onChoose={p => m.chooseProvider('analysis', p)} onEdit={patch => m.editConnection(main, patch)} />
          </fieldset>
          <div className="ac-setup-status"><StatusDot tone="muted" label={status} /></div>
          {connectionReady(main) && <details className="studio-details"><summary>{t('手动选择模型')}</summary><ModelPicker role="analysis" connection={main} model={model || ''}
            mode={settings.analysis_mode} list={m.lists[main.id]} busy={!!m.busy[main.id]} listError={m.listErrors[main.id]}
            onRefresh={() => void m.discover(main, true)}
            onChange={value => m.update({ analysis: { connection_id: main.id, model: value, capability: 'auto', model_source: 'user' } })} />
            <Btn size="sm" disabled={m.saving || !model?.trim()} onClick={() => void saveConnection(true)}>{t('连接并保存')}</Btn>
          </details>}
          {m.error && <p className="studio-error" role="alert">{m.error}</p>}
        </> : <>
          <div className="ac-choice-list" role="radiogroup" aria-label={t('选择 AI 服务商')}>
            {choices.map(id => {
              const title = optionTitle(id)
              if (!title) return null
              const preset = id === 'other' ? undefined : PROVIDERS[id as keyof typeof PROVIDERS]
              const promoted = id !== 'other' && promotionAllowsUpsell(id)
              return <button key={id} type="button" role="radio" className="ac-choice" aria-checked={choice === id}
                onClick={() => { touched.current = true; choiceRef.current = id; setChoice(id) }}>
                <span className="ac-choice-text">
                  <b>{title()}{promotionRecommends(id) && <span className="ac-badge">{t('推荐')}</span>}{promoted && !promotionRecommends(id) && preset?.sponsor && <span className="ac-badge">{`${t('赞助')} · ${preset.sponsor.offer}`}</span>}</b>
                  <span>{choiceDetail(id, otherName)}</span>
                </span>
                {choice === id && <Icon.Check />}
              </button>
            })}
          </div>
          {notices[choice] && <p className="ac-note">{notices[choice][noticeLanguage] || notices[choice].en || notices[choice].zh}</p>}
          <p className="ac-note">{t('可随时在设置中更换')}</p>
          {choice === 'other' && <p className="ac-note"><button type="button" className="ac-link-button" onClick={goSettings}>{t('去设置选择其他服务商')}</button></p>}
        </>}
      </div>
    </ConfigProvider>
  </Dialog>
}
