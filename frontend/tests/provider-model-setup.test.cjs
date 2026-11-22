const test = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')
const { recommendProviderSetup } = loadTs('providerModelSetup.ts')
const connection = { id: 'one', provider: 'openai' }
const base = { connections: [connection], analysis: null, vision: null, transcription: null, cover: null, cover_enabled: false, allow_send_frame: false }
const list = { source: 'live', models: [
  { id: 'text', analysis: true, capability: 'text' },
  { id: 'vision', analysis: true, capability: 'multimodal' },
  { id: 'whisper-1', asr: true, asr_supported: true },
  { id: 'gpt-image-1', image: true },
] }
test('one account supplies all four purposes including model-designed covers by default', () => {
  const next = recommendProviderSetup(base, connection, list)
  for (const slot of ['analysis','vision','transcription','cover']) assert.equal(next[slot].connection_id, 'one', slot)
  assert.equal(next.vision.model, 'vision')
  assert.equal(next.transcription.model, 'whisper-1')
  assert.equal(next.cover_enabled, true)
  assert.equal(next.allow_send_frame, false)
})
test('text-only provider keeps existing speech and cover, never selects unsupported or hidden models', () => {
  const conn = { ...connection, enabled_model_ids: ['text','asr-preview','unadapted'] }
  const current = { ...base, cover: { connection_id: 'prior', model: 'keep' }, transcription: { provider: 'whisper_local', model: 'base' } }
  const next = recommendProviderSetup(current, conn, { source: 'live', models: [...list.models, { id: 'asr-preview', asr: true, asr_preview: true, asr_supported: true }, { id: 'unadapted', asr: true }] })
  assert.equal(next.analysis.model, 'text')
  assert.equal(next.vision, null)
  assert.equal(next.transcription, current.transcription)
  assert.equal(next.cover, current.cover)
})
test('catalog previews and accounts without a usable model never produce a misleading setup', () => {
  assert.equal(recommendProviderSetup(base, connection, { ...list, source: 'catalog', preview: true }), null)
  assert.equal(recommendProviderSetup(base, connection, { source: 'live', models: [{ id: 'video', kind: 'video', analysis: false }] }), null)
})
test('replacing the key removes retired routes on that account while preserving the choice to use local covers', () => {
  const previous = recommendProviderSetup(base, connection, list)
  const next = recommendProviderSetup(previous, connection, { source: 'live', models: [list.models[0]] })
  assert.equal(next.analysis.model, 'text')
  assert.equal(next.vision, null)
  assert.equal(next.cover, null)
  assert.equal(next.transcription.provider, 'whisper_local')
})
test('switching accounts cannot convert a following cover into a hidden independent route', () => {
  for (const follow of [true, false]) {
    const previous = { ...base, analysis: { connection_id: 'old', model: 'old-chat', model_source: 'preset' },
      cover_enabled: true, cover_follows_analysis: follow, cover: { connection_id: 'old', model: 'existing-cover', model_source: 'preset' } }
    const next = recommendProviderSetup(previous, connection, { source: 'live', models: [list.models[0]] })
    assert.equal(next.cover, follow ? null : previous.cover)
    assert.equal(next.cover_enabled, !follow)
    assert.equal(next.cover_follows_analysis, false)
  }
})

test('a saved local-only choice survives one-key setup even when an image model is available', () => {
  const next = recommendProviderSetup({ ...base, prefer_local_cover: true }, connection, list)
  assert.equal(next.cover.model, 'gpt-image-1')
  assert.equal(next.cover_enabled, false)
  assert.equal(next.allow_send_frame, false)
})

test('one-key keeps manually assigned purposes and the chosen account, even when another account advertises the same model', () => {
  const manual = { connection_id: 'old', model: 'vision', model_source: 'user' }
  const speech = { provider: 'whisper_local', model: 'base', model_source: 'user' }
  const before = { ...base, analysis: manual, transcription: speech, cover: { ...manual, model: 'art' }, cover_enabled: true, cover_follows_analysis: false }
  const next = recommendProviderSetup(before, connection, list)
  assert.equal(next.analysis, before.analysis)
  assert.equal(next.transcription, speech)
  assert.equal(next.cover, before.cover)
  assert.equal(next.cover_follows_analysis, false)
  assert.equal(next.vision.connection_id, connection.id)
  const same = recommendProviderSetup({ ...base, analysis: { ...manual, connection_id: connection.id } }, connection, list)
  assert.equal(same.analysis.model_source, 'user')
})
