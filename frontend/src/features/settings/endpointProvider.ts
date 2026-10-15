import { getProvider } from './providerPresets'
import type { Connection } from './modelSettingsApi'

/** Endpoint-only catalog rows are drafts until the user's address passes validation. */
export const endpointProviderReady = (c: Connection) => {
  const preset = getProvider(c.catalog_provider_id || c.provider)
  if (!preset || preset.base_url || preset.protocol === 'local') return true
  return !!c.base_url.trim() && c.validation_status === 'ok'
}

