/**
 * Known-weak local chat models for the Studio timeline (#428).
 * Same rule as backend/core/weak_local_timeline.py: small local models only.
 * A warning, not a block. Saving the key or the model stays allowed.
 */
const LOCAL_PROVIDERS = new Set(['ollama', 'lmstudio'])
const MAX_WEAK_BILLIONS = 8
const SMALL_ALIASES = ['phi3', 'phi-3', 'phi4-mini', 'phi-4-mini', 'tinyllama', 'smollm']

function isLocalBase(url?: string | null): boolean {
  const raw = (url || '').trim()
  if (!raw) return false
  let host = ''
  try { host = new URL(raw).hostname.toLowerCase().replace(/^\[|\]$/g, '') } catch { return false }
  if (['localhost', '0.0.0.0', 'host.docker.internal', '::1'].includes(host) || host.endsWith('.local') || host.endsWith('.localhost')) return true
  const v4 = host.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/)
  if (v4) {
    const a = Number(v4[1])
    const b = Number(v4[2])
    return a === 127 || a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254)
  }
  return /^f[cd][0-9a-f]{2}:|^fe80:/.test(host)
}

export function isKnownWeakLocalTimelineModel(provider?: string | null, model?: string | null, baseUrl?: string | null): boolean {
  const name = (model || '').trim().toLowerCase()
  if (!name || /embed|whisper|rerank/.test(name)) return false
  const id = (provider || '').trim().toLowerCase()
  const local = LOCAL_PROVIDERS.has(id) || ((id === 'compatible' || id === 'openai' || id === 'other') && isLocalBase(baseUrl))
  if (!local) return false
  const sizes = [...name.matchAll(/(?:^|[^0-9a-z])(\d+(?:\.\d+)?)b(?=[^0-9a-z]|$)/g)].map(match => Number(match[1]))
  if (sizes.length) return sizes[sizes.length - 1] <= MAX_WEAK_BILLIONS
  return SMALL_ALIASES.some(alias => name.includes(alias))
}

export function analysisUsesWeakLocalTimelineModel(settings: {
  analysis?: { connection_id?: string; model?: string } | null
  connections?: { id: string; provider?: string; base_url?: string }[]
}): boolean {
  const binding = settings.analysis
  if (!binding?.model) return false
  const connection = (settings.connections || []).find(item => item.id === binding.connection_id)
  return isKnownWeakLocalTimelineModel(connection?.provider, binding.model, connection?.base_url)
}
