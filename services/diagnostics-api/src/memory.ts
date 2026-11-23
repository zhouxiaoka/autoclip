import { tryReserve, type Limits, type QuotaState } from './quota.ts'

export interface ObjectRow {
  objectId: string
  caseId: string
  role: string
  r2Key: string
  declaredBytes: number
  actualBytes: number | null
  sha256: string
  uploadId: string | null
  partPlan: { number: number; offset: number; length: number; contentMd5?: string }[]
  state: 'reserved' | 'complete' | 'aborted'
  createdAt: string
  updatedAt: string
}

export interface CaseRow {
  caseId: string
  idempotencyKey: string
  manifestSha256: string
  state: 'creating' | 'creation_cleanup' | 'open' | 'complete' | 'failed' | 'deleting' | 'deleted'
  capabilitySha256: string
  recoverySha256?: string
  consentVersion: string
  manifestBytes: number
  reservedBytes: number
  landedBytes: number
  createdAt: string
  expiresAt: string
  updatedAt: string
}

export type OpenResult = { ok: true } | { ok: false; reason: string }

export interface Repo {
  openCase(row: CaseRow, limits: Pick<Limits, 'landedCap' | 'inflightCap'>): Promise<OpenResult>
  finishCreation(caseId: string, now: string): Promise<boolean>
  cancelCreation(key: string, recoveryHash: string, now: string): Promise<void>
  beginDelete(caseId: string, now: string): Promise<CaseRow | null>
  beginCreationCleanup(caseId: string, now: string): Promise<boolean>
  forgetFailedCreation(caseId: string): Promise<void>
  finishDelete(caseId: string, now: string, creationFailure?: boolean): Promise<void>
  rotateCapability(caseId: string, hash: string, now: string): Promise<boolean>
  failFile(caseId: string, objectId: string, now: string): Promise<void>
  reserve(bytes: number, limits: Pick<Limits, 'landedCap' | 'inflightCap'>): Promise<{ ok: true } | { ok: false; reason: string }>
  release(bytes: number): Promise<void>
  land(bytes: number): Promise<void>
  unland(bytes: number): Promise<void>
  snapshot(): QuotaState | Promise<QuotaState>
  hit(bucket: string, limit: number): Promise<boolean>
  findByIdempotency(key: string): Promise<CaseRow | null>
  getCase(id: string): Promise<CaseRow | null>
  saveCase(row: CaseRow): Promise<void>
  getObject(id: string): Promise<ObjectRow | null>
  saveObject(row: ObjectRow): Promise<void>
  objectsFor(caseId: string): Promise<ObjectRow[]>
  allCases(): Promise<CaseRow[]>
  activeCases(): Promise<CaseRow[]>
  liveKeys(): Promise<Set<string>>
  reconcile(): QuotaState | Promise<QuotaState>
  commitFile(caseId: string, objectId: string, actualBytes: number, now: string): Promise<CommitResult>
}

export type CommitResult =
  | { committed: true }
  | { committed: false; already: true }
  | { committed: false; reason: 'gone' }

export class MemoryRepo {
  quota: QuotaState = { landed: 0, reserved: 0 }
  cases = new Map<string, CaseRow>()
  objects = new Map<string, ObjectRow>()
  rates = new Map<string, number>()
  cancellations = new Set<string>()
  private chain: Promise<void> = Promise.resolve()

  private exclusive<T>(fn: () => T): Promise<T> {
    const run = this.chain.then(fn)
    this.chain = run.then(() => undefined, () => undefined)
    return run
  }

  reserve(bytes: number, limits: Pick<Limits, 'landedCap' | 'inflightCap'>): Promise<{ ok: true } | { ok: false; reason: string }> {
    return this.exclusive(() => {
      const decision = tryReserve(this.quota, bytes, limits)
      if (!decision.ok) return decision
      this.quota = { landed: this.quota.landed, reserved: this.quota.reserved + bytes }
      return { ok: true as const }
    })
  }

  release(bytes: number): Promise<void> {
    return this.exclusive(() => {
      this.quota = { ...this.quota, reserved: Math.max(0, this.quota.reserved - bytes) }
    })
  }

  land(bytes: number): Promise<void> {
    return this.exclusive(() => {
      this.quota = {
        reserved: Math.max(0, this.quota.reserved - bytes),
        landed: this.quota.landed + bytes,
      }
    })
  }

