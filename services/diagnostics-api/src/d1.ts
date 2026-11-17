import type { CaseRow, CommitResult, ObjectRow } from './memory.ts'
import { tryReserve, type Limits, type QuotaState } from './quota.ts'

interface Prepared {
  bind(...values: unknown[]): { first: <T>() => Promise<T | null>; run: () => Promise<{ meta?: { changes?: number } }>; all: <T>() => Promise<{ results: T[] }> }
}

export interface D1 {
  prepare(sql: string): Prepared
}

/** Durable quota. reserve() uses the same predicate as tryReserve and a conditional UPDATE. */
export class D1Repo {
  constructor(private readonly db: D1, private readonly now: () => string) {}

  async reserve(bytes: number, limits: Pick<Limits, 'landedCap' | 'inflightCap'>): Promise<{ ok: true } | { ok: false; reason: string }> {
    const current = await this.snapshot()
    const decision = tryReserve(current, bytes, limits)
    if (!decision.ok) return decision
    const result = await this.db.prepare(
      `UPDATE quota SET reserved_bytes = reserved_bytes + ?1, updated_at = ?2
       WHERE id = 1 AND landed_bytes + reserved_bytes + ?1 <= ?3 AND reserved_bytes + ?1 <= ?4`,
    ).bind(bytes, this.now(), limits.landedCap, limits.inflightCap).run()
    if ((result.meta?.changes ?? 0) !== 1) return { ok: false, reason: 'landed_cap' }
    return { ok: true }
  }

  async release(bytes: number): Promise<void> {
    await this.db.prepare(
      `UPDATE quota SET reserved_bytes = MAX(0, reserved_bytes - ?1), updated_at = ?2 WHERE id = 1`,
    ).bind(bytes, this.now()).run()
  }

  async land(bytes: number): Promise<void> {
    await this.db.prepare(
      `UPDATE quota SET reserved_bytes = MAX(0, reserved_bytes - ?1), landed_bytes = landed_bytes + ?1, updated_at = ?2 WHERE id = 1`,
    ).bind(bytes, this.now()).run()
  }

  async unland(bytes: number): Promise<void> {
    await this.db.prepare(
      `UPDATE quota SET landed_bytes = MAX(0, landed_bytes - ?1), updated_at = ?2 WHERE id = 1`,
    ).bind(bytes, this.now()).run()
  }

  async snapshot(): Promise<QuotaState> {
    const row = await this.db.prepare(`SELECT landed_bytes, reserved_bytes FROM quota WHERE id = 1`).bind().first<{ landed_bytes: number; reserved_bytes: number }>()
    return { landed: row?.landed_bytes ?? 0, reserved: row?.reserved_bytes ?? 0 }
  }

  async hit(bucket: string, limit: number): Promise<boolean> {
    await this.db.prepare(
      `INSERT INTO rate_windows (bucket, window_start, hits) VALUES (?1, '', 1)
       ON CONFLICT (bucket, window_start) DO UPDATE SET hits = hits + 1`,
    ).bind(bucket).run()
    const row = await this.db.prepare(`SELECT hits FROM rate_windows WHERE bucket = ?1`).bind(bucket).first<{ hits: number }>()
    return (row?.hits ?? limit + 1) <= limit
  }

  async findByIdempotency(key: string): Promise<CaseRow | null> {
    const row = await this.db.prepare(`SELECT * FROM cases WHERE idempotency_key = ?1`).bind(key).first<Record<string, unknown>>()
    return row ? caseFrom(row) : null
  }

  async getCase(id: string): Promise<CaseRow | null> {
    const row = await this.db.prepare(`SELECT * FROM cases WHERE case_id = ?1`).bind(id).first<Record<string, unknown>>()
    return row ? caseFrom(row) : null
  }

  async saveCase(row: CaseRow): Promise<void> {
    await this.db.prepare(
      `INSERT INTO cases (case_id, idempotency_key, manifest_sha256, state, capability_sha256, consent_version, manifest_bytes, reserved_bytes, landed_bytes, created_at, expires_at, updated_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)
       ON CONFLICT (case_id) DO UPDATE SET state = ?4, capability_sha256 = ?5, reserved_bytes = ?8, landed_bytes = ?9, updated_at = ?12`,
    ).bind(row.caseId, row.idempotencyKey, row.manifestSha256, row.state, row.capabilitySha256, row.consentVersion, row.manifestBytes, row.reservedBytes, row.landedBytes, row.createdAt, row.expiresAt, row.updatedAt).run()
  }

  async getObject(id: string): Promise<ObjectRow | null> {
    const row = await this.db.prepare(`SELECT * FROM objects WHERE object_id = ?1`).bind(id).first<Record<string, unknown>>()
    return row ? objectFrom(row) : null
  }

  async saveObject(row: ObjectRow): Promise<void> {
    await this.db.prepare(
      `INSERT INTO objects (object_id, case_id, role, r2_key, declared_bytes, actual_bytes, sha256, upload_id, part_plan, state, created_at, updated_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)
       ON CONFLICT (object_id) DO UPDATE SET actual_bytes = ?6, state = ?10, updated_at = ?12`,
    ).bind(
      row.objectId, row.caseId, row.role, row.r2Key, row.declaredBytes, row.actualBytes, row.sha256,
      row.uploadId, JSON.stringify(row.partPlan), row.state, row.createdAt, row.updatedAt,
    ).run()
  }

