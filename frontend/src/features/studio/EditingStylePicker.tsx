import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { t } from '../../i18n'
import { telemetryId } from '../../analytics/workflow'
import { trackTemplateOverride, trackTemplatePickerShown, trackTemplatePreviewFailed, trackTemplatePreviewPlayed, trackTemplateRestore } from '../../analytics/studio'
import { captureStudioException } from '../../desktop/sentry'
import { requestStyleRecommendation } from './editingStyleClient'
import { STYLE_POSTERS, loadStylePreview } from './editingStyleMedia'
import { beginStyleRecommendation, readStyle, subscribeStyle, type StyleSnapshot } from './editingStyleSession'
import StyleProbeLine from './StyleProbeLine'
import {
  HTML_TEMPLATE_CHOICES, PREVIEW_SECONDS, chosenTemplate, degradeFromEnvironment, intelMacFromHints, selectionAfterRecommendation, supportsBackdrop,
  type EditingStyle, type HtmlTemplateChoice,
} from './editingStyle'

type InputKind = 'mouse' | 'keyboard'
type Trigger = 'hover' | 'focus' | 'keyboard' | 'button' | 'select'

const COPY: Record<EditingStyle, { name: string; desc: string }> = {
  editorial: { name: 'editing_style.editorial.name', desc: 'editing_style.editorial.desc' },
  street: { name: 'editing_style.street.name', desc: 'editing_style.street.desc' },
  classic: { name: 'editing_style.classic.name', desc: 'editing_style.classic.desc' },
}

function previewUrl(node: HTMLVideoElement, urls: { webm: string; mp4: string }): string {
  return node.canPlayType('video/webm; codecs="vp9"') !== '' ? urls.webm : urls.mp4
}

function assignPreview(node: HTMLVideoElement, src: string) {
  if (node.getAttribute('data-src') === src) return
  node.preload = 'auto'
  node.muted = true
  node.setAttribute('data-src', src)
  node.src = src
}

function useMedia(query: string): boolean {
  const [matches, setMatches] = useState(false)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const media = window.matchMedia(query)
    const apply = () => setMatches(media.matches)
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [query])
  return matches
}

