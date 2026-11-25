import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { Modal } from 'antd'
import { getLocale, t } from '../../i18n'
import { telemetryId } from '../../analytics/workflow'
import { trackTemplateOverride, trackTemplatePickerShown, trackTemplatePreviewFailed, trackTemplatePreviewPlayed, trackTemplateRestore } from '../../analytics/studio'
import { captureStudioException } from '../../desktop/sentry'
import { requestStyleRecommendation } from './editingStyleClient'
import { loadStylePreview, posterForTemplate } from './editingStyleMedia'
import { beginStyleRecommendation, readStyle, subscribeStyle, type StyleSnapshot } from './editingStyleSession'
import {
  PREVIEW_SECONDS, chosenTemplate, degradeFromEnvironment, intelMacFromHints, isBuiltinTemplate, selectionAfterRecommendation, supportsBackdrop,
  type BuiltinTemplateChoice, type EditingStyle, type HtmlTemplateChoice,
} from './editingStyle'
import {
  installRemoteTemplate, resolveLocalizedCopy, syncTemplateCatalog, uninstallUserTemplate, useTemplateCatalog,
  type TemplateCatalogItem,
} from './templateCatalogClient'

type InputKind = 'mouse' | 'keyboard'
type Trigger = 'hover' | 'focus' | 'keyboard' | 'button' | 'select'

