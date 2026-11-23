import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import api from '../../services/api'
import { Btn, Dialog, Segmented } from '../../ui'
import { getLocale } from '../../i18n'
import { isDesktopMode } from '../../utils/desktopMode'
import { openExternalLink } from '../../utils/externalLinks'
import ChannelReplays, { type ChannelReplay } from './ChannelReplays'
import ObsSettings from '../settings/ObsSettings'

import obsMark from '../../assets/replay-sources/obsstudio.svg'
import twitchMark from '../../assets/replay-sources/twitch.svg'
import youtubeMark from '../../assets/replay-sources/youtube.svg'
import kickMark from '../../assets/replay-sources/kick.svg'
import discordMark from '../../assets/replay-sources/discord.svg'
import folderMark from '../../assets/replay-sources/folder.svg'
import './liveReplayPicker.css'

const fileSources = {
  discord: { hint: 'replays.discordFile' },
  other: { hint: 'replays.otherFile' },
  kick: { hint: 'replays.kickFile', dashboard: 'Kick Studio', url: 'https://dashboard.kick.com/studio/vods' },
  twitch: { hint: 'replays.twitchFile', dashboard: 'Twitch', url: 'https://dashboard.twitch.tv/' },
  youtube: { hint: 'replays.youtubeFile', dashboard: 'YouTube Studio', url: 'https://studio.youtube.com/' },
} as const

export type ReplayFileSource = keyof typeof fileSources
export type RemoteReplay =
  | ({ kind: 'twitch' } & ChannelReplay)
  | { kind: 'obs'; id: string; title: string; seconds: number }

// The brand paths are bundled from Simple Icons 14.15.0 (CC0).
const replayOptions = [
  { value: 'obs', name: 'OBS Studio', mark: obsMark },
  { value: 'twitch', name: 'Twitch', mark: twitchMark },
  { value: 'youtube', name: 'YouTube', mark: youtubeMark },
  { value: 'kick', name: 'Kick', mark: kickMark },
  { value: 'discord', name: 'Discord', mark: discordMark },
  { value: 'other', name: 'replays.other', mark: folderMark },
] as const

interface Replay {
  id: string
  saved_at: number
  seconds: number
  status: string
  project_id: string | null
  selectable: boolean
}
interface History { connection: string; phase: string; items: Replay[] }

const statuses: Record<string, string> = {
  available: 'replays.available', waiting: 'obs.checking', ready: 'obs.checking',
  manual_ready: 'obs.checking', manual_waiting: 'obs.checking', manual_importing: 'obs.checking', dispatching: 'obs.dispatching',
  submitted: 'obs.submitted', paused: 'obs.changed', uncertain: 'obs.uncertain',
  duplicate: 'obs.duplicate', file_error: 'obs.file_error', setup_required: 'obs.setup',
  limit: 'obs.limitReached', deleted: 'obs.deleted',
}

