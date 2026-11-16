/**
 * One promotion fetch for this screen lifetime.
 * A late response from an older request or an unmounted host is dropped.
 * Cleanup never clears another host.
 */
import { useEffect, useState } from 'react'
import { loadSponsorPromo, providerServiceNotice, type AppliedSponsorPromo } from './sponsorPromo'
import { writePromoSnapshot } from './sponsorPromoState'

export const SPONSOR_PROMO_INTERVAL_MS = 6 * 60 * 60 * 1000
/** A too-fast pending reply waits this long before the same host asks again. */
export const SPONSOR_PROMO_FAST_GAP_MS = 250

let snapshot: AppliedSponsorPromo | null = null
let requestSerial = 0
let hostSerial = 0
const listeners = new Set<() => void>()

function publish(next: AppliedSponsorPromo) {
  const prev = snapshot
  if (prev && typeof next.revision === 'number' && typeof prev.revision === 'number' && next.revision < prev.revision) return
  if (prev && prev.pending === false && next.pending === true && (next.revision ?? 0) <= (prev.revision ?? 0)) return
  snapshot = next
  writePromoSnapshot({
    choices: [...next.choices],
    defaultChoice: next.defaultChoice,
    statuses: next.statuses,
    registerUrls: next.registerUrls,
    notices: next.notices,
    sequence: next.sequence,
    revision: next.revision,
    pending: next.pending,
    source: next.source,
  })
  for (const listener of listeners) listener()
}

export function readSponsorPromo(): AppliedSponsorPromo | null {
  return snapshot
}

export function subscribeSponsorPromo(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export async function refreshSponsorPromo(
  trigger: 'startup' | 'settings' | 'interval' | 'resume',
  request = ++requestSerial,
) {
  const applied = await loadSponsorPromo(trigger)
  if (request !== requestSerial) return null
  if (applied) publish(applied)
  return applied
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/** One follow for this host. A newer host or unmount ends it. Pending keeps a single bounded read open. */
async function follow(host: number) {
  let trigger: 'startup' | 'resume' = 'startup'
  while (host === hostSerial) {
    const ticket = ++requestSerial
    const started = Date.now()
    const applied = await refreshSponsorPromo(trigger, ticket)
    if (host !== hostSerial) return
    if (applied && !applied.pending) return
    if (!applied && readSponsorPromo() && !readSponsorPromo()?.pending) return
    trigger = 'resume'
    if (Date.now() - started < 250) {
      await delay(SPONSOR_PROMO_FAST_GAP_MS)
      if (host !== hostSerial) return
    }
  }
}

export function startSponsorPromoWatch(): () => void {
  const host = ++hostSerial
  let stopped = false
  let chaining = true
  void follow(host).finally(() => { if (host === hostSerial) chaining = false })
  const timer = setInterval(() => {
    if (stopped || host !== hostSerial || chaining) return
    void refreshSponsorPromo('interval')
  }, SPONSOR_PROMO_INTERVAL_MS)
  return () => {
    stopped = true
    clearInterval(timer)
    if (host !== hostSerial) return
    hostSerial += 1
    requestSerial += 1
    chaining = false
  }
}

export function useSponsorPromo(): AppliedSponsorPromo | null {
  const [value, setValue] = useState(snapshot)
  useEffect(() => subscribeSponsorPromo(() => setValue(readSponsorPromo())), [])
  return value
}

export { providerServiceNotice }
