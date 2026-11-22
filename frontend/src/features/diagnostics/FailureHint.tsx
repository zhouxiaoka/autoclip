import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { useTranslation } from 'react-i18next'
import { diagnosticsApi } from '../../services/api'
import {
  FAILURE_HINT_MAX_MS,
  FAILURE_HINT_MS,
  HINT_COPY,
  claimFailureHint,
  createHintTimer,
  hintKind,
  taskOrigin,
  type HintKind,
} from './failureHintPolicy'

type ProjectLike = Parameters<typeof taskOrigin>[0]

/** Transient first-failure note. Showing or dismissing it does not change consent. */
export default function FailureHint({ active, project }: { active: boolean; project: ProjectLike }) {
  useTranslation()
  const navigate = useNavigate()
  const [kind, setKind] = useState<HintKind | null>(null)
  const timer = useRef<ReturnType<typeof createHintTimer> | null>(null)
  const root = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!active) return
    let live = true
    const read = diagnosticsApi.consent
    if (typeof read !== 'function') return
    read()
      .then((grant) => {
        if (!live || !claimFailureHint()) return
        setKind(hintKind(taskOrigin(project), grant))
      })
      .catch(() => {
        /* Can't tell whether sending is on. Stay quiet instead of claiming a send. */
      })
    return () => { live = false }
  }, [active, project])

  useEffect(() => {
    if (!kind) return
    const clock = createHintTimer(FAILURE_HINT_MS, () => setKind(null))
    timer.current = clock
    clock.start()
    const cap = window.setTimeout(() => setKind(null), FAILURE_HINT_MAX_MS)
    return () => {
      clock.stop()
      window.clearTimeout(cap)
    }
  }, [kind])

  const pausedInside = (next: EventTarget | null) => next instanceof Node && root.current?.contains(next)

  if (!kind || typeof document === 'undefined') return null

  return (
    <div
      ref={root}
      className="ac-failure-hint"
      role="status"
      aria-live="polite"
      onMouseEnter={() => timer.current?.pause()}
      onMouseLeave={event => { if (!pausedInside(event.relatedTarget)) timer.current?.resume() }}
      onFocus={() => timer.current?.pause()}
      onBlur={event => { if (!pausedInside(event.relatedTarget)) timer.current?.resume() }}
    >
      <span>{t(HINT_COPY[kind])}</span>
      <button
        type="button"
        className="ac-failure-hint-link"
        onClick={() => navigate('/settings?section=diagnostics')}
      >{t('设置')}</button>
    </div>
  )
}