export default function LiveReplayPicker({ disabled, onOpen, onFile, onRemote }: {
  onRemote: (replay: RemoteReplay) => void
  disabled: boolean; onOpen: () => void; onFile: (file: File, source: ReplayFileSource, replay?: ChannelReplay) => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [source, setSource] = useState<'obs' | ReplayFileSource>('obs')
  const [channels, setChannels] = useState({ twitch: false, youtube: false })
  const fileSource = source === 'obs' ? undefined : fileSources[source]
  const dashboard = fileSource && 'url' in fileSource ? fileSource : undefined
  const [selected, setSelected] = useState<ChannelReplay>()
  const [configure, setConfigure] = useState(false)
  const [desktop, setDesktop] = useState(false)
  const [history, setHistory] = useState<History>()
  const [loadError, setLoadError] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  useEffect(() => { void isDesktopMode().then(setDesktop) }, [])
  useEffect(() => {
    if (!open || !desktop) return
    let active = true
    api.get<unknown, typeof channels>('/replay-channels/availability', { retry: false }).then(result => {
      if (active) setChannels({ twitch: result.twitch === true, youtube: result.youtube === true })
    }).catch(() => {})
    return () => { active = false }
  }, [open, desktop])
  useEffect(() => {
    if (!open || source !== 'obs' || !desktop) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function refresh() {
      try {
        const result = await api.get<unknown, History>('/obs/replays', { retry: false })
        if (active) { setHistory(result); setLoadError(false) }
      } catch { if (active) setLoadError(true) }
      if (active) timer = setTimeout(refresh, 2000)
    }
    void refresh()
    return () => { active = false; clearTimeout(timer) }
  }, [open, desktop, source])
  return <>
    <Btn size="sm" disabled={disabled} onClick={() => { onOpen(); setSelected(undefined); setOpen(true) }}>{t('replays.choose')}</Btn>
    <Dialog open={open} title={t('replays.title')} onClose={() => setOpen(false)}>
      <Segmented className="replay-sources" value={source} onChange={next => { if (next !== source) { setSelected(undefined); setSource(next) } }} ariaLabel={t('replays.title')} options={
        replayOptions.map(({ value, name, mark }) => ({
          value,
          label: <>
            <span className={`replay-mark replay-mark--${value}`}><img src={mark} alt="" /></span>
            <span className="replay-source-label">{value === 'other' ? t(name) : name}</span>
          </>,
        }))
      } />
      {source === 'obs' ? <>
        {!desktop ? <p>{t('replays.desktop')}</p> : <>
          <div className="studio-row"><p role="status">{loadError ? t('obs.unavailable') : history
            ? t('obs.' + (history.connection === 'connected' && ['waiting_recording', 'live', 'unconfirmed'].includes(history.phase)
              ? history.phase : history.connection)) : t('replays.loading')}</p>
            <Btn size="sm" aria-expanded={configure} onClick={() => setConfigure(!configure)}>{t('replays.connection')}</Btn></div>
          {configure && <ObsSettings />}
          {history && !history.items.length && !loadError && <p className="studio-muted">{t('replays.empty')}</p>}
          {history?.items.map(item => {
            const title = 'OBS · ' + new Date(item.saved_at * 1000).toLocaleString(getLocale())
            return <div className="studio-source-row" key={item.id}>
              <div><b>{title}</b>
                <p className="studio-muted">{Math.floor(item.seconds / 60)}:{String(Math.floor(item.seconds % 60)).padStart(2, '0')} · {t(statuses[item.status] || 'obs.unconfirmed')}</p></div>
              {item.project_id && !['ready', 'manual_ready'].includes(item.status) ? <Btn size="sm" onClick={() => navigate('/project/' + item.project_id)}>{t('obs.review')}</Btn>
                : item.selectable && <Btn size="sm" variant="cta" disabled={disabled || loadError} onClick={() => { onRemote({ kind: 'obs', id: item.id, title, seconds: item.seconds }); setOpen(false) }}>{t('channels.select')}</Btn>}
            </div>
          })}
        </>}
      </> : <div className="studio-field">
        {desktop && (source === 'twitch' || source === 'youtube') && channels[source] && <ChannelReplays key={source} provider={source} disabled={disabled}
          selected={selected} onSelect={setSelected} />}
        <p>{selected?.direct_video_id ? t('channels.directHint') : selected ? t('channels.attach', { title: selected.title }) : t(fileSources[source].hint)}</p>
        <div className="studio-actions">{source === 'twitch' && selected?.direct_video_id && <Btn variant="cta" disabled={disabled}
          onClick={() => { onRemote({ kind: 'twitch', ...selected }); setOpen(false) }}>{t('channels.directUse')}</Btn>}{dashboard && <Btn onClick={() => void openExternalLink(dashboard.url)}>{dashboard.dashboard} ↗</Btn>}
          <Btn variant={selected?.direct_video_id ? undefined : "cta"} disabled={disabled} onClick={() => fileInput.current?.click()}>{t('replays.pickFile')}</Btn></div>
        <input ref={fileInput} type="file" hidden accept=".mp4,.mkv,.mov,.webm,.avi" onChange={event => {
          const file = event.target.files?.[0]
          if (file) { onFile(file, source, selected); setOpen(false) }
          event.target.value = ''
        }} /></div>}
      <p className="replay-upcoming">{t('replays.moreTools')}</p>
    </Dialog>
  </>
}