export default function EditingStylePicker({
  value, disabled, onChange, sourceKey, url, file,
}: {
  value: string | undefined
  disabled?: boolean
  onChange: (next: HtmlTemplateChoice) => void
  sourceKey: string | null
  url?: string
  file?: File | null
}) {
  const [snap, setSnap] = useState<StyleSnapshot>(() => readStyle())
  const [manual, setManual] = useState<EditingStyle | null>(null)
  const manualRef = useRef<EditingStyle | null>(null)
  const [hover, setHover] = useState<EditingStyle | null>(null)
  const [focus, setFocus] = useState<EditingStyle | null>(null)
  const [pinned, setPinned] = useState<EditingStyle | null>(null)
  const [hidden, setHidden] = useState(false)
  const [viewTick, setViewTick] = useState(0)
  const [intelMac, setIntelMac] = useState(false)
  const [degraded, setDegraded] = useState(() => degradeFromEnvironment(
    typeof navigator === 'undefined' ? undefined : navigator.hardwareConcurrency,
    supportsBackdrop(),
    false,
  ))
  const reducedMotion = useMedia('(prefers-reduced-motion: reduce)')
  const reducedTransparency = useMedia('(prefers-reduced-transparency: reduce)')
  const videos = useRef<Partial<Record<EditingStyle, HTMLVideoElement | null>>>({})
  const visible = useRef<Partial<Record<EditingStyle, boolean>>>({})
  const bars = useRef<Partial<Record<EditingStyle, HTMLElement | null>>>({})
  const cards = useRef<Partial<Record<EditingStyle, HTMLDivElement | null>>>({})
  const started = useRef(new Set<string>())
  const reportedPlay = useRef(new Set<string>())
  const reportedFail = useRef(new Set<string>())
  const shownFor = useRef<string | null>(null)
  const measuredSlide = useRef(false)
  const lastIndex = useRef<number | null>(null)
  const onChangeRef = useRef(onChange)
  const lastInput = useRef<InputKind | null>(null)
  onChangeRef.current = onChange
  const current = chosenTemplate(value)
  const recommendation = snap.key === sourceKey ? snap.result : null
  const resolved = selectionAfterRecommendation(manual, recommendation?.template ?? null, current)
  const selected = resolved.selected
  const index = HTML_TEMPLATE_CHOICES.indexOf(selected)

  useEffect(() => subscribeStyle(() => setSnap(readStyle())), [])

  useEffect(() => {
    manualRef.current = null
    setManual(null)
    setPinned(null)
  }, [sourceKey])

  useEffect(() => {
    if (!sourceKey) return
    const delay = sourceKey.startsWith('url:') ? 400 : 0
    const handle = window.setTimeout(() => {
      beginStyleRecommendation(sourceKey, signal => requestStyleRecommendation({ url, file }, signal))
    }, delay)
    return () => window.clearTimeout(handle)
  }, [sourceKey, url, file])

  useEffect(() => {
    if (!sourceKey || snap.key !== sourceKey || !snap.result || manualRef.current) return
    const next = selectionAfterRecommendation(null, snap.result.template, chosenTemplate(value))
    if (next.apply) onChangeRef.current(next.selected)
  }, [sourceKey, snap, value])

  useEffect(() => {
    if (!sourceKey || snap.key !== sourceKey || !snap.result || shownFor.current === sourceKey) return
    shownFor.current = sourceKey
    trackTemplatePickerShown({
      recommended: snap.result.template,
      reason_code: snap.result.reason_code,
      flag_variant: 'visual',
      source_kind: sourceKey.startsWith('file:') ? 'file' : 'link',
      latency_ms: snap.latencyMs,
    })
  }, [sourceKey, snap])

  useEffect(() => {
    const nav = navigator as Navigator & { userAgentData?: { getHighEntropyValues?: (hints: string[]) => Promise<{ architecture?: string; platform?: string }> } }
    const read = nav.userAgentData?.getHighEntropyValues
    if (!read) return
    let live = true
    read.call(nav.userAgentData, ['architecture', 'platform']).then(data => {
      if (live && intelMacFromHints(data?.platform || '', data?.architecture || '')) setIntelMac(true)
    }).catch(() => { /* a missing hint just hides the Intel note */ })
    return () => { live = false }
  }, [])

  useEffect(() => {
    const mark = () => setHidden(document.hidden || !document.hasFocus())
    document.addEventListener('visibilitychange', mark)
    window.addEventListener('blur', mark)
    window.addEventListener('focus', mark)
    return () => {
      document.removeEventListener('visibilitychange', mark)
      window.removeEventListener('blur', mark)
      window.removeEventListener('focus', mark)
    }
  }, [])

  useEffect(() => {
    if (lastIndex.current === null) { lastIndex.current = index; return }
    if (lastIndex.current === index || measuredSlide.current || reducedMotion || degraded) return
    lastIndex.current = index
    measuredSlide.current = true
    let last = performance.now()
    let slow = 0
    const startedAt = last
    let raf = 0
    const tick = (now: number) => {
      if (now - last > 50) slow += 1
      last = now
      if (now - startedAt < 180) raf = requestAnimationFrame(tick)
      else if (slow >= 2) setDegraded(true)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [index, reducedMotion, degraded])

  const onScreen = (id: EditingStyle | null): id is EditingStyle => id !== null && visible.current[id] !== false
  const playing: EditingStyle[] = []
  if (!disabled && !hidden && sourceKey) {
    if (reducedMotion) {
      if (onScreen(pinned)) playing.push(pinned)
    } else {
      if (onScreen(hover) && hover !== selected) playing.push(hover)
      if (onScreen(focus) && focus !== selected && focus !== hover) playing.push(focus)
      if (onScreen(selected)) playing.push(selected)
    }
  }
  const screenKey = HTML_TEMPLATE_CHOICES.map(id => visible.current[id] === false ? '0' : '1').join('')
  const playKey = `${playing.slice(0, 2).join(',')}|${screenKey}|${viewTick}`

  useEffect(() => {
    if (!sourceKey || typeof IntersectionObserver !== 'function') return
    const observer = new IntersectionObserver(entries => {
      let changed = false
      for (const entry of entries) {
        const id = entry.target.getAttribute('data-style') as EditingStyle | null
        if (!id) continue
        const next = entry.isIntersecting
        if (visible.current[id] !== next) {
          visible.current[id] = next
          changed = true
        }
      }
      if (changed) setViewTick(value => value + 1)
    }, { threshold: 0.01 })
    for (const id of HTML_TEMPLATE_CHOICES) {
      const node = cards.current[id]
      if (node) observer.observe(node)
    }
    return () => observer.disconnect()
  }, [sourceKey])

  useEffect(() => {
    if (!sourceKey || reducedMotion) return
    const recommended = recommendation?.template ?? selected
    const order = [recommended, ...HTML_TEMPLATE_CHOICES.filter(id => id !== recommended && visible.current[id] !== false)]
    let cancel = false
    let cursor = 0
    const ric = window.requestIdleCallback || ((cb: IdleRequestCallback) => window.setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 } as IdleDeadline), 80))
    const prime = async (id: EditingStyle) => {
      const urls = await loadStylePreview(id)
      if (cancel) return
      const node = videos.current[id]
      if (!node) return
      assignPreview(node, previewUrl(node, urls))
      if (node.dataset.primed === '1' || node.dataset.show === '1') return
      try {
        node.muted = true
        await node.play()
        if (cancel || node.dataset.show === '1') return
        node.pause()
        node.dataset.primed = '1'
      } catch {
        /* autoplay can be blocked; the file is still buffered for the hover */
      }
    }
    const step = () => {
      if (cancel || cursor >= order.length) return
      const id = order[cursor]
      cursor += 1
      prime(id).finally(() => { if (!cancel) ric(step) })
    }
    const handle = ric(step)
    return () => {
      cancel = true
      if (typeof handle !== 'number') return
      if (window.cancelIdleCallback) window.cancelIdleCallback(handle)
      else window.clearTimeout(handle)
    }
  }, [sourceKey, reducedMotion, selected, recommendation?.template, viewTick])

  useEffect(() => {
    const want = new Set(playKey.split('|')[0].split(',').filter(Boolean) as EditingStyle[])
    let cancel = false
    for (const id of HTML_TEMPLATE_CHOICES) {
      const node = videos.current[id]
      if (!node) continue
      if (!want.has(id)) {
        node.dataset.show = '0'
        node.pause()
        continue
      }
      const trigger: Trigger = pinned === id && reducedMotion ? 'button' : hover === id ? 'hover' : focus === id && id !== selected ? 'focus' : lastInput.current === 'keyboard' && id === selected ? 'keyboard' : 'select'
      const mark = `${id}:${trigger}`
      node.dataset.show = '1'
      void loadStylePreview(id).then(urls => {
        if (cancel || !want.has(id)) return
        assignPreview(node, previewUrl(node, urls))
        if (!started.current.has(id)) {
          started.current.add(id)
          if (node.dataset.primed !== '1' && node.readyState >= 2 && node.currentTime > 0.04) {
            try { node.currentTime = 0 } catch { /* the poster stays until a frame exists */ }
          }
        }
        const begun = performance.now()
        const played = node.play()
        if (!played) return
        played.then(() => {
          if (reportedPlay.current.has(mark)) return
          reportedPlay.current.add(mark)
          trackTemplatePreviewPlayed({
            template: id,
            trigger,
            first_frame_ms: Math.max(0, Math.round(performance.now() - begun)),
            is_recommended: id === recommendation?.template,
          })
        }).catch(() => {
          if (reportedFail.current.has(id)) return
          reportedFail.current.add(id)
          node.classList.remove('is-playing')
          trackTemplatePreviewFailed({ template: id, error_kind: node.error?.code === 4 ? 'unsupported' : 'decode' })
          captureStudioException(new Error('template preview failed'), 'template_picker')
        })
      }).catch(() => {
        if (reportedFail.current.has(id)) return
        reportedFail.current.add(id)
        trackTemplatePreviewFailed({ template: id, error_kind: 'unknown' })
      })
    }
    return () => { cancel = true }
  }, [playKey, hover, focus, pinned, reducedMotion, selected, recommendation?.template])

  const choose = (next: EditingStyle, input: InputKind) => {
    if (disabled || next === selected) return
    lastInput.current = input
    manualRef.current = next
    setManual(next)
    trackTemplateOverride({
      from_template: selected,
      to_template: next,
      recommended: recommendation?.template,
      stage: 'pre_import',
      input,
      flow_id: telemetryId(),
    })
    onChange(next)
  }

  const restore = () => {
    if (!recommendation || disabled) return
    const next = recommendation.template
    trackTemplateRestore({ from_template: selected, recommended: next })
    manualRef.current = null
    setManual(null)
    if (next !== selected) onChange(next)
  }

  const onCardKey = (id: EditingStyle, event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      choose(id, 'keyboard')
      return
    }
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
    event.preventDefault()
    const delta = event.key === 'ArrowRight' ? 1 : -1
    const next = HTML_TEMPLATE_CHOICES[(HTML_TEMPLATE_CHOICES.indexOf(id) + delta + HTML_TEMPLATE_CHOICES.length) % HTML_TEMPLATE_CHOICES.length]
    choose(next, 'keyboard')
    cards.current[next]?.focus()
  }

  if (!sourceKey) {
    return <fieldset className="studio-template-picker studio-style-picker" disabled={disabled}>
      <legend>{t('editing_style.title')}</legend>
      <p className="studio-muted">{t('editing_style.lead')}</p>
      <p className="studio-style-empty">{t('editing_style.empty')}</p>
    </fieldset>
  }

  const loading = !recommendation
  const overridden = manual !== null && recommendation !== null && manual !== recommendation.template
  const flat = degraded || reducedTransparency
  return <fieldset className={`studio-template-picker studio-style-picker${disabled ? ' is-disabled' : ''}${flat ? ' is-degraded' : ''}${reducedMotion ? ' is-still' : ''}`} disabled={disabled}>
    <legend>{t('editing_style.title')}</legend>
    <p className="studio-muted">{t('editing_style.lead_ready')}</p>
    <div className="studio-style-row" role="radiogroup" aria-label={t('editing_style.title')} aria-disabled={disabled || undefined}>
      {HTML_TEMPLATE_CHOICES.map(id => {
        const on = id === selected
        const recommendedCard = recommendation?.template === id
        const label = `${t(COPY[id].name)}${recommendedCard ? `, ${t('editing_style.badge')}` : ''}, ${t(COPY[id].desc)}`
        return <div
          key={id}
          ref={node => { cards.current[id] = node }}
          data-style={id}
          className={`studio-style-card${on ? ' is-selected' : ''}${hover === id ? ' is-hover' : ''}`}
          role="radio"
          aria-checked={on}
          aria-disabled={disabled || undefined}
          aria-label={label}
          tabIndex={disabled ? -1 : on ? 0 : -1}
          onClick={() => choose(id, 'mouse')}
          onKeyDown={event => onCardKey(id, event)}
          onMouseEnter={() => setHover(id)}
          onMouseLeave={() => setHover(current => current === id ? null : current)}
          onFocus={() => setFocus(id)}
          onBlur={() => setFocus(current => current === id ? null : current)}
        >
          <div className="studio-style-thumb">
            <img src={STYLE_POSTERS[id]} alt="" />
            <video
              ref={node => { videos.current[id] = node }}
              muted
              loop
              playsInline
              preload="auto"
              aria-hidden="true"
              poster={STYLE_POSTERS[id]}
              onPlaying={event => {
                if (event.currentTarget.dataset.show === '1') event.currentTarget.classList.add('is-playing')
              }}
              onTimeUpdate={event => {
                const bar = bars.current[id]
                if (bar) bar.style.transform = `scaleX(${Math.min(1, event.currentTarget.currentTime / PREVIEW_SECONDS)})`
              }}
            />
            {loading && id === 'editorial' ? <span className="studio-style-badge studio-style-badge--wait" aria-hidden="true" /> : null}
            {recommendedCard ? <span className="studio-style-badge">{t('editing_style.badge')}</span> : null}
            <span className={`studio-style-radio${on ? ' is-on' : ''}`} aria-hidden="true">{on ? '✓' : ''}</span>
            <span className="studio-style-mark" aria-hidden="true">{t('editing_style.preview_mark')}</span>
            <span className="studio-style-progress" aria-hidden="true"><i ref={node => { bars.current[id] = node }} /></span>
            {reducedMotion && <button type="button" className="studio-style-preview-btn" onClick={event => { event.stopPropagation(); setPinned(id) }}>{t('editing_style.preview_button')}</button>}
          </div>
          <div className="studio-style-name">{t(COPY[id].name)}</div>
          <div className="studio-style-desc">{t(COPY[id].desc)}</div>
        </div>
      })}
    </div>
    <div className="studio-style-why" aria-live="polite">
      <span className="studio-style-recognition">
        <StyleProbeLine sourceKey={sourceKey} />
        <span aria-hidden="true">·</span>
        {loading ? <span className="studio-style-why-wait">{t('editing_style.analyzing')}</span> : overridden && recommendation ? <>
          <b>{t('editing_style.override', { style: t(COPY[manual].name), recommended: t(COPY[recommendation.template].name) })}</b>
          <button type="button" className="studio-link" onClick={restore}>{t('editing_style.restore')}</button>
        </> : <span>{t(`editing_style.reason.${recommendation?.reason_code || 'default'}`)}</span>}
      </span>
    </div>
    {intelMac && <p className="studio-muted studio-style-intel">{t('editing_style.intel_mac')}</p>}
  </fieldset>
}
