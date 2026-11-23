import type { CaseRow, CommitResult, ObjectRow, OpenResult } from './memory.ts'
import { tryReserve, type Limits, type QuotaState } from './quota.ts'

interface Result { meta?: { changes?: number }; results?: Record<string, unknown>[] }
export interface Prepared {
  bind(...values: unknown[]): Prepared
  first<T>(): Promise<T | null>
  run(): Promise<Result>
  all<T>(): Promise<{ results: T[] }>
}

export interface D1 {
  prepare(sql: string): Prepared
  batch(statements: Prepared[]): Promise<Result[]>
}

/** Durable quota. reserve() uses the same predicate as tryReserve and a conditional UPDATE. */
export class D1Repo {
  private readonly db: D1
  private readonly now: () => string
  constructor(db: D1, now: () => string) { this.db = db; this.now = now }

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
    const result = await this.db.prepare(
      `INSERT INTO rate_windows (bucket, window_start, hits) VALUES (?1, '', 1)
       ON CONFLICT (bucket, window_start) DO UPDATE SET hits = hits + 1 WHERE hits < ?2`,
    ).bind(bucket, limit).run()
    return (result.meta?.changes ?? 0) === 1
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
       ON CONFLICT (case_id) DO UPDATE SET state = ?4, capability_sha256 = ?5, reserved_bytes = ?8, landed_bytes = ?9, updated_at = ?12 WHERE cases.state NOT IN ('deleted', 'deleting', 'creation_cleanup')`,
    ).bind(row.caseId, row.idempotencyKey, row.manifestSha256, row.state, row.capabilitySha256, row.consentVersion, row.manifestBytes, row.reservedBytes, row.landedBytes, row.createdAt, row.expiresAt, row.updatedAt).run()
  }

  async getObject(id: string): Promise<ObjectRow | null> {
    const row = await this.db.prepare(`SELECT * FROM objects WHERE object_id = ?1`).bind(id).first<Record<string, unknown>>()
    return row ? objectFrom(row) : null
  }

  async saveObject(row: ObjectRow): Promise<void> {
    await this.db.prepare(
      `INSERT INTO objects (object_id, case_id, role, r2_key, declared_bytes, actual_bytes, sha256, upload_id, part_plan, state, created_at, updated_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, CASE WHEN EXISTS (SELECT 1 FROM cases WHERE case_id = ?2 AND state IN ('deleting', 'deleted')) THEN 'aborted' ELSE ?10 END, ?11, ?12)
       ON CONFLICT (object_id) DO UPDATE SET actual_bytes = CASE WHEN objects.state IN ('complete', 'aborted') THEN objects.actual_bytes ELSE ?6 END, state = CASE WHEN objects.state IN ('complete', 'aborted') THEN objects.state ELSE ?10 END, upload_id = COALESCE(?8, objects.upload_id), updated_at = ?12`,
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

  async activeCases(): Promise<CaseRow[]> {
    const rows = await this.db.prepare(`SELECT * FROM cases WHERE state != 'deleted'`).bind().all<Record<string, unknown>>()
    return rows.results.map(caseFrom)
  }

  async liveKeys(): Promise<Set<string>> {
    const rows = await this.db.prepare(
      `SELECT 'cases/' || case_id || '/manifest.json' AS r2_key FROM cases WHERE state != 'deleted'
       UNION ALL
       SELECT o.r2_key FROM objects o JOIN cases c ON c.case_id = o.case_id WHERE c.state != 'deleted' AND o.state != 'aborted'`,
    ).bind().all<{ r2_key: string }>()
    return new Set(rows.results.map((row) => String(row.r2_key)))
  }

  private guardRejected(error: unknown): boolean {
    return error instanceof Error && /CHECK constraint failed/i.test(error.message)
  }

  private accountingGuard(name: string, okSql: string, binds: unknown[]) {
    return this.db.prepare(`INSERT INTO write_guard (name, ok) VALUES (?1, (${okSql}))
      ON CONFLICT(name) DO UPDATE SET ok = excluded.ok`).bind(name, ...binds)
  }

  /** Each write names the row state it requires. A broken unit fails write_guard and aborts the batch. */
  async commitFile(caseId: string, objectId: string, actualBytes: number, now: string): Promise<CommitResult> {
    let results: { meta?: { changes?: number } }[]
    try {
      results = await this.db.batch([
      this.db.prepare(`UPDATE objects SET actual_bytes = ?1, state = 'complete', updated_at = ?2
        WHERE object_id = ?3 AND case_id = ?4 AND state = 'reserved' AND declared_bytes = ?1
        AND EXISTS (SELECT 1 FROM cases WHERE case_id = ?4 AND state IN ('open', 'complete', 'failed'))`
      ).bind(actualBytes, now, objectId, caseId),
      this.db.prepare(`UPDATE quota SET reserved_bytes = reserved_bytes - ?1, landed_bytes = landed_bytes + ?1, updated_at = ?2
        WHERE id = 1 AND EXISTS (
          SELECT 1 FROM objects o JOIN cases c ON c.case_id = o.case_id
          WHERE o.object_id = ?3 AND o.case_id = ?4 AND o.state = 'complete' AND o.actual_bytes = ?1 AND c.reserved_bytes >= ?1)`
      ).bind(actualBytes, now, objectId, caseId),
      this.db.prepare(`UPDATE cases SET reserved_bytes = reserved_bytes - ?1, landed_bytes = landed_bytes + ?1,
        state = CASE WHEN state = 'failed' THEN 'failed'
          WHEN EXISTS (SELECT 1 FROM objects WHERE case_id = ?3 AND state = 'reserved') THEN 'open' ELSE 'complete' END,
        updated_at = ?2
        WHERE case_id = ?3 AND reserved_bytes >= ?1 AND EXISTS (
          SELECT 1 FROM objects WHERE object_id = ?4 AND case_id = ?3 AND state = 'complete' AND actual_bytes = ?1)`
      ).bind(actualBytes, now, caseId, objectId),
      this.accountingGuard('commit', `CASE WHEN (
          SELECT landed_bytes FROM cases WHERE case_id = ?2
        ) = (
          SELECT manifest_bytes FROM cases WHERE case_id = ?2
        ) + (
          SELECT COALESCE(SUM(actual_bytes), 0) FROM objects WHERE case_id = ?2 AND state = 'complete'
        ) THEN 1 ELSE 0 END`, [caseId]),
    ])
    } catch (error) {
      if (!this.guardRejected(error)) throw error
      return { committed: false, reason: 'gone' }
    }
    if ((results[0]?.meta?.changes ?? 0) === 1 && (results[1]?.meta?.changes ?? 0) === 1 && (results[2]?.meta?.changes ?? 0) === 1) return { committed: true }
    const object = await this.getObject(objectId), row = await this.getCase(caseId)
    if (object?.caseId === caseId && object.state === 'complete' && object.actualBytes === actualBytes && row &&
        ['open', 'complete', 'failed'].includes(row.state)) return { committed: false, already: true }
    return { committed: false, reason: 'gone' }
  }

  async openCase(row: CaseRow, limits: Pick<Limits, 'landedCap' | 'inflightCap'>): Promise<OpenResult> {
    try {
      const result = await this.db.batch([
        this.db.prepare(`UPDATE quota SET reserved_bytes = reserved_bytes + ?1, updated_at = ?2
          WHERE id = 1 AND landed_bytes + reserved_bytes + ?1 <= ?3 AND reserved_bytes + ?1 <= ?4
          AND NOT EXISTS (SELECT 1 FROM cases WHERE idempotency_key = ?5)
          AND NOT EXISTS (SELECT 1 FROM creation_cancellations WHERE idempotency_key = ?5 AND recovery_sha256 = ?6)`
        ).bind(row.reservedBytes, row.caseId, limits.landedCap, limits.inflightCap, row.idempotencyKey, row.recoverySha256 || ''),
        this.db.prepare(`INSERT INTO cases (case_id, idempotency_key, manifest_sha256, state, capability_sha256,
          consent_version, manifest_bytes, reserved_bytes, landed_bytes, created_at, expires_at, updated_at, recovery_sha256)
          SELECT ?1, ?2, ?3, 'creating', ?4, ?5, ?6, ?7, 0, ?8, ?9, ?8, ?10
          WHERE EXISTS (SELECT 1 FROM quota WHERE id = 1 AND updated_at = ?1)`
        ).bind(row.caseId, row.idempotencyKey, row.manifestSha256, row.capabilitySha256, row.consentVersion,
          row.manifestBytes, row.reservedBytes, row.createdAt, row.expiresAt, row.recoverySha256 || ''),
        this.accountingGuard('open', `CASE
          WHEN EXISTS (SELECT 1 FROM cases WHERE case_id = ?2) THEN 1
          WHEN NOT EXISTS (SELECT 1 FROM quota WHERE id = 1 AND updated_at = ?2) THEN 1
          ELSE 0 END`, [row.caseId]),
      ])
      if ((result[0]?.meta?.changes ?? 0) === 1 && (result[1]?.meta?.changes ?? 0) === 1) return { ok: true }
    } catch (error) {
      if (!this.guardRejected(error)) throw error
    }
    const cancelled = await this.db.prepare(`SELECT 1 FROM creation_cancellations WHERE idempotency_key = ?1 AND recovery_sha256 = ?2`
    ).bind(row.idempotencyKey, row.recoverySha256 || '').first()
    if (cancelled) return { ok: false, reason: 'cancelled' }
    if (await this.findByIdempotency(row.idempotencyKey)) return { ok: false, reason: 'existing' }
    const decision = tryReserve(await this.snapshot(), row.reservedBytes, limits)
    return decision.ok ? { ok: false, reason: 'retry' } : decision
  }

  async finishCreation(caseId: string, now: string): Promise<boolean> {
    const results = await this.db.batch([
      this.db.prepare(`UPDATE quota SET reserved_bytes = reserved_bytes - (SELECT manifest_bytes FROM cases WHERE case_id = ?1 AND state = 'creating'),
        landed_bytes = landed_bytes + (SELECT manifest_bytes FROM cases WHERE case_id = ?1 AND state = 'creating'), updated_at = ?2
        WHERE id = 1 AND EXISTS (SELECT 1 FROM cases WHERE case_id = ?1 AND state = 'creating')`).bind(caseId, now),
      this.db.prepare(`UPDATE cases SET reserved_bytes = reserved_bytes - manifest_bytes, landed_bytes = manifest_bytes,
        state = CASE WHEN reserved_bytes > manifest_bytes THEN 'open' ELSE 'complete' END, updated_at = ?2
        WHERE case_id = ?1 AND state = 'creating'`).bind(caseId, now),
      this.accountingGuard('finish', `CASE WHEN NOT EXISTS (
        SELECT 1 FROM cases WHERE case_id = ?2 AND state = 'creating') THEN 1 ELSE 0 END`, [caseId]),
    ])
    return (results[0]?.meta?.changes ?? 0) === 1 && (results[1]?.meta?.changes ?? 0) === 1
  }

  async cancelCreation(key: string, recoveryHash: string, now: string): Promise<void> {
    await this.db.batch([
      this.db.prepare(`INSERT INTO creation_cancellations (idempotency_key, recovery_sha256, created_at)
        VALUES (?1, ?2, ?3) ON CONFLICT DO NOTHING`).bind(key, recoveryHash, now),
      this.db.prepare(`UPDATE cases SET state = 'deleting', updated_at = ?3
        WHERE idempotency_key = ?1 AND recovery_sha256 = ?2 AND state != 'deleted'`).bind(key, recoveryHash, now),
    ])
  }

  async beginDelete(caseId: string, now: string): Promise<CaseRow | null> {
    await this.db.prepare(`UPDATE cases SET state = 'deleting', updated_at = ?2 WHERE case_id = ?1 AND state != 'deleted'`).bind(caseId, now).run()
    return this.getCase(caseId)
  }

  async beginCreationCleanup(caseId: string, now: string): Promise<boolean> {
    const result = await this.db.prepare(`UPDATE cases SET state = 'creation_cleanup', updated_at = ?2
      WHERE case_id = ?1 AND state IN ('creating', 'creation_cleanup')`).bind(caseId, now).run()
    return result.meta?.changes === 1
  }

  async forgetFailedCreation(caseId: string): Promise<void> {
    await this.db.batch([
      this.db.prepare(`DELETE FROM objects WHERE case_id = ?1 AND EXISTS (SELECT 1 FROM cases
        WHERE case_id = ?1 AND state = 'failed' AND reserved_bytes = 0 AND landed_bytes = 0
        AND NOT EXISTS (SELECT 1 FROM creation_cancellations WHERE idempotency_key = cases.idempotency_key AND recovery_sha256 = cases.recovery_sha256))`).bind(caseId),
      this.db.prepare(`DELETE FROM cases WHERE case_id = ?1 AND state = 'failed' AND reserved_bytes = 0 AND landed_bytes = 0
        AND NOT EXISTS (SELECT 1 FROM creation_cancellations WHERE idempotency_key = cases.idempotency_key AND recovery_sha256 = cases.recovery_sha256)`).bind(caseId),
    ])
  }

  async finishDelete(caseId: string, now: string, creationFailure = false): Promise<void> {
    await this.db.batch([
      this.db.prepare(`UPDATE quota SET
        reserved_bytes = MAX(0, reserved_bytes - (SELECT reserved_bytes FROM cases WHERE case_id = ?1)),
        landed_bytes = MAX(0, landed_bytes - (SELECT landed_bytes FROM cases WHERE case_id = ?1)), updated_at = ?2
        WHERE id = 1 AND EXISTS (SELECT 1 FROM cases WHERE case_id = ?1 AND state = ?3)`).bind(caseId, now, creationFailure ? 'creation_cleanup' : 'deleting'),
      this.db.prepare(`UPDATE objects SET state = 'aborted', updated_at = ?2 WHERE case_id = ?1
        AND EXISTS (SELECT 1 FROM cases WHERE case_id = ?1 AND state = ?3)`).bind(caseId, now, creationFailure ? 'creation_cleanup' : 'deleting'),
      this.db.prepare(`UPDATE cases SET state = ?4, reserved_bytes = 0, landed_bytes = 0,
        updated_at = ?2 WHERE case_id = ?1 AND state = ?3`).bind(caseId, now, creationFailure ? 'creation_cleanup' : 'deleting', creationFailure ? 'failed' : 'deleted'),
      this.accountingGuard('delete', `CASE WHEN NOT EXISTS (
        SELECT 1 FROM cases WHERE case_id = ?2 AND state = ?3) THEN 1 ELSE 0 END`, [caseId, creationFailure ? 'creation_cleanup' : 'deleting']),
    ])
  }

  async rotateCapability(caseId: string, hash: string, now: string): Promise<boolean> {
    const result = await this.db.prepare(`UPDATE cases SET capability_sha256 = ?2, updated_at = ?3
      WHERE case_id = ?1 AND state IN ('open', 'complete')`).bind(caseId, hash, now).run()
    return result.meta?.changes === 1
  }

  async failFile(caseId: string, objectId: string, now: string): Promise<void> {
    await this.db.batch([
      this.db.prepare(`UPDATE quota SET reserved_bytes = reserved_bytes - (SELECT declared_bytes FROM objects WHERE object_id = ?2 AND state = 'reserved'),
        updated_at = ?3 WHERE id = 1 AND EXISTS (SELECT 1 FROM objects JOIN cases USING (case_id)
        WHERE object_id = ?2 AND case_id = ?1 AND objects.state = 'reserved' AND cases.state IN ('open', 'failed'))`
      ).bind(caseId, objectId, now),
      this.db.prepare(`UPDATE cases SET reserved_bytes = reserved_bytes - (SELECT declared_bytes FROM objects WHERE object_id = ?2 AND state = 'reserved'),
        state = 'failed', updated_at = ?3 WHERE case_id = ?1 AND EXISTS (
          SELECT 1 FROM objects WHERE object_id = ?2 AND case_id = ?1 AND state = 'reserved')`).bind(caseId, objectId, now),
      this.db.prepare(`UPDATE objects SET state = 'aborted', updated_at = ?2 WHERE object_id = ?1 AND state = 'reserved'`).bind(objectId, now),
      this.accountingGuard('fail', `CASE WHEN NOT EXISTS (
        SELECT 1 FROM objects WHERE object_id = ?2 AND state = 'reserved') THEN 1 ELSE 0 END`, [objectId]),
    ])
  }

  async reconcile(): Promise<QuotaState> {
    await this.db.prepare(`UPDATE quota SET
      landed_bytes = agg.landed,
      reserved_bytes = agg.reserved,
      updated_at = ?1
      FROM (
        SELECT COALESCE(SUM(landed_bytes), 0) AS landed,
               COALESCE(SUM(reserved_bytes), 0) AS reserved
        FROM cases WHERE state != 'deleted'
      ) AS agg
      WHERE quota.id = 1`
    ).bind(this.now()).run()
    return this.snapshot()
  }
}

function caseFrom(row: Record<string, unknown>): CaseRow {
  return {
    caseId: String(row.case_id), idempotencyKey: String(row.idempotency_key), manifestSha256: String(row.manifest_sha256),
    state: row.state as CaseRow['state'], capabilitySha256: String(row.capability_sha256), consentVersion: String(row.consent_version),
    recoverySha256: String(row.recovery_sha256 || ''),
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
      const row = part as { number?: unknown; offset?: unknown; length?: unknown; contentMd5?: unknown }
      if (typeof row.number !== 'number' || typeof row.offset !== 'number' || typeof row.length !== 'number') return []
      const contentMd5 = typeof row.contentMd5 === 'string' && /^[A-Za-z0-9+/]{22}==$/.test(row.contentMd5) ? row.contentMd5 : undefined
      return [{ number: row.number, offset: row.offset, length: row.length, contentMd5 }]
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
