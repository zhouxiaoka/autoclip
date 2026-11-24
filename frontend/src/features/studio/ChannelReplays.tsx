import { useEffect, useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import api from '../../services/api'
import { Btn, Icon } from '../../ui'
import { openExternalLink } from '../../utils/externalLinks'
import { getLocale } from '../../i18n'

export interface ChannelReplay { id: string; title: string; direct_video_id?: string; duration?: string | null }
interface Archive extends ChannelReplay { thumbnail_url?: string | null; duration?: string | null; processing: boolean; date: string | null; project_id: string | null }
interface Page { live_streaming_disabled?: boolean; selected: ChannelReplay | null; channel: string; items: Archive[]; next: string | null }
interface Connection { configured: boolean; channel: string | null }
interface Attempt { id: string; url: string; code?: string }

function durationLabel(value?: string | null) {
  const match = value?.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/)
  if (!match || !value) return null
  const [, hours, minutes = '0', seconds = '0'] = match
  return [hours, hours ? minutes.padStart(2, '0') : minutes, seconds.padStart(2, '0')].filter(Boolean).join(':')
}

export default function ChannelReplays({ provider, selected, onSelect, disabled }: {
  provider: 'twitch' | 'youtube'; selected?: ChannelReplay; onSelect: (replay?: ChannelReplay) => void; disabled: boolean
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const base = '/replay-channels/' + provider
  const [connection, setConnection] = useState<Connection>()
  const [page, setPage] = useState<Page>()
  const [attempt, setAttempt] = useState<Attempt>()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const alive = useRef(false)

  const showError = useCallback((e: unknown) => {
    if (!alive.current) return
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    if (detail === 'channel_reconnect') {
      setConnection({ configured: true, channel: null }); setPage(undefined); onSelect(undefined)
    }
    setError(detail === 'channel_keychain' ? 'channels.keychain'
      : detail === 'channel_denied' || detail === 'channel_expired' ? 'channels.incomplete'
      : detail === 'channel_missing' ? 'channels.noChannel' : detail === 'channel_reconnect' ? 'channels.reconnect' : 'channels.error')
  }, [onSelect])

  useEffect(() => {
    alive.current = true
    let active = true
    setLoading(true); setError('')
    async function load() {
      try {
        const state = await api.get<unknown, Connection>(base, { retry: false })
        if (!active) return
        setConnection(state); onSelect(undefined); setPage(undefined)
        if (state.channel) {
          const first = await api.get<unknown, Page>(base + '/archives', { retry: false })
          if (active) { setPage(first); onSelect(first.selected ?? undefined) }
        }
      } catch (e) { if (active) showError(e) }
      finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false; alive.current = false }
  }, [base, revision, onSelect, showError])

  useEffect(() => {
    if (!attempt) return
    const url = base + '/connect/' + encodeURIComponent(attempt.id)
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const result = await api.post<unknown, {pending: boolean}>(url, {}, { retry: false })
        if (!active) return
        if (result.pending) timer = setTimeout(poll, 2500)
        else { setAttempt(undefined); setRevision(r => r + 1) }
      } catch (e) {
        if (active) { setAttempt(undefined); showError(e) }
      }
    }
    timer = setTimeout(poll, 2000)
    return () => {
      active = false; clearTimeout(timer)
      void api.delete(url, { retry: false }).catch(() => {})
    }
  }, [base, attempt, showError])

  async function start() {
    setLoading(true); setError('')
    try {
      const flow = await api.post<unknown, Attempt>(base + '/connect', {}, { retry: false })
      if (!alive.current) {
        await api.delete(base + '/connect/' + flow.id, { retry: false })
        return
      }
      setAttempt(flow)
      await openExternalLink(flow.url)
    } catch (e) { showError(e) }
    finally { if (alive.current) setLoading(false) }
  }
  async function choose(row?: ChannelReplay) {
    setLoading(true); setError('')
    try {
      await api.put(base + '/selection', { archive_id: row?.id ?? null }, { retry: false })
      if (alive.current) onSelect(row)
    } catch (e) { showError(e) }
    finally { if (alive.current) setLoading(false) }
  }
  async function disconnect() {
    setLoading(true); setError('')
    try {
      await api.delete(base, { retry: false })
      if (alive.current) { onSelect(undefined); setPage(undefined); setRevision(r => r + 1) }
    } catch (e) { showError(e) }
    finally { if (alive.current) setLoading(false) }
  }
  async function more() {
    if (!page?.next) return
    setLoading(true); setError('')
    try {
      const next = await api.get<unknown, Page>(base + '/archives', { params: { cursor: page.next }, retry: false })
      if (alive.current) setPage({ ...next, items: [...new Map([...page.items, ...next.items].map(i => [i.id, i])).values()] })
    } catch (e) { showError(e) }
    finally { if (alive.current) setLoading(false) }
  }
  return <section className="replay-channel">
    {connection?.channel
      ? <div className="studio-row"><strong>{connection.channel}</strong>
        <Btn size="sm" disabled={loading} onClick={() => void disconnect()}>{t('channels.disconnect')}</Btn></div>
      : connection?.configured && !attempt && <Btn disabled={loading} onClick={() => void start()}>{t('channels.connect', { platform: provider === 'twitch' ? 'Twitch' : 'YouTube' })}</Btn>}
    {connection && !connection.configured && <p>{t('channels.unconfigured')}</p>}
    {loading && <p role="status">{t('replays.loading')}</p>}
    {attempt && <div><p role="status">{t('channels.authorize')} <b>{attempt.code}</b></p>
      <div className="studio-actions"><Btn size="sm" onClick={() => void openExternalLink(attempt.url)}>{t('channels.browser')}</Btn>
        <Btn size="sm" onClick={() => setAttempt(undefined)}>{t('取消')}</Btn></div></div>}
    {page && <>
      {!page.items.length && <p>{t(page.live_streaming_disabled ? 'channels.liveDisabled' : 'channels.empty')}</p>}
      <div className="replay-channel-list">{page.items.map(row => {
        const chosen = selected?.id === row.id
        const duration = durationLabel(row.duration)
        return <button key={row.id} type="button" className="replay-archive"
          aria-pressed={row.project_id ? undefined : chosen} disabled={!row.project_id && (disabled || loading)}
          onClick={() => row.project_id ? navigate('/project/' + row.project_id) : void choose(row)}>
          <span className="replay-cover" aria-hidden="true">
            <Icon.Play size={20} />
            {row.thumbnail_url && <img key={row.thumbnail_url} src={row.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer"
              onError={event => { event.currentTarget.hidden = true }} />}
            {duration && <span className="replay-duration">{duration}</span>}
          </span>
          <span className="replay-caption">
            <strong title={row.title}>{row.title}</strong>
            <span className="replay-meta">{row.date && <time dateTime={row.date}>{new Date(row.date).toLocaleDateString(getLocale())}</time>}
              {duration && <span className="studio-sr">{duration}</span>}
              {row.processing && <small>{t('channels.processing')}</small>}</span>
          </span>
          <span className="replay-row-action">{t(row.project_id ? 'obs.review' : chosen ? '已选择' : 'channels.select')}</span>
        </button>
      })}</div>
      {selected && <Btn size="sm" disabled={loading} onClick={() => void choose()}>{t('取消')}</Btn>}
      {page.next && <Btn size="sm" disabled={loading} onClick={() => void more()}>{t('channels.more')}</Btn>}
    </>}
    {error && <div role="alert"><p>{t(error)}</p><Btn size="sm" disabled={loading} onClick={() => setRevision(r => r + 1)}>{t('重试')}</Btn></div>}
  </section>
}
