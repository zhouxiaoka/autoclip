/**
 * 片源下载进度。
 *
 * 列表/详情接口把 processing_config 序列化成 settings，不返回 processing_config。
 * 用 `processing_config.download_progress || 0` 时进度一直是 0，待处理项目会被
 * 项目卡画成写死的 5%（「导入中」），看起来像下载停在 5%。
 * 进度 0 且 download_status 为 downloading 也算正在下载，不能用 > 0 把起点滤掉。
 */

export interface DownloadFields {
  download_progress?: number | null
  download_status?: string | null
}

export interface DownloadProjectLike {
  status?: string | null
  processing_config?: DownloadFields | null
  settings?: DownloadFields | null
}

function hasDownloadFields(bag?: DownloadFields | null): bag is DownloadFields {
  return !!bag && (bag.download_progress != null || typeof bag.download_status === 'string')
}

export function downloadFields(project: DownloadProjectLike): DownloadFields | undefined {
  if (hasDownloadFields(project.processing_config)) return project.processing_config
  if (hasDownloadFields(project.settings)) return project.settings
  return undefined
}

export function readDownloadProgress(project: DownloadProjectLike): number {
  const raw = downloadFields(project)?.download_progress
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : 0
}

export function isSourceDownloading(project: DownloadProjectLike): boolean {
  const status = project.status
  if (status !== 'pending' && status !== 'downloading') return false
  const fields = downloadFields(project)
  if (!fields) return false
  const progress = readDownloadProgress(project)
  if (progress >= 100) return false
  if (fields.download_status === 'downloading') return true
  return progress > 0
}
