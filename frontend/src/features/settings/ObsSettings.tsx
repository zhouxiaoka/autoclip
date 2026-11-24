import { useEffect, useState } from 'react'
import { Input, InputNumber, Switch } from 'antd'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import api from '../../services/api'
import { Btn, Row, Section } from '../../ui'

interface Status {
  enabled: boolean
  has_password?: boolean
  port: number
  revision: string
  connected: boolean
  connection: string
  supported: boolean
  phase: string
  recording: boolean
  version: string
  directory: string
  automatic: boolean
  changed: boolean
  digest: string
  max_calls: number
  recipients: { role: string; host: string; model: string }[]
  latest?: { status: string; project_id?: string }
}

export default function ObsSettings() {
  const { t } = useTranslation()
  const [state, setState] = useState<Status>()
  const [port, setPort] = useState<number | null>(null)
  const [limit, setLimit] = useState<number | null>(null)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const next = await api.get<unknown, Status>('/obs', { retry: false })
        if (active) setState(next)
      } catch { if (active) setState(undefined) }
      finally { if (active) timer = setTimeout(poll, 2000) }
    }
    void poll()
    return () => { active = false; clearTimeout(timer) }
  }, [])

  async function save(path: string, body: Record<string, unknown>) {
    setBusy(true)
    setError(false)
    try {
      await api.put('/obs/' + path, body)
      if (path === 'connection') setPassword('')
      setState(await api.get<unknown, Status>('/obs'))
    } catch { setError(true) }
    finally { setBusy(false) }
  }
  const phase = state?.connected ? state.phase : state?.connection
  const activePhase = phase === 'checking' ? 'connected' : phase === 'idle' ? 'connected' : phase
  const recent = state?.latest
  const messages: Record<string, string> = {
    manual_waiting: 'checking', manual_ready: 'checking', waiting: 'checking', ready: 'checking', dispatching: 'dispatching', submitted: 'submitted',
    file_error: 'file_error', setup_required: 'setup', deleted: 'deleted', paused: 'changed', duplicate: 'duplicate', uncertain: 'uncertain', limit: 'limitReached',
  }
  return <Section title="OBS Studio" description={t('obs.help')}>
    <div className="ac-rows">
      <Row label={t('obs.port')}><InputNumber aria-label={t('obs.port')} min={1} max={65535} disabled={state?.enabled}
        value={port ?? state?.port ?? 4455} onChange={setPort} /></Row>
      <Row label={t('obs.password')} hint={state?.has_password ? t('obs.passwordSaved') : undefined}>
        <div className="studio-actions">
          <Input.Password autoComplete="off" maxLength={1024} aria-label={t('obs.password')}
            placeholder={state?.has_password ? t('obs.passwordSaved') : undefined}
            disabled={state?.enabled} value={password} onChange={event => setPassword(event.target.value)} />
          {!state?.enabled && state?.has_password && <Btn size="sm" disabled={busy}
            onClick={() => void save('connection', { enabled: false, port: port ?? state?.port, password: '' })}>{t('obs.clearPassword')}</Btn>}
        </div>
      </Row>
      <Row label={t('obs.connect')} hint={activePhase ? t('obs.' + activePhase) : t('obs.unavailable')}>
        <Switch aria-label={t('obs.connect')} checked={!!state?.enabled} disabled={!state || busy}
          onChange={enabled => void save('connection', { enabled, port: port ?? state?.port, password: password || null })} />
      </Row>
      {state?.connected && <Row label={'OBS ' + state.version} hint={state.directory}>{state.recording && t('obs.recording')}</Row>}
      <Row label={t('obs.limit')} hint={t('obs.fees')}><InputNumber aria-label={t('obs.limit')} min={1} max={500}
        disabled={state?.automatic} value={limit ?? state?.max_calls ?? 50} onChange={setLimit} /></Row>
      {state?.recipients.map(({ role, host, model }) =>
        <Row key={role} label={t('obs.' + role)} hint={host}>{model}</Row>)}
      <Row label={t('obs.auto')} hint={state?.changed ? t('obs.changed') : state?.connected && !state.supported
        ? t('obs.version') : !state?.digest ? t('obs.models') : t('obs.consent')}>
        <Switch aria-label={t('obs.auto')} checked={!!state?.automatic}
          disabled={!state || busy || (!state.automatic && (!state.connected || !state.supported || !state.directory || !state.digest))}
          onChange={enabled => void save('automation', { enabled, revision: state?.revision, digest: state?.digest, max_calls: limit ?? state?.max_calls })} />
      </Row>
      {recent && <Row label={t('obs.last')} hint={t(recent.status === 'available' ? 'replays.available' : 'obs.' + (messages[recent.status] ?? 'unconfirmed'))}>
        {recent.project_id && <Link to={'/project/' + recent.project_id}>{t('obs.review')}</Link>}
      </Row>}
      {error && <p role="alert">{t('obs.error')}</p>}
    </div>
  </Section>
}
