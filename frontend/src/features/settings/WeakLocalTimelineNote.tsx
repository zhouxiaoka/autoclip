import { t } from '../../i18n'

/** Non-blocking. The save bar stays available. */
export default function WeakLocalTimelineNote() {
  return (
    <p className="ac-note" role="status">
      {t('这个本地小模型经常无法返回可用的时间线。可以保存，但制作前建议改用云端模型，或更大、能返回结构化时间区间的模型。')}
    </p>
  )
}
