'use strict'
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('../vm-sandbox.cjs')

const root = path.join(__dirname, '../../../backend/assets/templates')

function element() {
  const node = { innerHTML: '', textContent: '', className: '', style: {}, children: [] }
  node.appendChild = child => { node.children.push(child) }
  return node
}

function load(template) {
  const elements = new Map()
  const document = {
    getElementById: id => {
      if (!elements.has(id)) elements.set(id, element())
      return elements.get(id)
    },
    createElement: () => element(),
  }
  const sandbox = { window: {}, document, console }
  sandbox.window = sandbox
  runInSandbox(fs.readFileSync(path.join(root, template, 'template.js'), 'utf8'), sandbox, { filename: template + '.js' })
  return sandbox
}

function captionsAtWords(template, fill) {
  const page = load(template)
  page.setData(fill)
  return (fill.words || []).map((word, index) => {
    const t = ((word.start_frame + word.end_frame) / 2) / fill.fps
    page.renderFrame(t)
    return { index, t, html: page.document.getElementById('zh').innerHTML }
  })
}

module.exports = { captionsAtWords }

if (require.main === module) {
  const template = process.argv[2]
  const fill = JSON.parse(fs.readFileSync(0, 'utf8'))
  process.stdout.write(JSON.stringify(captionsAtWords(template, fill)))
}
