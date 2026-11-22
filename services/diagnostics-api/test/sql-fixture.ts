/** Execute production D1 SQL against SQLite, including real atomic rollback. No cloud calls. */
import { DatabaseSync } from 'node:sqlite'
import { readFileSync, readdirSync } from 'node:fs'
import { D1Repo } from '../src/d1.ts'
import { handle, type Deps } from '../src/app.ts'
import { PROPOSED_LIMITS } from '../src/quota.ts'

export class SqliteD1 {
  db = new DatabaseSync(':memory:')
  beforeStatement: (sql: string) => void = () => {}
  afterStatement: (sql: string) => void = () => {}
  clearChangesBetween = false
  beforeBatch: () => Promise<void> = async () => {}
  afterBatch: () => Promise<void> = async () => {}
  constructor(migrationCount = Infinity) {
    const migrations = new URL('../migrations/', import.meta.url)
    for (const name of readdirSync(migrations).filter((file) => file.endsWith('.sql')).sort().slice(0, migrationCount)) {
      this.db.exec(readFileSync(new URL(name, migrations), 'utf8'))
    }
  }
  prepare(sql: string) {
    const owner = this
    let values: unknown[] = []
    const params = () => Object.fromEntries(values.map((value, index) => [String(index + 1), value]))
    const execute = () => {
      owner.beforeStatement(sql)
      const result = owner.db.prepare(sql).run(params())
      owner.afterStatement(sql)
      return { meta: { changes: Number(result.changes) } }
    }
    return {
      bind(...args: unknown[]) { values = args; return this },
      async first() { return owner.db.prepare(sql).get(params()) ?? null },
      async all() { return { results: owner.db.prepare(sql).all(params()) } },
      async run() { return execute() },
      execute,
    }
  }
  async batch(statements: ReturnType<SqliteD1['prepare']>[]) {
    await this.beforeBatch()
    this.db.exec('BEGIN IMMEDIATE')
    let results
    try {
      results = statements.map((statement) => {
        const result = statement.execute()
        if (this.clearChangesBetween) this.db.prepare('UPDATE quota SET landed_bytes = landed_bytes WHERE 0').run()
        return result
      })
      this.db.exec('COMMIT')
    } catch (error) {
      this.db.exec('ROLLBACK')
      throw error
    }
    await this.afterBatch()
    return results
  }
}

export const key = 'ab'.repeat(32)
export const secret = 'synthetic_recovery_secret_'.padEnd(43, 'a')
export const manifest = {
  schema: 'autoclip.support_manifest/1', purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
  consent_text_version: '2026-11-16.1', runtime: { app_version: '1.5.9', os: 'linux', arch: 'x86_64', runtime: 'python' },
  attempt: { attempt_id: `t-${'a'.repeat(32)}`, state: 'failed', error_code: 'timeout', failure_stage: 'analyze', sequence: 1 },
  run: { provider: 'deepseek', duration_ms: 10 }, media_facts: {}, log_lines: [], limits: { approval: 'pending' },
}

export function fixture() {
  const db = new SqliteD1()
  const repo = new D1Repo(db as any, () => '2026-11-17T00:00:00Z')
  const objects = new Map<string, Uint8Array>()
  const bucket = {
    puts: 0,
    async put(key: string, bytes: Uint8Array) { this.puts++; objects.set(key, bytes) },
    async head(key: string) { const bytes = objects.get(key); return bytes ? { size: bytes.byteLength } : null },
    async delete(key: string) { objects.delete(key) },
    async list(prefix: string) { return [...objects.keys()].filter((key) => key.startsWith(prefix)) },
    async createMultipartUpload() { throw new Error('unexpected multipart in SQL fixture') },
    resumeMultipartUpload() { throw new Error('unexpected multipart in SQL fixture') },
  }
  let clock = new Date('2026-11-17T00:00:00Z')
  let signs = 0
  const deps: Deps = {
    repo, bucket, now: () => clock, limits: { ...PROPOSED_LIMITS }, adminToken: 'synthetic-admin',
    bucketName: 'autoclip-diagnostics', partBytes: 8 * 1024 * 1024,
    signer: { async sign(input) { signs++; return { url: `https://fixture.invalid/${signs}`, headers: { 'content-length': String(input.contentLength) } } } },
  }
  const createBody = { purpose: 'troubleshooting_and_product_improvement', not_for_training: true, recovery_token: secret,
    manifest, files: [{ role: 'original', bytes: 6, sha256: 'cd'.repeat(32) }] }
  const call = (path: string, method: string, body?: unknown, capability = '') => handle(new Request(`https://diagnostics.invalid${path}`, {
    method, headers: { 'content-type': 'application/json', 'idempotency-key': key, authorization: `Bearer ${capability}` },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  }), deps)
  return { db, repo, bucket, objects, deps, call, createBody,
    advance() { clock = new Date(clock.getTime() + 16 * 60 * 1000) },
    create: () => call('/v1/cases', 'POST', createBody),
    cancel: (credential = secret) => call('/v1/cases/cancel', 'POST', { idempotency_key: key, recovery_token: credential }),
  }
}

export async function ready() {
  const f = fixture()
  const response = await f.create()
  if (response.status !== 201) throw new Error(`create status ${response.status}: ${await response.text()}`)
  const created = await response.json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const object = (await f.repo.objectsFor(created.case_id))[0]!
  await f.bucket.put(object.r2Key, new TextEncoder().encode('abcdef'))
  return { ...f, created, object,
    complete: () => f.call(`/v1/cases/${created.case_id}/files/${object.objectId}/complete`, 'POST', {}, created.capability),
    remove: () => f.call(`/v1/cases/${created.case_id}`, 'DELETE', undefined, created.capability),
  }
}
