const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')
const React = require('react')

function dialogs() {
  const document = { activeElement: null, body: {}, querySelector: () => null, querySelectorAll: () => live }
  const live = []; const listeners = []; const cleanups = []
  let current
  const focus = label => ({ label, isConnected: true, getClientRects: () => [1], focus() { document.activeElement = this } })
  const hookReact = { useId: () => 'dialog-title', useRef: init => ({ current: init === null ? current : init }), useEffect: fn => { cleanups.push(fn()) } }
  const mod = loadTs('../../ui/index.tsx', {
    react: { default: hookReact }, 'react-dom': { createPortal: node => node }, antd: { ConfigProvider: 'ConfigProvider' }, './ac.css': {},
    __globals: { document, window: { addEventListener: (_key, fn) => listeners.push(fn), removeEventListener: (_key, fn) => { const index = listeners.indexOf(fn); if (index >= 0) listeners.splice(index, 1) } } },
  })
  const open = name => {
    const controls = [focus(name + '-first'), focus(name + '-last')]
    current = { controls, querySelectorAll: () => controls, contains: node => controls.includes(node), focus() { document.activeElement = this } }
    live.push(current); const root = current; const closed = []
    const tree = mod.Dialog({ open: true, onClose: () => closed.push(name), title: name, className: name === 'advanced' ? 'ac-request-dialog' : undefined, children: React.createElement('button', {}, name) })
    return { root, controls, closed, tree }
  }
  const key = (value, shiftKey = false) => {
    const e = { key: value, shiftKey, prevented: false, preventDefault() { this.prevented = true } }
    for (const listener of [...listeners]) listener(e)
    return e
  }
  return { open, key, document, live, cleanups, focus }
}

test('nested advanced dialog owns Escape and Tab without closing or refocusing its parent', () => {
  const x = dialogs(); const parent = x.open('parent'); const child = x.open('advanced')
  assert.equal(child.tree.props.children.props.children.props.className, 'ac-dialog ac-request-dialog')
  x.document.activeElement = child.controls[1]
  assert.equal(x.key('Tab').prevented, true)
  assert.equal(x.document.activeElement, child.controls[0])
  x.key('Escape')
  assert.deepEqual(parent.closed, [])
  assert.deepEqual(child.closed, ['advanced'])
  x.live.pop(); x.cleanups.pop()()
  assert.equal(x.document.activeElement, parent.controls[0])
  x.key('Escape')
  assert.deepEqual(parent.closed, ['parent'])
})

test('single-dialog focus trap and select-menu Escape remain unchanged', () => {
  const x = dialogs(); const current = x.open('single')
  x.document.activeElement = current.controls[0]
  assert.equal(x.key('Tab', true).prevented, true)
  assert.equal(x.document.activeElement, current.controls[1])
  x.document.querySelector = () => ({})
  x.key('Escape'); assert.deepEqual(current.closed, [])
  x.document.querySelector = () => null
  x.key('Escape'); assert.deepEqual(current.closed, ['single'])
})
