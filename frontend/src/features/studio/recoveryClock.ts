/** the one timing rule of the install-recovery wait (contract, approved by 2026-10-17 11:49).
 *
 * The wait has two outcomes besides continuing: `offline` (no answer for OFFLINE_MS of counted time) and `timeout`
 * (no progress for STALL_MS of counted time). Every observation (the end of a round) counts the time since the
 * previous one, capped at 2 x pollMs + 2 x readTimeoutMs (one late wait plus a probe and one follow-up read that both
 * ran into their timeout). Anything above the cap is sleep / throttling and is dropped; nothing is ever reset by a
 * long gap, so under any steady schedule (pollMs > 0) an outcome is reached after a bounded number of observations.
 * Pure: no imports, no clock of its own. */
export const STALL_MS = 10 * 60 * 1000
/** #403: counted time the backend must be unreachable (network errors / timeouts only) before a wait is failed. */
export const OFFLINE_MS = 30 * 1000

export interface Clock { lastAt: number; offlineMs: number; stalledMs: number; unanswered: boolean }
export interface Observation { now: number; answered: boolean; progressed: boolean; pollMs: number; readTimeoutMs: number }
export interface Limits { offlineMs: number; stallMs: number }
export type Outcome = 'continue' | 'offline' | 'timeout'

/** open / install / retry (and a re-activated round): counting starts now. */
export const startClock = (now: number): Clock => ({ lastAt: now, offlineMs: 0, stalledMs: 0, unanswered: false })
/** The most one observation can count. */
export const capMs = (pollMs: number, readTimeoutMs: number) => 2 * pollMs + 2 * readTimeoutMs

export function observe(c: Clock, o: Observation, limits: Limits = { offlineMs: OFFLINE_MS, stallMs: STALL_MS }): { clock: Clock; counted: number; outcome: Outcome } {
  const counted = Math.min(Math.max(o.now - c.lastAt, 0), capMs(o.pollMs, o.readTimeoutMs))
  const offlineMs = o.answered ? 0 : c.offlineMs + counted
  const stalledMs = o.progressed ? 0 : c.stalledMs + counted
  const outcome: Outcome = !o.answered && offlineMs >= limits.offlineMs ? 'offline' : stalledMs >= limits.stallMs ? 'timeout' : 'continue'
  return { clock: { lastAt: o.now, offlineMs, stalledMs, unanswered: !o.answered }, counted, outcome }
}
