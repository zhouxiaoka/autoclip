import { t } from '../../i18n'

/** Non-blocking. The save bar stays available. */
export default function WeakLocalTimelineNote() {
  return (
    <p className="ac-note" role="status">
      {t('这个本地模型往往剪不出片段，建议换更大的或云端模型')}
    </p>
  )
}
