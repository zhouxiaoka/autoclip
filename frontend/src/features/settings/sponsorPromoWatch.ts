/**
 * One promotion fetch for this screen lifetime.
 * A late response from an older request or an unmounted host is dropped.
 * Cleanup never clears another host.
 * Settings and the idle interval keep reading after startup follow ends,
 * so a deferred accept is not dropped when the first short reads stay pending.
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

function sequenceOf(value: AppliedSponsorPromo): number | null {
  return typeof value.sequence === 'number' ? value.sequence : null
}

/** Same publisher. A missing epoch still compares revisions, which covers an older build. */
function sameEpoch(prev: AppliedSponsorPromo, next: AppliedSponsorPromo): boolean {
  return !prev.instance || !next.instance || prev.instance === next.instance
}

function publish(next: AppliedSponsorPromo) {
  const prev = snapshot
  if (prev) {
    const previousSequence = sequenceOf(prev)
    const nextSequence = sequenceOf(next)
    if (previousSequence !== null && nextSequence !== null && nextSequence < previousSequence) return
    const newerSequence = previousSequence !== null && nextSequence !== null && nextSequence > previousSequence
    const same = sameEpoch(prev, next)
    if (!newerSequence && same && typeof next.revision === 'number' && typeof prev.revision === 'number' && next.revision < prev.revision) return
    if (!newerSequence && prev.pending === false && next.pending === true && (same ? (next.revision ?? 0) <= (prev.revision ?? 0) : true)) return
    if (!newerSequence && !same && previousSequence !== null && nextSequence === null) return
  }
  snapshot = next
  writePromoSnapshot({
    choices: [...next.choices],
    defaultChoice: next.defaultChoice,
    statuses: next.statuses,
    registerUrls: next.registerUrls,
    notices: next.notices,
    ...(next.byLocale ? { byLocale: next.byLocale } : {}),
    sequence: next.sequence,
    revision: next.revision,
    instance: next.instance,
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

let pursuit: Promise<AppliedSponsorPromo | null> | null = null
let pursuitHost = -1

export async function refreshSponsorPromo(
  trigger: 'startup' | 'settings' | 'interval' | 'resume' = 'settings',
  request?: number,
): Promise<AppliedSponsorPromo | null> {
  if (request === undefined && (trigger === 'settings' || trigger === 'interval') && hostSerial !== 0) {
    return pursueSettled(trigger)
  }
  const ticket = request ?? ++requestSerial
  const applied = await loadSponsorPromo(trigger)
  if (ticket !== requestSerial) return null
  if (applied) publish(applied)
  return applied
}

/** One settings/interval chain per host. It keeps reading until the view is no longer pending. */
function pursueSettled(trigger: 'settings' | 'interval'): Promise<AppliedSponsorPromo | null> {
  const host = hostSerial
  const previous = pursuit && pursuitHost === host ? pursuit : Promise.resolve(null)
  const run = previous.then(() => {
    if (host !== hostSerial) return readSponsorPromo()
    return readUntilSettled(host, trigger)
  })
  pursuit = run
  pursuitHost = host
  void run.finally(() => {
    if (pursuit === run) {
      pursuit = null
      pursuitHost = -1
    }
  })
  return run
}

async function readUntilSettled(
  host: number,
  trigger: 'settings' | 'interval' | 'resume',
): Promise<AppliedSponsorPromo | null> {
  let next: 'settings' | 'interval' | 'resume' = trigger
  while (host === hostSerial) {
    const ticket = ++requestSerial
    const started = Date.now()
    const applied = await refreshSponsorPromo(next, ticket)
    if (host !== hostSerial) return applied
    if (applied && !applied.pending) return applied
    if (!applied && readSponsorPromo() && !readSponsorPromo()?.pending) return readSponsorPromo()
    next = 'resume'
    if (Date.now() - started < 250) {
      await delay(SPONSOR_PROMO_FAST_GAP_MS)
      if (host !== hostSerial) return readSponsorPromo()
    }
  }
  return readSponsorPromo()
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
