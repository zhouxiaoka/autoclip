// RL: exercise the real settings transitions, without a browser or provider traffic.
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')
const mocks = { '../../i18n': { t: text => text } }
const logic = loadTs('modelSettingsLogic.ts', mocks)
const defaults = loadTs('modelDefaults.ts', mocks)
const catalog = loadTs('providerCatalogView.ts', mocks)
const slots = loadTs('defaultModelSlots.ts', mocks)
const plain = value => JSON.parse(JSON.stringify(value))

function transition(document, entry, action) {
  let state = logic.prepareLoaded(document)
  const connection = state.connections.find(row => row.id === 'new')
  const models = [{ id: 'new-analysis', capability: 'text', analysis: true }, { id: 'new-cover', image: true }]
  const lists = { new: { models, source: 'live', preview: false } }
  if (action === 'switch') {
    state = entry === 'legacy'
      ? logic.chooseProvider(state, 'analysis', connection.provider, lists, false).settings
      : entry === 'catalog' ? catalog.assignAnalysis(state, connection)
        : entry === 'smart' ? slots.applySmartSelection(state, 'analysis', 'new-analysis', 'new')
          : slots.applyFixedSelection(state, 'analysis', 'new-analysis', 'new')
    state = defaults.applyModelDefaults(state, connection, models, false)
  } else if (action === 'off' || action === 'on') {
    state = logic.setVisual(state, action === 'on')
    state = logic.setCoverEnabled(state, action === 'on', lists)
  }
  return plain(logic.forSave(state))
}

module.exports = { transition }

if (require.main === module) {
  const { test } = require('node:test')
  for (const entry of ['legacy', 'catalog', 'smart', 'fixed']) {
    for (const source of ['preset', 'user']) {
      for (const bindingId of ['old', 'independent']) {
        test(`RL purpose providers survive ${entry}/${source}/${bindingId}, toggles and reopen`, () => {
          const connection = (id, provider) => ({ id, name: id, provider, base_url: '', api_key: '', has_key: true })
          let state = {
            version: 1, saved: true,
            connections: [connection('old', 'openai'), connection('new', 'lmstudio'), connection('independent', 'dashscope')],
            analysis: { connection_id: 'old', model: 'old-analysis', capability: 'text', model_source: source },
            vision: { connection_id: bindingId, model: 'own-vision', capability: 'multimodal', model_source: source },
            cover: { connection_id: bindingId, model: 'own-cover', capability: 'auto', model_source: source },
            transcription: { provider: 'cloud', connection_id: bindingId, model: bindingId === 'old' ? 'whisper-1' : 'qwen-audio-3.0-asr-flash', model_source: source },
            cover_enabled: true, cover_follows_analysis: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
          }
          const original = plain(state)
          for (const action of ['switch', 'off', 'on', 'reopen']) {
            state = transition(plain(state), entry, action)
            assert.equal(state.analysis.connection_id, 'new')
            for (const role of ['vision', 'cover', 'transcription']) {
              assert.deepEqual(state[role], original[role], `${role} binding after ${action}`)
              const before = original.connections.find(row => row.id === original[role].connection_id)
              const after = state.connections.find(row => row.id === state[role].connection_id)
              assert.equal(after.provider, before.provider)
            }
            assert.equal(state.cover_enabled, action !== 'off')
            assert.equal(state.allow_visual_screening, action !== 'off')
          }
        })
      }
    }
  }
}
