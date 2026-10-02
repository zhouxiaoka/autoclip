function configRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

/** Automatic imports stay on results while screening; older saves can still have staging set. */
export function needsImportConfirmation(project: { settings?: unknown; processing_config?: unknown }): boolean {
  const configs = [project.settings, project.processing_config].map(configRecord)
  if (configs.some(config => configRecord(config.smart_import).auto_start === true)) return false
  return configs.some(config => !!config.import_staging)
}