  unland(bytes: number): Promise<void> {
    return this.exclusive(() => {
      this.quota = { ...this.quota, landed: Math.max(0, this.quota.landed - bytes) }
    })
  }

  snapshot(): QuotaState {
    return { ...this.quota }
  }

  hit(bucket: string, limit: number): Promise<boolean> {
    const hits = (this.rates.get(bucket) ?? 0) + 1
    this.rates.set(bucket, hits)
    return Promise.resolve(hits <= limit)
  }

  findByIdempotency(key: string): Promise<CaseRow | null> {
    return Promise.resolve(structuredClone([...this.cases.values()].find((row) => row.idempotencyKey === key) ?? null))
  }

  getCase(id: string): Promise<CaseRow | null> {
    return Promise.resolve(structuredClone(this.cases.get(id) ?? null))
  }

  saveCase(row: CaseRow): Promise<void> {
    const existing = this.cases.get(row.caseId)
    if (!existing || !['deleting', 'deleted', 'creation_cleanup'].includes(existing.state)) this.cases.set(row.caseId, structuredClone(row))
    return Promise.resolve()
  }

  getObject(id: string): Promise<ObjectRow | null> {
    return Promise.resolve(structuredClone(this.objects.get(id) ?? null))
  }

  saveObject(row: ObjectRow): Promise<void> {
    const existing = this.objects.get(row.objectId)
    const state = this.cases.get(row.caseId)?.state
    this.objects.set(row.objectId, { ...structuredClone(row),
      actualBytes: existing?.state === 'complete' ? existing.actualBytes : row.actualBytes,
      state: existing?.state === 'aborted' || state === 'deleting' || state === 'deleted' ? 'aborted' : existing?.state === 'complete' ? 'complete' : row.state })
    return Promise.resolve()
  }

  openCase(row: CaseRow, limits: Pick<Limits, 'landedCap' | 'inflightCap'>): Promise<OpenResult> {
    return this.exclusive(() => {
      if (this.cancellations.has(`${row.idempotencyKey}:${row.recoverySha256 || ''}`)) return { ok: false, reason: 'cancelled' }
      if ([...this.cases.values()].some((item) => item.idempotencyKey === row.idempotencyKey)) return { ok: false, reason: 'existing' }
      const decision = tryReserve(this.quota, row.reservedBytes, limits)
      if (!decision.ok) return decision
      this.quota.reserved += row.reservedBytes
      this.cases.set(row.caseId, structuredClone(row))
      return { ok: true }
    })
  }

  finishCreation(caseId: string, now: string): Promise<boolean> {
    return this.exclusive(() => {
      const row = this.cases.get(caseId)
      if (!row || row.state !== 'creating') return false
      row.reservedBytes -= row.manifestBytes
      row.landedBytes += row.manifestBytes
      this.quota.reserved -= row.manifestBytes
      this.quota.landed += row.manifestBytes
      row.state = row.reservedBytes ? 'open' : 'complete'
      row.updatedAt = now
      return true
    })
  }

  cancelCreation(key: string, recoveryHash: string, now: string): Promise<void> {
    return this.exclusive(() => {
      this.cancellations.add(`${key}:${recoveryHash}`)
      const row = [...this.cases.values()].find((item) => item.idempotencyKey === key && item.recoverySha256 === recoveryHash)
      if (row && row.state !== 'deleted') { row.state = 'deleting'; row.updatedAt = now }
    })
  }

  beginDelete(caseId: string, now: string): Promise<CaseRow | null> {
    return this.exclusive(() => {
      const row = this.cases.get(caseId)
      if (row && row.state !== 'deleted') { row.state = 'deleting'; row.updatedAt = now }
      return structuredClone(row ?? null)
    })
  }

  beginCreationCleanup(caseId: string, now: string): Promise<boolean> {
    return this.exclusive(() => {
      const row = this.cases.get(caseId)
      if (!row || !['creating', 'creation_cleanup'].includes(row.state)) return false
      row.state = 'creation_cleanup'; row.updatedAt = now
      return true
    })
  }

