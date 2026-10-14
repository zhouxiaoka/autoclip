import { t } from '../../i18n'
import { Btn, StatusDot } from '../../ui'
import type { ModelSettings } from './modelSettingsApi'
import type { ProviderGroupId, ProviderPreset } from './providerPresets'
import {
  CAPABILITY_FILTERS, CATALOG_GROUPS, type CapabilityFilter,
  connectKind, displayNameOf, filterCatalog, groupCatalog, initialLetter,
  isCatalogConnected, shouldExpandMore,
} from './providerCatalogView'

const FILTER_KEY: Record<CapabilityFilter, string> = {
  all: 'settings.providers.filter.all',
  language: 'settings.providers.filter.language',
  asr: 'settings.providers.filter.asr',
  tts: 'settings.providers.filter.tts',
  image: 'settings.providers.filter.image',
  music: 'settings.providers.filter.music',
  video: 'settings.providers.filter.video',
}

const GROUP_KEY: Record<ProviderGroupId, string> = {
  recommended: 'settings.providers.group.recommended',
  popular: 'settings.providers.group.popular',
  local: 'settings.providers.group.local',
  more: 'settings.providers.group.more',
}

function actionLabel(preset: ProviderPreset, connected: boolean): string {
  if (connected) return preset.id === 'whisper' || preset.id === 'sensevoice' ? t('settings.providers.available') : t('settings.providers.connected')
  if (preset.sponsor) return t('settings.providers.one_click')
  return t('settings.providers.configure')
}

function ProviderCard({
  preset, settings, selected, onOpen,
}: {
  preset: ProviderPreset
  settings: ModelSettings
  selected: boolean
  onOpen: (id: string) => void
}) {
  const connected = isCatalogConnected(settings, preset)
  const caps = preset.capabilities.filter((capability): capability is Exclude<CapabilityFilter, 'all'> => capability !== 'all' && capability in FILTER_KEY)
  return (
    <button
      type="button"
      className={`ac-provider-card${selected ? ' is-selected' : ''}${connected ? ' is-connected' : ''}`}
      data-provider-id={preset.id}
      data-connect-kind={connectKind(preset)}
      aria-current={selected || undefined}
      onClick={() => onOpen(preset.id)}
    >
      <span className="ac-provider-mark" aria-hidden>{initialLetter(preset)}</span>
      <span className="ac-provider-card-body">
        <span className="ac-provider-card-title">
          {t(displayNameOf(preset))}
          {preset.sponsor && <span className="ac-badge">{t('settings.providers.badge.sponsor')}</span>}
        </span>
        {caps.length > 0 && (
          <span className="ac-provider-caps">
            {caps.map(capability => (
              <span key={capability} className="ac-provider-cap">{t(FILTER_KEY[capability])}</span>
            ))}
          </span>
        )}
      </span>
      <span className="ac-provider-card-action">
        {connected
          ? <StatusDot tone="ok" label={actionLabel(preset, true)} />
          : <span className="ac-provider-action-label">{actionLabel(preset, false)}</span>}
      </span>
    </button>
  )
}

export default function ProviderCatalog({
  settings, query, filter, moreOpen, selectedId, onQuery, onFilter, onToggleMore, onOpen,
}: {
  settings: ModelSettings
  query: string
  filter: CapabilityFilter
  moreOpen: boolean
  selectedId?: string | null
  onQuery: (value: string) => void
  onFilter: (value: CapabilityFilter) => void
  onToggleMore: () => void
  onOpen: (id: string) => void
}) {
  const visible = filterCatalog(query, filter)
  const groups = groupCatalog(visible)
  const expandMore = moreOpen || shouldExpandMore(query, filter, groups.more.length)
  const empty = visible.length === 0
  return (
    <div className="ac-provider-catalog" id="ai-model">
      <div className="ac-provider-toolbar">
        <label className="ac-provider-search">
          <span className="visually-hidden">{t('settings.providers.search')}</span>
          <input
            className="ac-input"
            type="search"
            value={query}
            placeholder={t('settings.providers.search_placeholder')}
            aria-label={t('settings.providers.search')}
            onChange={event => onQuery(event.target.value)}
          />
        </label>
      </div>
      <div className="ac-chips ac-provider-filters" role="radiogroup" aria-label={t('settings.providers.filter.all')}>
        {CAPABILITY_FILTERS.map(value => (
          <button
            key={value}
            type="button"
            className="ac-chip"
            role="radio"
            aria-checked={filter === value}
            onClick={() => onFilter(value)}
          >
            {t(FILTER_KEY[value])}
          </button>
        ))}
      </div>
      {empty && (
        <div className="ac-empty" role="status">
          <b>{t('settings.providers.no_matches')}</b>
          {t('settings.providers.no_matches_hint')}
        </div>
      )}
      {CATALOG_GROUPS.map(group => {
        const rows = groups[group]
        if (!rows.length) return null
        const collapsed = group === 'more' && !expandMore
        return (
          <section key={group} className="ac-provider-group" data-provider-group={group}>
            <header className="ac-provider-group-head">
              <h3 className="ac-model-section-title">
                {t(GROUP_KEY[group])}
                <span className="count">{rows.length}</span>
              </h3>
              {group === 'more' && (
                <Btn variant="text" size="sm" onClick={onToggleMore}>
                  {expandMore ? t('settings.providers.collapse') : t('settings.providers.expand')}
                </Btn>
              )}
            </header>
            {!collapsed && (
              <div className={`ac-provider-grid${group === 'recommended' ? ' ac-provider-grid--recommended' : ''}`}>
                {rows.map(preset => (
                  <ProviderCard
                    key={preset.id}
                    preset={preset}
                    settings={settings}
                    selected={selectedId === preset.id}
                    onOpen={onOpen}
                  />
                ))}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}
