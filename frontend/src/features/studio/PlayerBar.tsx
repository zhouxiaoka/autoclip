import { t } from '../../i18n'
import { fmtDuration } from '../../ui'

const Icon = ({ d }: { d: string }) => <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d={d} fill="currentColor" /></svg>
const PLAY = 'M4 2.5v11l9-5.5z'
const PAUSE = 'M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z'
const SOUND = 'M2 6h3l4-3.5v11L5 10H2zM11 5.2a3.6 3.6 0 0 1 0 5.6v-1.4a2.2 2.2 0 0 0 0-2.8z'
const MUTED = 'M2 6h3l4-3.5v11L5 10H2zM10.6 6.1l1 1 1.4-1.4 1 1L12.6 8l1.4 1.4-1 1-1.4-1.4-1.4 1.4-1-1L10.6 8 9.2 6.6l1-1z'

/**
 * Transport for the editor preview, scoped to what the clip actually uses: the scrubber runs from
 * 0 to the scene length (not the whole source), so the timeline is the clip's timeline.
 */
export default function PlayerBar({ offset, length, playing, muted, onToggle, onSeek, onMute }: {
  /** Seconds into the scene (already clamped by the caller). */
  offset: number
  length: number
  playing: boolean
  muted: boolean
  onToggle: () => void
  onSeek: (offset: number) => void
  onMute: () => void
}) {
  return <div className="studio-player-bar" role="group" aria-label={t("播放控制")}>
    <button type="button" className="studio-player-btn" aria-label={playing ? t("暂停") : t("播放")} onClick={onToggle}><Icon d={playing ? PAUSE : PLAY} /></button>
    <span className="ac-mono studio-player-time">{fmtDuration(offset)} / {fmtDuration(length)}</span>
    <input type="range" aria-label={t("成片进度")} min={0} max={Math.max(length, .1)} step={.05} value={Math.min(offset, length)} onChange={e => onSeek(Number(e.target.value))} />
    <button type="button" className="studio-player-btn" aria-label={muted ? t("取消静音") : t("静音")} aria-pressed={muted} onClick={onMute}><Icon d={muted ? MUTED : SOUND} /></button>
  </div>
}
