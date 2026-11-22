import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { D1Repo } from '../src/d1.ts'
import { sweep } from '../src/app.ts'
import { SqliteD1, fixture, ready, secret, key } from './sql-fixture.ts'

test('D1 completion rolls back object, case and quota together at every write boundary', async () => {
  for (const boundary of [0, 1, 2]) {
    const f = await ready()
    const before = await f.repo.snapshot()
    let step = 0
    f.db.beforeStatement = () => { if (step++ === boundary) throw new Error('temporary SQL failure') }
    assert.equal((await f.complete()).status, 503)
    assert.deepEqual(await f.repo.snapshot(), before)
    assert.equal((await f.repo.getObject(f.object.objectId))?.state, 'reserved')
    assert.equal((await f.repo.getCase(f.created.case_id))?.state, 'open')
    assert.equal(f.objects.get(f.object.r2Key)?.byteLength, 6)
    f.db.beforeStatement = () => {}
    // A fresh Worker/repository uses the same durable database, not an in-memory retry flag.
    f.deps.repo = new D1Repo(f.db as any, () => '2026-11-17T00:00:00Z')
    assert.equal((await f.complete()).status, 200)
    assert.equal((await f.complete()).status, 200)
    assert.deepEqual(await f.repo.snapshot(), { reserved: 0, landed: before.landed + 6 })
    assert.equal((await f.repo.getCase(f.created.case_id))?.state, 'complete')
  }
})

test('a D1 outage after writing the object cannot leave an already-complete half commit', async () => {
  const f = await ready()
  let down = false
  f.db.beforeStatement = () => { if (down) throw new Error('database unavailable') }
  f.db.afterStatement = (sql) => { if (sql.startsWith('UPDATE objects SET actual_bytes')) down = true }
  assert.equal((await f.complete()).status, 503)
  down = false
  f.db.afterStatement = () => {}
  f.deps.repo = new D1Repo(f.db as any, () => '2026-11-17T00:00:00Z')
  assert.equal((await f.complete()).status, 200)
  assert.equal((await f.repo.getCase(f.created.case_id))?.state, 'complete')
  assert.equal((await f.repo.snapshot()).reserved, 0)
})

test('delete between completion verification and its transaction wins', async () => {
  const f = await ready()
  f.db.beforeBatch = async () => {
    f.db.beforeBatch = async () => {}
    assert.equal((await f.remove()).status, 200)
  }
  assert.equal((await f.complete()).status, 404)
  assert.equal((await f.repo.getCase(f.created.case_id))?.state, 'deleted')
  assert.equal(f.objects.has(f.object.r2Key), false)
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
})

test('delete after committed completion cannot be overwritten by a stale case snapshot', async () => {
  const f = await ready()
  const stale = (await f.repo.getCase(f.created.case_id))!
  f.db.afterBatch = async () => {
    f.db.afterBatch = async () => {}
    assert.equal((await f.remove()).status, 200)
  }
  await f.complete()
  stale.state = 'complete'
  await f.repo.saveCase(stale)
  assert.equal((await f.repo.getCase(stale.caseId))?.state, 'deleted')
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
})

test('delete with an R2 error remains fenced and its restarted retry clears all accounting', async () => {
  const f = await ready()
  const remove = f.bucket.delete.bind(f.bucket)
  f.bucket.delete = async () => { throw new Error('storage unavailable') }
  await assert.rejects(f.remove(), /storage unavailable/)
  assert.equal((await f.repo.getCase(f.created.case_id))?.state, 'deleting')
  assert.equal((await f.complete()).status, 404)
  f.bucket.delete = remove
  f.deps.repo = new D1Repo(f.db as any, () => '2026-11-17T00:00:00Z')
  await sweep(f.deps)
  assert.equal((await f.repo.getCase(f.created.case_id))?.state, 'deleted')
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
})

test('lost create response can be cancelled by the durable credential, with no replay or extra bytes', async () => {
  const f = fixture()
  assert.equal((await f.create()).status, 201) // discard the entire response
  const puts = f.bucket.puts
  assert.equal((await f.cancel()).status, 200)
  assert.equal(f.bucket.puts, puts)
  assert.equal(f.objects.size, 0)
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
  assert.equal((await f.cancel()).status, 200)
  assert.equal((await f.create()).status, 404)
})

