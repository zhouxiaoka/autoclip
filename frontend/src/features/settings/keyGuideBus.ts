/**
 * In-memory handoff for a detected key. The key never goes into the router,
 * sessionStorage, or an analytics property. Dismissal stores only a hash.
 */

export type KeyOffer = {
  source: 'clipboard' | 'deeplink' | 'paste'
  key: string
  baseUrl: string
  hintedProviderId: string | null
  conflict: boolean
}

export type KeyGuideRequest = {
  providerId: string
  apiKey: string
  baseUrl: string
  /** True only after the user confirms, including when that replaces a saved key. */
  overwrite: boolean
}

type Applier = (request: KeyGuideRequest) => Promise<{ ok: boolean; blocked?: boolean; connectionId?: string }>

let offer: KeyOffer | null = null
let pendingRequest: KeyGuideRequest | null = null
let pendingSelect: string | null = null
let applier: Applier | null = null
let scanListener: (() => void) | null = null
const listeners = new Set<(offer: KeyOffer | null) => void>()

export function currentOffer(): KeyOffer | null {
  return offer
}

export function publishOffer(next: KeyOffer) {
  offer = next
  listeners.forEach(listener => listener(offer))
}

export function clearOffer() {
  offer = null
  listeners.forEach(listener => listener(offer))
}

export function subscribeOffers(listener: (offer: KeyOffer | null) => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function registerKeyGuideApplier(fn: Applier) {
  applier = fn
  return () => {
    if (applier === fn) applier = null
  }
}

export function hasKeyGuideApplier() {
  return !!applier
}

export function stageKeyGuideRequest(request: KeyGuideRequest) {
  pendingRequest = request
}

export function takePendingRequest(): KeyGuideRequest | null {
  const request = pendingRequest
  pendingRequest = null
  return request
}

export function requestClipboardScan() {
  scanListener?.()
}

export function onClipboardScanRequest(listener: () => void) {
  scanListener = listener
  return () => {
    if (scanListener === listener) scanListener = null
  }
}

export function stagePendingSelect(id: string) {
  pendingSelect = id
}

export function takePendingSelect(): string | null {
  const id = pendingSelect
  pendingSelect = null
  return id
}

export async function commitKeyGuide(request: KeyGuideRequest) {
  if (!applier) {
    stageKeyGuideRequest(request)
    return { ok: false, blocked: false, deferred: true as const }
  }
  const result = await applier(request)
  return { ok: result.ok, blocked: !!result.blocked, connectionId: result.connectionId, deferred: false as const }
}
