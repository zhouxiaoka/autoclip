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
  partPlan: { number: number; offset: number; length: number }[]
  state: 'reserved' | 'complete' | 'aborted'
  createdAt: string
  updatedAt: string
}

export interface CaseRow {
  caseId: string
  idempotencyKey: string
  manifestSha256: string
  state: 'open' | 'complete' | 'failed' | 'deleted'
  capabilitySha256: string
  consentVersion: string
  manifestBytes: number
  reservedBytes: number
  landedBytes: number
  createdAt: string
  expiresAt: string
  updatedAt: string
}

export interface Repo {
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
  reconcile(): QuotaState | Promise<QuotaState>
}

export class MemoryRepo {
  quota: QuotaState = { landed: 0, reserved: 0 }
  cases = new Map<string, CaseRow>()
  objects = new Map<string, ObjectRow>()
  rates = new Map<string, number>()
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
    return Promise.resolve([...this.cases.values()].find((row) => row.idempotencyKey === key) ?? null)
  }

  getCase(id: string): Promise<CaseRow | null> {
    return Promise.resolve(this.cases.get(id) ?? null)
  }

  saveCase(row: CaseRow): Promise<void> {
    this.cases.set(row.caseId, row)
    return Promise.resolve()
  }

  getObject(id: string): Promise<ObjectRow | null> {
    return Promise.resolve(this.objects.get(id) ?? null)
  }

  saveObject(row: ObjectRow): Promise<void> {
    this.objects.set(row.objectId, row)
    return Promise.resolve()
  }

  objectsFor(caseId: string): Promise<ObjectRow[]> {
    return Promise.resolve([...this.objects.values()].filter((row) => row.caseId === caseId))
  }

  allCases(): Promise<CaseRow[]> {
    return Promise.resolve([...this.cases.values()])
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
