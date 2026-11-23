import assert from 'node:assert/strict'
import test from 'node:test'
import { sweep } from '../src/app.ts'
import { fixture } from './sql-fixture.ts'

function explainDetails(db: ReturnType<typeof fixture>['db'], sql: string): string[] {
  const rows = db.db.prepare(`EXPLAIN QUERY PLAN ${sql}`).all() as { detail: string }[]
  return rows.map((row) => String(row.detail))
}

function seedBulkCases(f: ReturnType<typeof fixture>, activeCount: number, deletedCount: number) {
  const now = '2026-11-17T00:00:00.000Z'
  const future = '2026-12-01T00:00:00.000Z'
  const past = '2026-11-01T00:00:00.000Z'
  const insertCase = f.db.db.prepare(
    `INSERT INTO cases (case_id, idempotency_key, manifest_sha256, state, capability_sha256, consent_version, manifest_bytes, reserved_bytes, landed_bytes, created_at, expires_at, updated_at, recovery_sha256)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  )
  const insertObject = f.db.db.prepare(
    `INSERT INTO objects (object_id, case_id, role, r2_key, declared_bytes, actual_bytes, sha256, upload_id, part_plan, state, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, NULL, '[]', ?, ?, ?)`,
  )
  for (let i = 0; i < activeCount; i += 1) {
    const id = `active-${i}`
    const key = `cases/${id}/excerpt`
    insertCase.run(id, `idem-a-${i}`, 'mhash', 'complete', 'cap', 'v1', 100, 0, 150, now, future, now, '')
    insertObject.run(`obj-a-${i}-live`, id, 'excerpt', key, 50, 50, 'shash', 'complete', now, now)
    insertObject.run(`obj-a-${i}-aborted`, id, 'subtitle', `cases/${id}/subtitle`, 20, null, 'shash', 'aborted', now, now)
    f.objects.set(`cases/${id}/manifest.json`, new Uint8Array(100))
    f.objects.set(key, new Uint8Array(50))
  }
  for (let i = 0; i < deletedCount; i += 1) {
    const id = `deleted-${i}`
    insertCase.run(id, `idem-d-${i}`, 'mhash', 'deleted', 'cap', 'v1', 100, 0, 0, past, past, past, '')
    insertObject.run(`obj-d-${i}-0`, id, 'excerpt', `cases/${id}/excerpt`, 50, null, 'shash', 'aborted', past, past)
    insertObject.run(`obj-d-${i}-1`, id, 'original', `cases/${id}/original`, 50, null, 'shash', 'aborted', past, past)
  }
  f.db.db.prepare(`UPDATE quota SET landed_bytes = ?, reserved_bytes = 0, updated_at = ? WHERE id = 1`).run(activeCount * 150, now)
}

test('hot-path object lookups use case_id index instead of full table scans', () => {
  const f = fixture()
  seedBulkCases(f, 50, 50)
  const queries = [
    `SELECT * FROM objects WHERE case_id = 'active-1'`,
    `SELECT 1 FROM objects WHERE case_id = 'active-1' AND state = 'reserved'`,
    `SELECT COALESCE(SUM(actual_bytes), 0) FROM objects WHERE case_id = 'active-1' AND state = 'complete'`,
    `UPDATE objects SET state = 'aborted', updated_at = 'now' WHERE case_id = 'active-1'`,
    `DELETE FROM objects WHERE case_id = 'active-1'`,
  ]
  for (const sql of queries) {
    const details = explainDetails(f.db, sql)
    assert.ok(
      details.some((line) => /SEARCH objects USING (COVERING )?INDEX/.test(line)),
      `expected indexed search on objects for "${sql}", got: ${details.join(' | ')}`,
    )
    assert.ok(
      details.every((line) => !/^SCAN objects\b/.test(line)),
      `unexpected full table scan on objects for "${sql}": ${details.join(' | ')}`,
    )
  }
})

test('sweep avoids N+1 object queries and unindexed full table scans on D1', async () => {
  const f = fixture()
  seedBulkCases(f, 60, 60)

  // Add one expired case, one incomplete open case, and one orphan R2 key.
  f.db.db.prepare(
    `INSERT INTO cases (case_id, idempotency_key, manifest_sha256, state, capability_sha256, consent_version, manifest_bytes, reserved_bytes, landed_bytes, created_at, expires_at, updated_at, recovery_sha256)
     VALUES ('expired-1', 'idem-exp', 'mhash', 'complete', 'cap', 'v1', 100, 0, 150, '2026-11-01T00:00:00.000Z', '2026-11-16T00:00:00.000Z', '2026-11-01T00:00:00.000Z', '')`,
  ).run()
  f.db.db.prepare(
    `INSERT INTO objects (object_id, case_id, role, r2_key, declared_bytes, actual_bytes, sha256, upload_id, part_plan, state, created_at, updated_at)
     VALUES ('obj-exp', 'expired-1', 'excerpt', 'cases/expired-1/excerpt', 50, 50, 'shash', NULL, '[]', 'complete', '2026-11-01T00:00:00.000Z', '2026-11-01T00:00:00.000Z')`,
  ).run()
  f.objects.set('cases/expired-1/manifest.json', new Uint8Array(100))
  f.objects.set('cases/expired-1/excerpt', new Uint8Array(50))

  f.db.db.prepare(
    `INSERT INTO cases (case_id, idempotency_key, manifest_sha256, state, capability_sha256, consent_version, manifest_bytes, reserved_bytes, landed_bytes, created_at, expires_at, updated_at, recovery_sha256)
     VALUES ('stale-open', 'idem-open', 'mhash', 'open', 'cap', 'v1', 100, 50, 100, '2026-11-15T00:00:00.000Z', '2026-12-01T00:00:00.000Z', '2026-11-15T00:00:00.000Z', '')`,
  ).run()
  f.db.db.prepare(
    `INSERT INTO objects (object_id, case_id, role, r2_key, declared_bytes, actual_bytes, sha256, upload_id, part_plan, state, created_at, updated_at)
     VALUES ('obj-open', 'stale-open', 'excerpt', 'cases/stale-open/excerpt', 50, NULL, 'shash', NULL, '[]', 'reserved', '2026-11-15T00:00:00.000Z', '2026-11-15T00:00:00.000Z')`,
  ).run()
  f.objects.set('cases/stale-open/manifest.json', new Uint8Array(100))
  f.objects.set('cases/orphan-1/excerpt', new Uint8Array(10))

  const first = await sweep(f.deps)
  assert.equal(first.expired, 1)
  assert.equal(first.aborted, 1)
  assert.deepEqual(first.orphans, ['cases/orphan-1/excerpt'])
  assert.equal(f.objects.has('cases/orphan-1/excerpt'), false)
  assert.equal(f.objects.has('cases/expired-1/excerpt'), false)
  assert.equal(f.objects.has('cases/active-0/manifest.json'), true)
  assert.equal(f.objects.has('cases/active-0/excerpt'), true)
  assert.deepEqual(await f.repo.snapshot(), { landed: 60 * 150, reserved: 0 })

  // Steady-state sweep with 60 active cases + 62 deleted cases must stay O(1) in query count
  // and must never perform an unindexed full table scan on cases or objects.
  const executed: string[] = []
  const origPrepare = f.db.prepare.bind(f.db)
  f.db.prepare = (sql: string) => {
    executed.push(sql)
    return origPrepare(sql)
  }

  const second = await sweep(f.deps)
  assert.deepEqual(second, { aborted: 0, expired: 0, orphans: [] })
  assert.ok(
    executed.length <= 5,
    `expected O(1) statements during steady-state sweep for 60 active cases, got ${executed.length}`,
  )
  for (const sql of executed) {
    const details = explainDetails(f.db, sql)
    for (const line of details) {
      assert.ok(!/^SCAN (cases|objects|c|o)\b(?! USING (COVERING )?INDEX)/.test(line),
        `unindexed full table scan in sweep SQL "${sql}": ${details.join(' | ')}`)
    }
  }
})

test('D1 sweep preserves a case created while bucket listing is in flight and skips live-key query when empty', async () => {
  const f = fixture()
  seedBulkCases(f, 5, 5)

  // 1) Empty bucket listing skips live-key scan altogether.
  const origList = f.bucket.list.bind(f.bucket)
  f.bucket.list = async () => []
  const emptyQueries: string[] = []
  const origPrepare = f.db.prepare.bind(f.db)
  f.db.prepare = (sql: string) => {
    emptyQueries.push(sql)
    return origPrepare(sql)
  }
  const emptyResult = await sweep(f.deps)
  assert.deepEqual(emptyResult, { aborted: 0, expired: 0, orphans: [] })
  assert.ok(emptyQueries.every((sql) => !/FROM objects\b/i.test(sql)),
    `expected empty listing sweep to skip objects query, ran: ${emptyQueries.join(' ; ')}`)

  // 2) Concurrent creation during bucket.list is still seen as live on D1.
  f.db.prepare = origPrepare
  let manifestKey = ''
  f.bucket.list = async (prefix) => {
    const created = await f.create()
    assert.equal(created.status, 201)
    const body = await created.json() as { case_id: string }
    manifestKey = `cases/${body.case_id}/manifest.json`
    return origList(prefix)
  }
  const concurrent = await sweep(f.deps)
  assert.ok(f.objects.has(manifestKey))
  assert.ok(!concurrent.orphans.includes(manifestKey))
})