  async objectsFor(caseId: string): Promise<ObjectRow[]> {
    const rows = await this.db.prepare(`SELECT * FROM objects WHERE case_id = ?1`).bind(caseId).all<Record<string, unknown>>()
    return rows.results.map(objectFrom)
  }

  async allCases(): Promise<CaseRow[]> {
    const rows = await this.db.prepare(`SELECT * FROM cases`).bind().all<Record<string, unknown>>()
    return rows.results.map(caseFrom)
  }

  async commitFile(caseId: string, objectId: string, actualBytes: number, now: string): Promise<CommitResult> {
    const object = await this.getObject(objectId)
    const row = await this.getCase(caseId)
    if (!object || object.caseId !== caseId || !row || row.state === 'deleted') return { committed: false, reason: 'gone' }
    if (object.state === 'complete') return { committed: false, already: true }
    if (object.state !== 'reserved') return { committed: false, reason: 'gone' }
    const result = await this.db.prepare(
      `UPDATE objects SET actual_bytes = ?1, state = 'complete', updated_at = ?2
       WHERE object_id = ?3 AND case_id = ?4 AND state = 'reserved'`,
    ).bind(actualBytes, now, objectId, caseId).run()
    if ((result.meta?.changes ?? 0) !== 1) {
      const again = await this.getObject(objectId)
      if (again?.state === 'complete') return { committed: false, already: true }
      return { committed: false, reason: 'gone' }
    }
    const revert = () => this.db.prepare(
      `UPDATE objects SET actual_bytes = NULL, state = 'reserved', updated_at = ?1 WHERE object_id = ?2 AND state = 'complete'`,
    ).bind(now, objectId).run().then(() => undefined, () => undefined)
    try {
      await this.land(object.declaredBytes)
    } catch (error) {
      await revert()
      throw error
    }
    try {
      row.reservedBytes = Math.max(0, row.reservedBytes - object.declaredBytes)
      row.landedBytes += object.declaredBytes
      const pending = (await this.objectsFor(caseId)).filter((item) => item.state === 'reserved')
      if (!pending.length) row.state = 'complete'
      row.updatedAt = now
      await this.saveCase(row)
    } catch (error) {
      await this.unland(object.declaredBytes).then(() => undefined, () => undefined)
      await revert()
      throw error
    }
    return { committed: true }
  }

  async reconcile(): Promise<QuotaState> {
    const sums = await this.db.prepare(
      `SELECT COALESCE(SUM(landed_bytes), 0) AS landed, COALESCE(SUM(reserved_bytes), 0) AS reserved FROM cases WHERE state != 'deleted'`,
    ).bind().first<{ landed: number; reserved: number }>()
    await this.db.prepare(
      `UPDATE quota SET landed_bytes = ?1, reserved_bytes = ?2, updated_at = ?3 WHERE id = 1`,
    ).bind(sums?.landed ?? 0, sums?.reserved ?? 0, this.now()).run()
    return { landed: sums?.landed ?? 0, reserved: sums?.reserved ?? 0 }
  }
}

function caseFrom(row: Record<string, unknown>): CaseRow {
  return {
    caseId: String(row.case_id), idempotencyKey: String(row.idempotency_key), manifestSha256: String(row.manifest_sha256),
    state: row.state as CaseRow['state'], capabilitySha256: String(row.capability_sha256), consentVersion: String(row.consent_version),
    manifestBytes: Number(row.manifest_bytes), reservedBytes: Number(row.reserved_bytes), landedBytes: Number(row.landed_bytes),
    createdAt: String(row.created_at), expiresAt: String(row.expires_at), updatedAt: String(row.updated_at),
  }
}

function partPlanFrom(value: unknown): ObjectRow['partPlan'] {
  if (typeof value !== 'string' || !value) return []
  try {
    const parsed = JSON.parse(value) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.flatMap((part) => {
      if (!part || typeof part !== 'object') return []
      const row = part as { number?: unknown; offset?: unknown; length?: unknown }
      if (typeof row.number !== 'number' || typeof row.offset !== 'number' || typeof row.length !== 'number') return []
      return [{ number: row.number, offset: row.offset, length: row.length }]
    })
  } catch {
    return []
  }
}

function objectFrom(row: Record<string, unknown>): ObjectRow {
  return {
    objectId: String(row.object_id), caseId: String(row.case_id), role: String(row.role), r2Key: String(row.r2_key),
    declaredBytes: Number(row.declared_bytes), actualBytes: row.actual_bytes == null ? null : Number(row.actual_bytes),
    sha256: String(row.sha256), uploadId: row.upload_id == null ? null : String(row.upload_id),
    partPlan: partPlanFrom(row.part_plan),
    state: row.state as ObjectRow['state'], createdAt: String(row.created_at), updatedAt: String(row.updated_at),
  }
}
