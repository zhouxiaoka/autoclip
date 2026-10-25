import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Select, Input } from 'antd'
import { t } from '../../i18n'
import { Btn, Dialog } from '../../ui'
import { modelSettingsApi } from './modelSettingsApi'
import { getCatalog } from './providerPresets'
import { isLiveConnectable } from './providerCatalogView'
import {
  CUSTOM_PROVIDER_ID, hostOf, keyTail, needsOverwrite, normalizeGuideBaseUrl,
  type GuideEndpoint, type GuideTarget,
} from './keyGuide'
import { clearOffer, commitKeyGuide, currentOffer, onClipboardScanRequest, subscribeOffers, type KeyOffer } from './keyGuideBus'
import { dismissCurrentOffer, scanClipboard, setKeyGuideTargets } from './keyGuideWatch'

function guideTargets(): GuideTarget[] {
  return Object.values(getCatalog().providers)
    .filter(preset => isLiveConnectable(preset) && preset.auth === 'api_key' && preset.protocol !== 'local')
    .map(preset => ({
      id: preset.id,
      hosts: [...preset.accepted_hosts, hostOf(preset.base_url)].filter(Boolean),
    }))
}

function choiceLabel(id: string): string {
  if (id === CUSTOM_PROVIDER_ID) return t('settings.key_guide.custom')
  const preset = getCatalog().providers[id]
  return t(preset?.ui_name || preset?.display_name || id)
}

export default function KeyGuidePrompt() {
  const navigate = useNavigate()
  const [offer, setOffer] = useState<KeyOffer | null>(currentOffer())
  const [dialogOpen, setDialogOpen] = useState(false)
  const [providerId, setProviderId] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [endpoints, setEndpoints] = useState<GuideEndpoint[]>([])
  const [busy, setBusy] = useState(false)
  const [emptyNote, setEmptyNote] = useState(false)
  const targets = useMemo(guideTargets, [])
  setKeyGuideTargets(targets)
  useEffect(() => onClipboardScanRequest(() => {
    void scanClipboard('button').then(result => { if (result === 'empty') setEmptyNote(true) })
  }), [])
  useEffect(() => subscribeOffers(next => {
    setOffer(next)
    setEmptyNote(false)
    if (next && (next.source === 'deeplink' || next.source === 'paste')) setDialogOpen(true)
  }), [])

  useEffect(() => {
    if (!offer) return
    setProviderId(offer.hintedProviderId || '')
    setBaseUrl(offer.baseUrl || '')
  }, [offer])

  useEffect(() => {
    if (!dialogOpen) return
    let alive = true
    void modelSettingsApi.get().then(value => {
      if (!alive) return
      setEndpoints((value.connections || []).map(connection => ({
        id: connection.id,
        providerId: connection.provider,
        baseUrl: connection.base_url || '',
        apiKey: connection.api_key,
        hasKey: !!connection.has_key,
      })))
    }).catch(() => { if (alive) setEndpoints([]) })
    return () => { alive = false }
  }, [dialogOpen])

  if (!offer && !emptyNote) return null

  const choices = [
    ...targets.map(target => ({ value: target.id, label: choiceLabel(target.id) })),
    { value: CUSTOM_PROVIDER_ID, label: choiceLabel(CUSTOM_PROVIDER_ID) },
  ]
  const selected = providerId || undefined
  const custom = providerId === CUSTOM_PROVIDER_ID
  const preset = !custom && providerId ? getCatalog().providers[providerId] : undefined
  const endpoint = endpoints.find(item => (
    custom
      ? item.providerId === 'compatible' && hostOf(item.baseUrl) === hostOf(baseUrl)
      : item.providerId === providerId
  ))
  const replace = !!offer && needsOverwrite(endpoint, offer.key)
  const urlReady = !custom || !!normalizeGuideBaseUrl(baseUrl)
  const canConfirm = !!offer && !!providerId && urlReady && !busy

  const close = () => {
    setDialogOpen(false)
    if (offer) void dismissCurrentOffer(offer.key)
    clearOffer()
    setEmptyNote(false)
  }

  const confirm = async () => {
    if (!offer || !canConfirm) return
    setBusy(true)
    try {
      const result = await commitKeyGuide({
        providerId,
        apiKey: offer.key,
        baseUrl: custom ? baseUrl : (preset?.base_url || baseUrl),
        overwrite: true,
      })
      if (result.blocked || (!result.ok && !result.deferred)) return
      void dismissCurrentOffer(offer.key)
      clearOffer()
      setDialogOpen(false)
      const presetQuery = custom ? '' : providerId
      navigate(presetQuery ? `/settings?section=ai&provider=${encodeURIComponent(presetQuery)}` : '/settings?section=ai')
    } finally {
      setBusy(false)
    }
  }

  const banner = offer && offer.source === 'clipboard' && !dialogOpen
  return <>
    {banner && (
      <div className="ac-key-guide" role="status">
        <p>{t('settings.key_guide.clipboard')}</p>
        <Btn size="sm" onClick={() => setDialogOpen(true)}>{t('settings.key_guide.fill')}</Btn>
        <Btn variant="text" size="sm" onClick={close}>{t('settings.key_guide.ignore')}</Btn>
      </div>
    )}
    {emptyNote && !offer && (
      <div className="ac-key-guide" role="status">
        <p>{t('settings.key_guide.none')}</p>
        <Btn variant="text" size="sm" onClick={() => setEmptyNote(false)}>{t('settings.key_guide.ignore')}</Btn>
      </div>
    )}
    <Dialog
      open={!!offer && dialogOpen}
      onClose={close}
      title={t('settings.key_guide.title')}
      description={offer?.source === 'deeplink' ? t('settings.key_guide.deeplink') : offer?.source === 'paste' ? t('settings.key_guide.paste', { name: choiceLabel(offer.hintedProviderId || '') }) : t('settings.key_guide.clipboard')}
      footer={<>
        <Btn variant="text" size="sm" onClick={close}>{t('settings.key_guide.ignore')}</Btn>
        <Btn variant="cta" size="sm" disabled={!canConfirm} loading={busy} onClick={() => void confirm()}>
          {replace ? t('settings.key_guide.replace') : t('settings.key_guide.fill')}
        </Btn>
      </>}
    >
      {offer && <div className="ac-rows">
        <p className="ac-note">{t('settings.key_guide.masked', { tail: keyTail(offer.key) })}</p>
        {offer.conflict && <p className="ac-note" role="status">{t('settings.key_guide.conflict')}</p>}
        <label className="ac-row">
          <span className="ac-row-label"><b>{t('settings.key_guide.pick')}</b></span>
          <Select
            aria-label={t('settings.key_guide.pick')}
            value={selected}
            placeholder={t('settings.key_guide.pick_required')}
            style={{ width: '100%' }}
            options={choices}
            onChange={value => setProviderId(value)}
          />
        </label>
        {(custom || !preset?.base_url) && (
          <label className="ac-row">
            <span className="ac-row-label"><b>{t('settings.key_guide.endpoint')}</b></span>
            <Input
              aria-label={t('settings.key_guide.endpoint')}
              value={baseUrl}
              placeholder="https://example.com/v1"
              onChange={event => setBaseUrl(event.target.value)}
            />
          </label>
        )}
        {replace && <p className="ac-note" role="status">{t('settings.key_guide.keep')}</p>}
        {!providerId && <p className="ac-note">{t('settings.key_guide.pick_required')}</p>}
      </div>}
    </Dialog>
  </>
}
