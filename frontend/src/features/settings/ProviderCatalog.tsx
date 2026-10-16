import { t } from '../../i18n'
import { Btn, StatusDot } from '../../ui'
import type { Connection, ModelSettings } from './modelSettingsApi'
import type { ProviderGroupId, ProviderPreset } from './providerPresets'
import {
  CAPABILITY_FILTERS, CATALOG_GROUPS, type CapabilityFilter,
  connectKind, customCatalogId, displayNameOf, filterCatalog, groupCatalog, initialLetter,
  isCatalogConfigured, isCatalogConnected, shouldExpandMore, unmatchedCompatibleConnections, type LocalAsrReady,
} from './providerCatalogView'
import { providerIcon } from './providerIcons'

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

function actionLabel(preset: ProviderPreset, connected: boolean, configured = false): string {
  if (connected) return preset.id === 'whisper' || preset.id === 'sensevoice' ? t('settings.providers.available') : t('settings.providers.connected')
  if (configured) return t('已配置')
  if (connectKind(preset) === 'needs_endpoint') return t('settings.providers.needs_endpoint')
  if (preset.sponsor) return t('settings.providers.one_click')
  return t('settings.providers.configure')
}

function matchesCustom(connection: Connection, query: string, filter: CapabilityFilter): boolean {
  if (filter !== 'all' && filter !== 'language') return false
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  return [connection.name, connection.provider, 'compatible'].some(value => value.toLowerCase().includes(needle))
}

function CustomCard({
  connection, selected, onOpen,
}: {
  connection: Connection
  selected: boolean
  onOpen: (id: string) => void
}) {
  const id = customCatalogId(connection.id)
  return (
    <button
      type="button"
      className={`ac-provider-card${selected ? ' is-selected' : ''}`}
      data-provider-id={id}
      data-connect-kind="compatible"
      aria-current={selected || undefined}
      onClick={() => onOpen(id)}
    >
      <span className="ac-provider-mark" aria-hidden>{(connection.name.charAt(0) || '?').toUpperCase()}</span>
      <span className="ac-provider-card-body">
        <span className="ac-provider-card-title">{connection.name || t('自定义 OpenAI 兼容接口')}</span>
      </span>
      <span className="ac-provider-card-action">
        <span className="ac-provider-action-label">{t('settings.providers.repair_custom')}</span>
      </span>
    </button>
  )
}

function ProviderMark({ presetId, letter }: { presetId: string; letter: string }) {
  const icon = providerIcon(presetId)
  if (!icon) return <span className="ac-provider-mark" aria-hidden>{letter}</span>
  return (
    <span className={`ac-provider-mark has-icon is-${icon.tone}`} aria-hidden>
      <img src={icon.src} alt="" />
    </span>
  )
}

function ProviderCard({
  preset, settings, asrReady, selected, onOpen,
}: {
  preset: ProviderPreset
  settings: ModelSettings
  asrReady: LocalAsrReady
  selected: boolean
  onOpen: (id: string) => void
}) {
  const connected = isCatalogConnected(settings, preset, asrReady)
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
      <ProviderMark presetId={preset.id} letter={initialLetter(preset)} />
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
          : <span className="ac-provider-action-label">{actionLabel(preset, false, isCatalogConfigured(settings, preset))}</span>}
      </span>
    </button>
  )
}

export default function ProviderCatalog({
  settings, query, filter, moreOpen, selectedId, asrReady = {}, onQuery, onFilter, onToggleMore, onOpen, onAdd,
}: {
  settings: ModelSettings
  query: string
  filter: CapabilityFilter
  moreOpen: boolean
  selectedId?: string | null
  asrReady?: LocalAsrReady
  onQuery: (value: string) => void
  onFilter: (value: CapabilityFilter) => void
  onToggleMore: () => void
  onOpen: (id: string) => void
  onAdd?: () => void
}) {
  const visible = filterCatalog(query, filter)
  const groups = groupCatalog(visible)
  const customs = unmatchedCompatibleConnections(settings).filter(connection => matchesCustom(connection, query, filter))
  const expandMore = moreOpen || shouldExpandMore(query, filter, groups.more.length)
  const empty = visible.length === 0 && customs.length === 0
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
        {onAdd && <Btn size="sm" onClick={onAdd}>{t('添加服务商')}</Btn>}
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
      {customs.length > 0 && (
        <section className="ac-provider-group" data-provider-group="custom">
          <header className="ac-provider-group-head">
            <h3 className="ac-model-section-title">
              {t('settings.providers.custom_group')}
              <span className="count">{customs.length}</span>
            </h3>
          </header>
          <div className="ac-provider-grid">
            {customs.map(connection => (
              <CustomCard
                key={connection.id}
                connection={connection}
                selected={selectedId === customCatalogId(connection.id)}
                onOpen={onOpen}
              />
            ))}
          </div>
        </section>
      )}
      {CATALOG_GROUPS.map(group => {
        const rows = groups[group]
        if (!rows.length) return null
        // OhMyGame models-settings.tsx 175–182：「更多服务商 (N)」是独立折叠条，默认收起，展开后才渲染列表。
        if (group === 'more') {
          return (
            <section key={group} className="ac-provider-group" data-provider-group={group} data-expanded={expandMore ? '1' : '0'}>
              <button
                type="button"
                className="ac-provider-more"
                aria-expanded={expandMore}
                aria-controls="ac-provider-more-list"
                onClick={onToggleMore}
              >
                <span className="ac-provider-more-label">
                  {t(GROUP_KEY[group])}
                  <small>({rows.length})</small>
                </span>
                <svg className="ac-provider-more-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M6 9l6 6 6-6" /></svg>
              </button>
              {expandMore && (
                <div id="ac-provider-more-list" className="ac-provider-grid">
                  {rows.map(preset => (
                    <ProviderCard
                      key={preset.id}
                      preset={preset}
                      settings={settings}
                      asrReady={asrReady}
                      selected={selectedId === preset.id}
                      onOpen={onOpen}
                    />
                  ))}
                </div>
              )}
            </section>
          )
        }
        return (
          <section key={group} className="ac-provider-group" data-provider-group={group}>
            <header className="ac-provider-group-head">
              <h3 className="ac-model-section-title">
                {t(GROUP_KEY[group])}
                <span className="count">{rows.length}</span>
              </h3>
            </header>
            {(
              <div className={`ac-provider-grid${group === 'recommended' ? ' ac-provider-grid--recommended' : ''}`}>
                {rows.map(preset => (
                  <ProviderCard
                    key={preset.id}
                    preset={preset}
                    settings={settings}
                    asrReady={asrReady}
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
