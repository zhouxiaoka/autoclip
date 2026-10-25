// F1/F2: exercise the real TypeScript errorText (not a mirror).
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const { errorText } = loadTs(path.join(__dirname, '../src/features/studio/errorText.ts'))
const fail = data => ({ message: 'Request failed with status code 422', response: { data } })

test('string detail wins', () => {
  assert.equal(errorText(fail({ detail: '请到「设置 → 服务商与模型」改密钥', error: { message: '通用' } })), '请到「设置 → 服务商与模型」改密钥')
})

test('validation array: the specific field hint beats the generic envelope (F2)', () => {
  const data = {
    detail: [{ field: 'body.connections.0.base_url', message: '请填写不含密钥或查询参数的 HTTP(S) 接口地址' }],
    error: { code: 'VALIDATION_ERROR', message: '请求参数验证失败' },
  }
  assert.equal(errorText(fail(data)), '请填写不含密钥或查询参数的 HTTP(S) 接口地址')
  assert.equal(errorText(fail({ detail: [{ msg: 'FastAPI 原生 msg' }] })), 'FastAPI 原生 msg')
})

test('envelope only, then axios message fallback', () => {
  assert.equal(errorText(fail({ error: { message: '连接未通过校验' } })), '连接未通过校验')
  assert.equal(errorText(fail({})), 'Request failed with status code 422')
  assert.equal(errorText(null), '请求失败，请重试')
})
