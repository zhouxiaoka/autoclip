type ImportRoutingConfig = {
  import_staging?: unknown
  smart_import?: { auto_start?: unknown }
}

/** Automatic imports stay on results while screening; older saves can still have staging set. */
export function needsImportConfirmation(project: { settings?: ImportRoutingConfig; processing_config?: ImportRoutingConfig }): boolean {
  const configs = [project.settings, project.processing_config]
  if (configs.some(config => config?.smart_import?.auto_start === true)) return false
  return configs.some(config => !!config?.import_staging)
}
