import assert from 'node:assert/strict'
import test from 'node:test'
import { manifestProblems } from '../src/validate.ts'

function manifest(extra: Record<string, unknown> = {}) {
  return {
    schema: 'autoclip.support_manifest/1',
    purpose: 'troubleshooting_and_product_improvement',
    not_for_training: true,
    consent_text_version: '2026-11-18.1',
    runtime: { app_version: '1.5.9', os: 'linux', arch: 'x86_64', runtime: 'python' },
    attempt: { attempt_id: `t-${'a'.repeat(32)}`, state: 'failed', error_code: 'timeout', failure_stage: 'analyze', sequence: 1 },
    run: { provider: 'deepseek', duration_ms: 10 },
    media_facts: {},
    log_lines: [],
    limits: { approval: 'pending' },
    ...extra,
  }
}

test('a sanitized public video link is accepted and a secret query is not', () => {
  const clean = manifest({ source_link: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLpublic' })
  assert.deepEqual(manifestProblems(clean, 262144), [])
  const keptId = manifest({ source_link: 'https://www.youtube.com/watch?v=abc' })
  assert.deepEqual(manifestProblems(keptId, 262144), [])
  const dirty = [
    'https://user:pass@www.youtube.com/watch?v=dQw4w9WgXcQ&token=abc#frag',
    'https://www.youtube.com/watch?v=abc&api-key=1',
    'https://www.youtube.com/watch?v=abc&x-api-key=1',
    'https://www.youtube.com/watch?v=abc&x-auth=1',
    'https://www.youtube.com/watch?v=abc&sign=1',
    'https://www.youtube.com/watch?v=abc&%2574oken=1',
    'https://cdn.example/watch/%2FUsers%2Falice?v=abc',
    'https://www.youtube.com/watch?v=abc&next=%2FUsers%2Falice',
    'https://cdn.example/sk-live/watch?v=abc',
    'https://www.youtube.com/watch?v=abc&note=sk-live',
    'file:///tmp/private.mp4',
    'https://www.youtube.com:99999/watch?v=abc',
  ]
  for (const source_link of dirty) {
    assert.ok(manifestProblems(manifest({ source_link }), 262144).includes('source_link'), source_link)
  }
})