  forgetFailedCreation(caseId: string): Promise<void> {
    return this.exclusive(() => {
      const row = this.cases.get(caseId)
      if (!row || row.state !== 'failed' || row.reservedBytes || row.landedBytes ||
          this.cancellations.has(`${row.idempotencyKey}:${row.recoverySha256 || ''}`)) return
      for (const object of this.objects.values()) if (object.caseId === caseId) this.objects.delete(object.objectId)
      this.cases.delete(caseId)
    })
  }

  finishDelete(caseId: string, now: string, creationFailure = false): Promise<void> {
    return this.exclusive(() => {
      const row = this.cases.get(caseId)
      if (!row || row.state !== (creationFailure ? 'creation_cleanup' : 'deleting')) return
      this.quota.reserved = Math.max(0, this.quota.reserved - row.reservedBytes)
      this.quota.landed = Math.max(0, this.quota.landed - row.landedBytes)
      for (const object of this.objects.values()) if (object.caseId === caseId) { object.state = 'aborted'; object.updatedAt = now }
      row.reservedBytes = row.landedBytes = 0
      row.state = creationFailure ? 'failed' : 'deleted'
      row.updatedAt = now
    })
  }

  rotateCapability(caseId: string, hash: string, now: string): Promise<boolean> {
    return this.exclusive(() => {
      const row = this.cases.get(caseId)
      if (!row || !['open', 'complete'].includes(row.state)) return false
      row.capabilitySha256 = hash
      row.updatedAt = now
      return true
    })
  }

  failFile(caseId: string, objectId: string, now: string): Promise<void> {
    return this.exclusive(() => {
      const object = this.objects.get(objectId), row = this.cases.get(caseId)
      if (!row || !object || object.caseId !== caseId || object.state !== 'reserved' || !['open', 'failed'].includes(row.state)) return
      object.state = 'aborted'; object.updatedAt = now
      row.reservedBytes -= object.declaredBytes
      this.quota.reserved -= object.declaredBytes
      row.state = 'failed'; row.updatedAt = now
    })
  }

  commitFile(caseId: string, objectId: string, actualBytes: number, now: string): Promise<CommitResult> {
    return this.exclusive(() => {
      const object = this.objects.get(objectId)
      const row = this.cases.get(caseId)
      if (!object || object.caseId !== caseId || !row || !['open', 'complete', 'failed'].includes(row.state)) return { committed: false, reason: 'gone' }
      if (object.state === 'complete') return { committed: false, already: true }
      if (object.state !== 'reserved') return { committed: false, reason: 'gone' }
      object.state = 'complete'
      object.actualBytes = actualBytes
      object.updatedAt = now
      this.quota = {
        reserved: Math.max(0, this.quota.reserved - object.declaredBytes),
        landed: this.quota.landed + object.declaredBytes,
      }
      row.reservedBytes = Math.max(0, row.reservedBytes - object.declaredBytes)
      row.landedBytes += object.declaredBytes
      const pending = [...this.objects.values()].some((item) => item.caseId === caseId && item.state === 'reserved')
      if (!pending && row.state !== 'failed') row.state = 'complete'
      row.updatedAt = now
      return { committed: true }
    })
  }

  objectsFor(caseId: string): Promise<ObjectRow[]> {
    return Promise.resolve(structuredClone([...this.objects.values()].filter((row) => row.caseId === caseId)))
  }

  allCases(): Promise<CaseRow[]> {
    return Promise.resolve(structuredClone([...this.cases.values()]))
  }

  activeCases(): Promise<CaseRow[]> {
    return Promise.resolve(structuredClone([...this.cases.values()].filter((row) => row.state !== 'deleted')))
  }

  liveKeys(): Promise<Set<string>> {
    const live = new Set<string>()
    const activeIds = new Set<string>()
    for (const row of this.cases.values()) {
      if (row.state === 'deleted') continue
      activeIds.add(row.caseId)
      live.add(`cases/${row.caseId}/manifest.json`)
    }
    for (const object of this.objects.values()) {
      if (object.state !== 'aborted' && activeIds.has(object.caseId)) live.add(object.r2Key)
    }
    return Promise.resolve(live)
  }

  reconcile(): QuotaState {
    let landed = 0
    let reserved = 0
    for (const row of this.cases.values()) {
      if (row.state === 'deleted') continue
      landed += row.landedBytes
      reserved += row.reservedBytes
    }
    this.quota = { landed, reserved }
    return this.snapshot()
  }
}