const COPY: Record<BuiltinTemplateChoice, { name: string; desc: string }> = {
  editorial: { name: 'editing_style.editorial.name', desc: 'editing_style.editorial.desc' },
  street: { name: 'editing_style.street.name', desc: 'editing_style.street.desc' },
  news: { name: 'editing_style.news.name', desc: 'editing_style.news.desc' },
  cinema: { name: 'editing_style.cinema.name', desc: 'editing_style.cinema.desc' },
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

const CATEGORY_ORDER = ['gaming', 'interview', 'knowledge', 'general'] as const

function categoryLabel(cat: string): string {
  if (cat === 'all') return t('editing_style.category.all')
  if (cat === 'gaming') return t('editing_style.category.gaming')
  if (cat === 'interview') return t('editing_style.category.interview')
  if (cat === 'knowledge') return t('editing_style.category.knowledge')
  if (cat === 'general') return t('editing_style.category.general')
  return cat
}

function itemCategory(item: TemplateCatalogItem): string {
  const raw = (item.category || 'general').trim().toLowerCase()
  if (raw === 'gaming' || raw === 'game' || raw === 'livestream') return 'gaming'
  if (raw === 'interview' || raw === 'podcast' || raw === 'editorial') return 'interview'
  if (raw === 'knowledge' || raw === 'notes' || raw === 'note' || raw === 'xiaohongshu') return 'knowledge'
  return 'general'
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
  const { items: catalogItems, installed, remote } = useTemplateCatalog()
  const [syncing, setSyncing] = useState(false)
  const [installingId, setInstallingId] = useState<string | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [galleryOpen, setGalleryOpen] = useState(false)
  const [canPrev, setCanPrev] = useState(false)
  const [canNext, setCanNext] = useState(false)
  const rowRef = useRef<HTMLDivElement | null>(null)
  const locale = getLocale()
  const itemById = new Map<string, TemplateCatalogItem>(catalogItems.map(item => [item.id, item]))
  const categories = useMemo(() => {
    const present = new Set<string>()
    for (const item of [...installed, ...remote]) present.add(itemCategory(item))
    const ordered = [
      ...CATEGORY_ORDER.filter(cat => present.has(cat)),
      ...Array.from(present).filter(cat => !(CATEGORY_ORDER as readonly string[]).includes(cat)).sort(),
    ]
    return ordered.length > 1 ? ['all', ...ordered] : []
  }, [installed, remote])
  const visibleInstalled = useMemo(
    () => activeCategory === 'all' ? installed : installed.filter(item => itemCategory(item) === activeCategory),
    [installed, activeCategory],
  )
  const visibleRemote = useMemo(
    () => activeCategory === 'all' ? remote : remote.filter(item => itemCategory(item) === activeCategory),
    [remote, activeCategory],
  )
  const totalCount = installed.length + remote.length
  const installedIds = installed.map(item => item.id)

  const updateScrollArrows = useCallback(() => {
    const el = rowRef.current
    if (!el) { setCanPrev(false); setCanNext(false); return }
    setCanPrev(el.scrollLeft > 4)
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4)
  }, [])

  useEffect(() => {
    updateScrollArrows()
    const el = rowRef.current
    if (!el) return
    const onResize = () => updateScrollArrows()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [updateScrollArrows, visibleInstalled.length, visibleRemote.length, sourceKey])

  const scrollRow = (dir: -1 | 1) => {
    const el = rowRef.current
    if (!el) return
    const step = Math.max(240, Math.round(el.clientWidth * 0.8))
    el.scrollBy({ left: dir * step, behavior: 'smooth' })
  }
  const styleName = (id: EditingStyle): string => (
    isBuiltinTemplate(id) ? t(COPY[id].name) : resolveLocalizedCopy(itemById.get(id)?.name, locale, id)
  )
  const styleDesc = (id: EditingStyle): string => (
    isBuiltinTemplate(id) ? t(COPY[id].desc) : resolveLocalizedCopy(itemById.get(id)?.desc, locale, '')
  )

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
  const index = installedIds.indexOf(selected)

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
  const installedKey = installedIds.join(',')
  const screenKey = installedIds.map(id => visible.current[id] === false ? '0' : '1').join('')
  const playKey = `${playing.slice(0, 2).join(',')}|${screenKey}|${viewTick}|${installedKey}`

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
    for (const id of installedIds) {
      const node = cards.current[id]
      if (node) observer.observe(node)
    }
    return () => observer.disconnect()
  }, [sourceKey, installedKey])

  useEffect(() => {
    if (!sourceKey || reducedMotion) return
    const recommended = recommendation?.template ?? selected
    const order = [recommended, ...installedIds.filter(id => id !== recommended && visible.current[id] !== false)]
    let cancel = false
    let cursor = 0
    const ric = window.requestIdleCallback || ((cb: IdleRequestCallback) => window.setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 } as IdleDeadline), 80))
    const prime = async (id: EditingStyle) => {
      const urls = await loadStylePreview(id, itemById.get(id))
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
  }, [sourceKey, reducedMotion, selected, recommendation?.template, viewTick, installedKey])

  useEffect(() => {
    const want = new Set(playKey.split('|')[0].split(',').filter(Boolean) as EditingStyle[])
    let cancel = false
    for (const id of installedIds) {
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
      void loadStylePreview(id, itemById.get(id)).then(urls => {
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

  const onSyncCatalog = async () => {
    if (syncing || disabled) return
    setSyncing(true)
    setCatalogError(null)
    try {
      await syncTemplateCatalog()
    } catch {
      setCatalogError(t('editing_style.install_failed'))
    } finally {
      setSyncing(false)
    }
  }

  const onInstallRemote = async (id: string) => {
    if (installingId || disabled) return
    setInstallingId(id)
    setCatalogError(null)
    try {
      await installRemoteTemplate(id)
      choose(id, 'mouse')
    } catch {
      setCatalogError(t('editing_style.install_failed'))
    } finally {
      setInstallingId(null)
    }
  }

  const onUninstall = async (id: string) => {
    if (installingId || disabled) return
    setCatalogError(null)
    try {
      await uninstallUserTemplate(id)
      if (selected === id) choose('editorial', 'mouse')
    } catch {
      setCatalogError(t('editing_style.install_failed'))
    }
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
    const next = installedIds[(installedIds.indexOf(id) + delta + installedIds.length) % installedIds.length]
    choose(next, 'keyboard')
    cards.current[next]?.focus()
  }

  if (!sourceKey) {
    return <fieldset className="studio-template-picker studio-style-picker" disabled={disabled}>
      <legend>{t('editing_style.title')}</legend>
      <p className="studio-muted">{t('editing_style.lead')}</p>
    </fieldset>
  }

  const chooseFromGallery = (id: EditingStyle) => {
    choose(id, 'mouse')
    setGalleryOpen(false)
    if (activeCategory !== 'all') {
      const item = itemById.get(id)
      if (item && itemCategory(item) !== activeCategory) setActiveCategory('all')
    }
    window.setTimeout(() => {
      cards.current[id]?.scrollIntoView?.({ behavior: 'smooth', inline: 'nearest', block: 'nearest' })
    }, 60)
  }

  const loading = !recommendation
  const overridden = manual !== null && recommendation !== null && manual !== recommendation.template
  const flat = degraded || reducedTransparency
  return <fieldset className={`studio-template-picker studio-style-picker${disabled ? ' is-disabled' : ''}${flat ? ' is-degraded' : ''}${reducedMotion ? ' is-still' : ''}`} disabled={disabled}>
    <legend>{t('editing_style.title')}</legend>
    <div className="studio-style-toolbar">
      <p className="studio-muted" style={{ margin: 0 }}>{t('editing_style.lead_ready')}</p>
      <div className="studio-style-toolbar-actions">
        {totalCount > 5 ? (
          <button
            type="button"
            className="studio-style-all-btn"
            disabled={disabled}
            onClick={() => setGalleryOpen(true)}
          >
            {t('editing_style.view_all', { count: totalCount })}
          </button>
        ) : null}
        <button
          type="button"
          className={`studio-style-refresh-btn${syncing ? ' is-syncing' : ''}`}
          disabled={disabled || syncing}
          title={remote.length > 0 ? t('editing_style.new_count', { count: remote.length }) : t('editing_style.sync_catalog')}
          aria-label={remote.length > 0 ? t('editing_style.new_count', { count: remote.length }) : t('editing_style.sync_catalog')}
          onClick={onSyncCatalog}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M13.5 8a5.5 5.5 0 1 1-1.35-3.6" />
            <path d="M13.5 2.5v2.9h-2.9" />
          </svg>
          {remote.length > 0 ? <span className="studio-style-refresh-dot" aria-hidden="true" /> : null}
        </button>
      </div>
    </div>
    {categories.length > 0 ? (
      <div className="studio-style-cats" role="tablist" aria-label={t('editing_style.title')}>
        {categories.map(cat => (
          <button
            key={cat}
            type="button"
            role="tab"
            aria-selected={activeCategory === cat}
            className={`studio-style-cat-pill${activeCategory === cat ? ' is-active' : ''}`}
            disabled={disabled}
            onClick={() => { setActiveCategory(cat); if (rowRef.current) rowRef.current.scrollLeft = 0 }}
          >
            {categoryLabel(cat)}
          </button>
        ))}
      </div>
    ) : null}
    <div className="studio-style-carousel">
      {canPrev ? (
        <button type="button" className="studio-style-nav studio-style-nav--prev" aria-label={t('editing_style.scroll_prev')} onClick={() => scrollRow(-1)}>
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M10 3.5L5.5 8 10 12.5" />
          </svg>
        </button>
      ) : null}
      {canNext ? (
        <button type="button" className="studio-style-nav studio-style-nav--next" aria-label={t('editing_style.scroll_next')} onClick={() => scrollRow(1)}>
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M6 3.5L10.5 8 6 12.5" />
          </svg>
        </button>
      ) : null}
      <div
        ref={rowRef}
        className="studio-style-row"
        role="radiogroup"
        aria-label={t('editing_style.title')}
        aria-disabled={disabled || undefined}
        onScroll={updateScrollArrows}
      >
        {visibleInstalled.map(item => {
        const id = item.id
        const on = id === selected
        const recommendedCard = recommendation?.template === id
        const name = styleName(id)
        const desc = styleDesc(id)
        const poster = posterForTemplate(id, item)
        const label = `${name}${recommendedCard ? `, ${t('editing_style.badge')}` : ''}, ${desc}`
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
            <img src={poster} alt="" />
            <video
              ref={node => { videos.current[id] = node }}
              muted
              loop
              playsInline
              preload="auto"
              aria-hidden="true"
              poster={poster}
              onError={event => {
                // Missing or undecodable preview: hide the video so the static poster <img> shows.
                const node = event.currentTarget
                node.classList.remove('is-playing')
                node.dataset.show = '0'
                if (reportedFail.current.has(id)) return
                reportedFail.current.add(id)
                trackTemplatePreviewFailed({ template: id, error_kind: node.error?.code === 4 ? 'unsupported' : 'decode' })
              }}
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
            {item.removable ? <button type="button" className="studio-style-remove-btn" title={t('editing_style.uninstall')} aria-label={t('editing_style.uninstall')} onClick={event => { event.stopPropagation(); void onUninstall(id) }}>×</button> : null}
            {item.update_available ? <button type="button" className="studio-style-preview-btn" onClick={event => { event.stopPropagation(); void onInstallRemote(id) }}>{installingId === id ? t('editing_style.installing') : t('editing_style.update')}</button> : null}
            <span className={`studio-style-radio${on ? ' is-on' : ''}`} aria-hidden="true">{on ? '✓' : ''}</span>
            <span className="studio-style-mark" aria-hidden="true">{t('editing_style.preview_mark')}</span>
            <span className="studio-style-progress" aria-hidden="true"><i ref={node => { bars.current[id] = node }} /></span>
            {reducedMotion && <button type="button" className="studio-style-preview-btn" onClick={event => { event.stopPropagation(); setPinned(id) }}>{t('editing_style.preview_button')}</button>}
          </div>
          <div className="studio-style-name">{name}</div>
          <div className="studio-style-desc">{desc}</div>
        </div>
      })}
      {visibleRemote.map(item => {
        const id = item.id
        const name = resolveLocalizedCopy(item.name, locale, id)
        const desc = resolveLocalizedCopy(item.desc, locale, '')
        const poster = posterForTemplate(id, item)
        const remoteVideo = item.preview_mp4_url || item.preview_webm_url || ''
        const busy = installingId === id
        return <div
          key={id}
          data-style={id}
          className="studio-style-card studio-style-card--remote"
          onMouseEnter={e => {
            if (reducedMotion || !remoteVideo) return
            const v = e.currentTarget.querySelector('video')
            if (v) { v.currentTime = 0; v.classList.add('is-playing'); void v.play().catch(() => {}) }
          }}
          onMouseLeave={e => {
            const v = e.currentTarget.querySelector('video')
            if (v) { v.pause(); v.classList.remove('is-playing') }
          }}
        >
          <div className="studio-style-thumb">
            <img src={poster} alt="" />
            {remoteVideo ? (
              <video muted loop playsInline preload="metadata" poster={poster} src={remoteVideo} aria-hidden="true" />
            ) : null}
            <span className="studio-style-badge">{t('editing_style.remote_badge')}</span>
            {remoteVideo ? <span className="studio-style-mark" aria-hidden="true">{t('editing_style.preview_mark')}</span> : null}
            <button type="button" className="studio-style-preview-btn" disabled={disabled || Boolean(installingId)} onClick={() => void onInstallRemote(id)}>
              {busy ? t('editing_style.installing') : t('editing_style.install')}
            </button>
          </div>
          <div className="studio-style-name">{name}</div>
          <div className="studio-style-desc">{desc}</div>
        </div>
      })}
      </div>
    </div>
    <Modal
      open={galleryOpen}
      onCancel={() => setGalleryOpen(false)}
      footer={null}
      centered
      width={880}
      title={t('editing_style.gallery_title')}
      className="studio-style-gallery-modal"
    >
      {categories.length > 0 ? (
        <div className="studio-style-cats studio-style-cats--modal" role="tablist">
          {categories.map(cat => (
            <button
              key={cat}
              type="button"
              role="tab"
              aria-selected={activeCategory === cat}
              className={`studio-style-cat-pill${activeCategory === cat ? ' is-active' : ''}`}
              onClick={() => setActiveCategory(cat)}
            >
              {categoryLabel(cat)}
            </button>
          ))}
        </div>
      ) : null}
      <div className="studio-style-modal-grid">
        {visibleInstalled.map(item => {
          const id = item.id
          const on = id === selected
          const recommendedCard = recommendation?.template === id
          const name = styleName(id)
          const desc = styleDesc(id)
          const poster = posterForTemplate(id, item)
          return <div
            key={id}
            className={`studio-style-card${on ? ' is-selected' : ''}`}
            role="button"
            tabIndex={0}
            onClick={() => chooseFromGallery(id)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chooseFromGallery(id) } }}
          >
            <div className="studio-style-thumb">
              <img src={poster} alt="" />
              {recommendedCard ? <span className="studio-style-badge">{t('editing_style.badge')}</span> : null}
              <span className={`studio-style-radio${on ? ' is-on' : ''}`} aria-hidden="true">{on ? '✓' : ''}</span>
            </div>
            <div className="studio-style-name">{name}</div>
            <div className="studio-style-desc">{desc}</div>
          </div>
        })}
        {visibleRemote.map(item => {
          const id = item.id
          const name = resolveLocalizedCopy(item.name, locale, id)
          const desc = resolveLocalizedCopy(item.desc, locale, '')
          const poster = posterForTemplate(id, item)
          const remoteVideo = item.preview_mp4_url || item.preview_webm_url || ''
          const busy = installingId === id
          return <div
            key={id}
            className="studio-style-card studio-style-card--remote"
            onMouseEnter={e => {
              if (reducedMotion || !remoteVideo) return
              const v = e.currentTarget.querySelector('video')
              if (v) { v.currentTime = 0; v.classList.add('is-playing'); void v.play().catch(() => {}) }
            }}
            onMouseLeave={e => {
              const v = e.currentTarget.querySelector('video')
              if (v) { v.pause(); v.classList.remove('is-playing') }
            }}
          >
            <div className="studio-style-thumb">
              <img src={poster} alt="" />
              {remoteVideo ? (
                <video muted loop playsInline preload="metadata" poster={poster} src={remoteVideo} aria-hidden="true" />
              ) : null}
              <span className="studio-style-badge">{t('editing_style.remote_badge')}</span>
              {remoteVideo ? <span className="studio-style-mark" aria-hidden="true">{t('editing_style.preview_mark')}</span> : null}
              <button type="button" className="studio-style-preview-btn" disabled={Boolean(installingId)} onClick={() => void onInstallRemote(id).then(() => setGalleryOpen(false))}>
                {busy ? t('editing_style.installing') : t('editing_style.install')}
              </button>
            </div>
            <div className="studio-style-name">{name}</div>
            <div className="studio-style-desc">{desc}</div>
          </div>
        })}
      </div>
    </Modal>
    <div className="studio-style-why" aria-live="polite">
      {catalogError ? <span>{catalogError}</span> : loading ? <span className="studio-style-why-wait">{t('editing_style.analyzing')}</span> : overridden && recommendation ? <>
        <b>{t('editing_style.override', { style: styleName(manual), recommended: styleName(recommendation.template) })}</b>
        <button type="button" className="studio-link" onClick={restore}>{t('editing_style.restore')}</button>
      </> : <span>{t(`editing_style.reason.${recommendation?.reason_code || 'default'}`)}</span>}
    </div>
    {intelMac && <p className="studio-muted studio-style-intel">{t('editing_style.intel_mac')}</p>}
  </fieldset>
}
