const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

test('AUTOCLIP-FRONTEND-R: ModelSettingsLeaveGuard tolerates stale router blocker after async save', async () => {
  let proceeds = 0
  let resets = 0
  const blocker = {
    state: 'blocked',
    proceed() {
      proceeds += 1
      throw new Error('invariant: cannot proceed unblocked router')
    },
    reset() {
      resets += 1
      throw new Error('invariant: cannot reset unblocked router')
    },
  }
  const Guard = loadTs('ModelSettingsLeaveGuard.tsx', {
    react: {
      ...React,
      useRef: value => ({ current: value }),
      useEffect: () => {},
    },
    'react-router-dom': { useBlocker: () => blocker },
    '../../i18n': { t: text => text },
    '../../ui': {
      Btn: 'button',
      Dialog: 'div',
    },
  }).default

  const tree = Guard({
    dirty: { current: true },
    saving: false,
    onSave: async () => true,
  })
  const flatten = node => !React.isValidElement(node)
    ? [node]
    : [node, ...React.Children.toArray(node.props?.children).flatMap(flatten), ...React.Children.toArray(node.props?.footer).flatMap(flatten)]
  const buttons = flatten(tree).filter(n => n?.type === 'button')
  const saveBtn = buttons.find(b => b.props.children === '保存并离开')
  assert.ok(saveBtn)
  // Must not reject even when router blocker throws invariant after async onSave().
  saveBtn.props.onClick()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(proceeds, 1)

  const stayBtn = buttons.find(b => b.props.children === '继续编辑')
  stayBtn.props.onClick()
  assert.equal(resets, 1)
})

test('AUTOCLIP-FRONTEND-E: EditingStylePicker ignores AbortError/NotAllowedError and does not spam Sentry', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/features/studio/EditingStylePicker.tsx'), 'utf8')
  assert.equal(src.includes('captureStudioException'), false)
  assert.match(src, /AbortError/)
  assert.match(src, /NotAllowedError/)
})

test('Gemini AQ. keys are recognized by hintProviderForKey alongside AIza keys', () => {
  const access = loadTs('providerAccess.ts', {
    '../../i18n': { t: text => text },
    './providers': loadTs('providers.ts', { '../../i18n': { t: text => text } }),
  })
  assert.equal(access.hintProviderForKey('AQ.Ab8RN6test123'), 'gemini')
  assert.equal(access.hintProviderForKey('AIzaSyTest123'), 'gemini')
})

test('Live Replay OBS and channel replay files carry source_type and replay_source into studio telemetry', () => {
  const workflow = loadTs(path.join(__dirname, '../src/analytics/workflow.ts'))
  const studio = loadTs(path.join(__dirname, '../src/analytics/studio.ts'), {
    './flags': { flagAssigned: () => false },
    './posthog': { captureBusinessEvent() {} },
    './observer': { workflow: { generation: () => 1, active: () => true, list: () => [], context: () => ({}) } },
    './workflow': workflow,
  }, path.join(__dirname, '../src/analytics'))

  const makeForm = entries => ({
    get: key => entries[key] ?? null,
    entries: () => Object.entries(entries),
  })

  const obsProps = workflow.safeStudioProperties(studio.studioImportProperties(makeForm({
    obs_capture_id: 'cap-1',
    replay_source: 'obs',
    goal: 'auto',
  })))
  assert.equal(obsProps.source_type, 'obs')
  assert.equal(obsProps.material_origin, 'obs')
  assert.equal(obsProps.replay_source, 'obs')

  const kickProps = workflow.safeStudioProperties(studio.studioImportProperties(makeForm({
    replay_source: 'kick_file',
    goal: 'auto',
  })))
  assert.equal(kickProps.source_type, 'file')
  assert.equal(kickProps.material_origin, 'user')
  assert.equal(kickProps.replay_source, 'kick_file')
})