test('cancel before create leaves a durable tombstone rather than creating diagnostic data', async () => {
  const f = fixture()
  assert.equal((await f.cancel()).status, 200)
  f.deps.repo = new D1Repo(f.db as any, () => '2026-11-17T00:00:00Z')
  assert.equal((await f.create()).status, 410)
  assert.equal(f.bucket.puts, 0)
  assert.equal(await f.repo.findByIdempotency(key), null)
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
})

test('cancellation during creation cannot be overwritten by its late commit', async () => {
  const f = fixture()
  const put = f.bucket.put.bind(f.bucket)
  f.bucket.put = async (key, bytes) => { await put(key, bytes); assert.equal((await f.cancel()).status, 200) }
  assert.notEqual((await f.create()).status, 201)
  assert.equal((await f.repo.findByIdempotency(key))?.state, 'deleted')
  assert.equal(f.objects.size, 0)
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
})

test('wrong recovery credentials cannot cancel or refresh an existing case', async () => {
  const f = await ready()
  assert.equal((await f.cancel('b'.repeat(43))).status, 403)
  assert.equal((await f.call('/v1/cases', 'POST', { ...f.createBody, recovery_token: 'b'.repeat(43) })).status, 403)
  assert.equal((await f.repo.getCase(f.created.case_id))?.state, 'open')
})

test('refresh renews the same object grant without rotating a credential whose response can be lost', async () => {
  const f = fixture()
  const first = await (await f.create()).json() as any
  f.advance()
  const refresh = await (await f.create()).json() as any
  assert.equal(refresh.case_id, first.case_id)
  assert.equal(refresh.capability, first.capability)
  assert.equal(refresh.capability, secret)
  assert.equal(refresh.uploads[0].object_id, first.uploads[0].object_id)
  assert.notEqual(refresh.uploads[0].url, first.uploads[0].url)
  assert.ok(Date.parse(refresh.upload_expires_at) > Date.parse(first.upload_expires_at))
  const before = await f.repo.snapshot()
  await f.create() // another lost refresh response
  assert.deepEqual(await f.repo.snapshot(), before)
  assert.equal((await f.call(`/v1/cases/${first.case_id}`, 'DELETE', undefined, first.capability)).status, 200)
})

test('creation reservation and cancellation stay atomic under a failed database transaction', async () => {
  const f = fixture()
  let step = 0
  f.db.beforeStatement = (sql) => { if (sql.startsWith('INSERT INTO cases') && step++ === 0) throw new Error('insert failed') }
  await assert.rejects(f.create(), /insert failed/)
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
  assert.equal(await f.repo.findByIdempotency(key), null)
  assert.equal(f.bucket.puts, 0)
})

test('a fully staged create resumes after its final database transaction failed', async () => {
  const f = fixture()
  let fail = true
  f.db.beforeStatement = (sql) => {
    if (fail && sql.startsWith('UPDATE cases SET reserved_bytes = reserved_bytes - manifest_bytes')) {
      fail = false
      throw new Error('creation commit unavailable')
    }
  }
  await assert.rejects(f.create(), /creation commit unavailable/)
  assert.equal((await f.repo.findByIdempotency(key))?.state, 'creating')
  const puts = f.bucket.puts
  const replay = await f.create()
  assert.equal(replay.status, 200)
  assert.equal(f.bucket.puts, puts)
  assert.equal((await f.repo.findByIdempotency(key))?.state, 'open')
  assert.equal((await f.repo.snapshot()).reserved, 6)
})

test('concurrent duplicate completion charges the object exactly once', async () => {
  const f = await ready()
  const before = await f.repo.snapshot()
  const results = await Promise.all([f.complete(), f.complete(), f.complete()])
  assert.deepEqual(results.map((response) => response.status), [200, 200, 200])
  assert.deepEqual(await f.repo.snapshot(), { landed: before.landed + 6, reserved: 0 })
})

test('unknown cancellation is bounded and malformed requests do not create tombstones', async () => {
  const f = fixture()
  assert.equal((await f.call('/v1/cases/cancel', 'POST', null)).status, 422)
  for (let i = 0; i < f.deps.limits.ratePerHour; i++) assert.equal((await f.cancel()).status, 200)
  assert.equal((await f.cancel()).status, 429)
  assert.equal(f.objects.size, 0)
})

