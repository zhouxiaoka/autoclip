/**
 * Desktop clipboard + autoclip:// watch. Reads a secret only to offer it.
 * Never logs the text. Web clipboard reads that the browser blocks are ignored.
 */

import { isDesktopMode } from '../../utils/desktopMode'
import { extractApiKey, inferProviderId, parseAutoclipLink, type GuideTarget } from './keyGuide'
import { publishOffer, type KeyOffer } from './keyGuideBus'

const DISMISS_KEY = 'autoclip.keyguide.dismissed'
let targets: GuideTarget[] = []
let unlistenDeepLink: (() => void) | null = null

function dismissed(): Set<string> {
  try {
    const raw = sessionStorage.getItem(DISMISS_KEY)
    return new Set(raw ? JSON.parse(raw) as string[] : [])
  } catch {
    return new Set()
  }
}

function remember(hash: string) {
  const next = dismissed()
  next.add(hash)
  try { sessionStorage.setItem(DISMISS_KEY, JSON.stringify([...next])) } catch { /* session only */ }
}

export async function fingerprint(value: string): Promise<string> {
  try {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
    return [...new Uint8Array(digest)].slice(0, 8).map(byte => byte.toString(16).padStart(2, '0')).join('')
  } catch {
    let hash = 5381
    for (let i = 0; i < value.length; i += 1) hash = ((hash * 33) ^ value.charCodeAt(i)) >>> 0
    return hash.toString(16)
  }
}

export function setKeyGuideTargets(next: GuideTarget[]) {
  targets = next
}

async function readClipboard(): Promise<string> {
  const desktop = await isDesktopMode()
  if (desktop) {
    try {
      const { readText } = await import('@tauri-apps/plugin-clipboard-manager')
      return (await readText()) || ''
    } catch {
      return ''
    }
  }
  if (!navigator.clipboard?.readText) return ''
  try { return await navigator.clipboard.readText() } catch { return '' }
}

function offerFromText(text: string, source: KeyOffer['source']): KeyOffer | null {
  const link = parseAutoclipLink(text)
  if (link) {
    const route = inferProviderId(link.key, link.baseUrl, targets)
    const explicit = link.providerId && targets.some(target => target.id === link.providerId) ? link.providerId : null
    const conflict = route.conflict || (!!explicit && !!route.providerId && explicit !== route.providerId)
    return {
      source,
      key: link.key,
      baseUrl: link.baseUrl,
      hintedProviderId: conflict ? null : (explicit || route.providerId),
      conflict,
    }
  }
  const key = extractApiKey(text)
  if (!key) return null
  const route = inferProviderId(key, '', targets)
  return { source, key, baseUrl: '', hintedProviderId: route.providerId, conflict: route.conflict }
}

export async function scanClipboard(source: 'focus' | 'button'): Promise<'offered' | 'empty' | 'dismissed'> {
  const text = (await readClipboard()).trim()
  if (!text) return 'empty'
  if (/^autoclip:/i.test(text)) {
    const offer = offerFromText(text, 'deeplink')
    if (!offer) return 'empty'
    publishOffer(offer)
    return 'offered'
  }
  const offer = offerFromText(text, 'clipboard')
  if (!offer) return 'empty'
  const hash = await fingerprint(offer.key)
  if (source === 'focus' && dismissed().has(hash)) return 'dismissed'
  publishOffer(offer)
  return 'offered'
}

export async function dismissCurrentOffer(key: string) {
  remember(await fingerprint(key))
}

export function offerPastedKey(text: string, currentProviderId: string): boolean {
  const offer = offerFromText(text, 'paste')
  if (!offer?.hintedProviderId || offer.hintedProviderId === currentProviderId) return false
  publishOffer(offer)
  return true
}

async function listenDeepLinks() {
  if (!(await isDesktopMode())) return
  try {
    const { getCurrent, onOpenUrl } = await import('@tauri-apps/plugin-deep-link')
    const deliver = (urls: string[]) => {
      for (const url of urls) {
        const offer = offerFromText(url, 'deeplink')
        if (offer) publishOffer(offer)
      }
    }
    const current = await getCurrent()
    if (current?.length) deliver(current)
    unlistenDeepLink = await onOpenUrl(deliver)
  } catch {
    /* Web and desktop builds without the plugin keep clipboard paste. */
  }
}

export function startKeyGuideWatch(): () => void {
  let stopped = false
  const onFocus = () => { if (!stopped) void scanClipboard('focus') }
  window.addEventListener('focus', onFocus)
  void listenDeepLinks()
  void scanClipboard('focus')
  return () => {
    stopped = true
    window.removeEventListener('focus', onFocus)
    unlistenDeepLink?.()
    unlistenDeepLink = null
  }
}
