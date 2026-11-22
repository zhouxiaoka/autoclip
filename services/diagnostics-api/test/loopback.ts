/** Local HTTP fixture: real API + D1 SQL, with a deliberately failing object-storage grant. */
import { createServer } from 'node:http'
import { fixture } from './sql-fixture.ts'
import { handle } from '../src/app.ts'

const f = fixture()
f.deps.now = () => new Date()
const scenario = process.argv[2]
const requests: Record<string, number> = {}
const grants = new Map<string, { key: string; size: number }>()
let base = ''
let generation = 0
let dropped = false
f.deps.signer = { async sign(input) {
  const id = String(++generation)
  grants.set(id, { key: input.key, size: input.contentLength })
  return { url: `${base}/grants/${id}`, headers: { 'content-length': String(input.contentLength) } }
} }
const server = createServer(async (incoming, outgoing) => {
  const path = incoming.url || '/'
  requests[`${incoming.method} ${path}`] = (requests[`${incoming.method} ${path}`] || 0) + 1
  try {
    const chunks: Buffer[] = []
    for await (const chunk of incoming) chunks.push(Buffer.from(chunk))
    const bytes = Buffer.concat(chunks)
    if (path === '/__state') {
      outgoing.setHeader('content-type', 'application/json')
      outgoing.end(JSON.stringify({ requests, quota: await f.repo.snapshot(),
        cases: (await f.repo.allCases()).map((row) => ({ state: row.state })),
        objects: [...f.objects].map(([key, bytes]) => ({ key, bytes: [...bytes] })),
      }))
      return
    }
    if (path.startsWith('/grants/')) {
      const id = path.split('/').pop()!
      const grant = grants.get(id)
      if (!grant || (scenario === 'expired' && id === '1')) { outgoing.writeHead(403); outgoing.end(); return }
      if (bytes.length !== grant.size) { outgoing.writeHead(400); outgoing.end(); return }
      await f.bucket.put(grant.key, bytes)
      outgoing.setHeader('etag', 'synthetic-etag')
      outgoing.end()
      return
    }
    const request = new Request(base + path, {
      method: incoming.method,
      headers: Object.fromEntries(Object.entries(incoming.headers).map(([key, value]) => [key, String(value)])),
      ...(bytes.length ? { body: bytes } : {}),
    })
    const response = await handle(request, f.deps)
    if (scenario === 'lost' && !dropped && path === '/v1/cases' && response.status === 201) {
      dropped = true
      incoming.socket.destroy() // server has committed; client never receives identity
      return
    }
    outgoing.writeHead(response.status, Object.fromEntries(response.headers))
    outgoing.end(await response.text())
  } catch {
    outgoing.writeHead(503)
    outgoing.end('{"error":"fixture_request_failed"}')
  }
})
server.listen(0, '127.0.0.1', () => {
  const port = (server.address() as { port: number }).port
  base = `http://127.0.0.1:${port}`
  process.stdout.write(JSON.stringify({ endpoint: base }) + '\n')
})