test('recovery migration repairs old half commits without losing identities or capabilities', async () => {
  const db = new SqliteD1(1)
  db.db.exec(`INSERT INTO cases VALUES ('old-case', 'old-key', 'manifest-hash', 'open', 'capability-hash', 'v1', 100, 6, 100, 'start', 'expiry', 'updated');
    INSERT INTO objects VALUES ('old-object', 'old-case', 'original', 'cases/old-case/original', 6, 6, 'digest', NULL, '[]', 'complete', 'start', 'updated');
    UPDATE quota SET landed_bytes = 100, reserved_bytes = 0 WHERE id = 1;`)
  db.db.exec(readFileSync(new URL('../migrations/0002_recovery.sql', import.meta.url), 'utf8'))
  const repo = new D1Repo(db as any, () => 'now')
  const row = (await repo.getCase('old-case'))!
  assert.equal(row.capabilitySha256, 'capability-hash')
  assert.equal(row.idempotencyKey, 'old-key')
  assert.equal(row.expiresAt, 'expiry')
  assert.equal(row.state, 'complete')
  assert.equal((await repo.getObject('old-object'))?.r2Key, 'cases/old-case/original')
  assert.deepEqual(await repo.snapshot(), { landed: 106, reserved: 0 })
})

test('a transient create storage failure can retry without turning its key into a user cancellation', async () => {
  const f = fixture()
  const put = f.bucket.put.bind(f.bucket)
  let first = true
  f.bucket.put = async (key, bytes) => {
    if (first) { first = false; throw new Error('temporary write outage') }
    await put(key, bytes)
  }
  assert.equal((await f.create()).status, 500)
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
  assert.equal((await f.create()).status, 201)
  assert.equal((await f.repo.findByIdempotency(key))?.state, 'open')
})

test('cancellation during failed-create cleanup cannot be forgotten by the retry reset', async () => {
  const f = fixture()
  f.bucket.put = async () => { throw new Error('write outage') }
  const remove = f.bucket.delete.bind(f.bucket)
  let first = true
  f.bucket.delete = async (key) => {
    if (first) { first = false; assert.equal((await f.cancel()).status, 200) }
    await remove(key)
  }
  assert.equal((await f.create()).status, 500)
  assert.equal((await f.create()).status, 404)
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
})


test('the rate window stops at the limit instead of counting past it', async () => {
  const db = new SqliteD1()
  const repo = new D1Repo(db as any, () => '2026-11-17T00:00:00Z')
  for (let index = 0; index < 20; index += 1) assert.equal(await repo.hit('hour', 20), true)
  assert.equal(await repo.hit('hour', 20), false)
  const row = await db.prepare('SELECT hits FROM rate_windows WHERE bucket = ?1').bind('hour').first<{ hits: number }>()
  assert.equal(row?.hits, 20)
})

test('zeroing changes() between statements still commits each predicate once', async () => {
  const f = await ready()
  const before = await f.repo.snapshot()
  f.db.clearChangesBetween = true
  assert.equal((await f.complete()).status, 200)
  assert.deepEqual(await f.repo.snapshot(), { landed: before.landed + 6, reserved: 0 })
  assert.equal((await f.complete()).status, 200)
  assert.deepEqual(await f.repo.snapshot(), { landed: before.landed + 6, reserved: 0 })
  assert.equal(readFileSync(new URL('../src/d1.ts', import.meta.url), 'utf8').includes('changes()'), false)
})

test('a manifest write arriving after cancellation is removed by the creating request', async () => {
  const f = fixture()
  const put = f.bucket.put.bind(f.bucket)
  f.bucket.put = async (name, bytes) => {
    assert.equal((await f.cancel()).status, 200)
    await put(name, bytes) // the in-flight R2 write becomes visible after delete completed
  }
  assert.notEqual((await f.create()).status, 201)
  assert.equal((await f.repo.findByIdempotency(key))?.state, 'deleted')
  assert.equal(f.objects.size, 0)
  assert.deepEqual(await f.repo.snapshot(), { landed: 0, reserved: 0 })
})
