import { useState } from 'react'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import { trackOutputRating, trackOutputShare, type VariantProperties } from '../../analytics/studio'
import { openExternalLink } from '../../utils/externalLinks'
import { USE_CASE_URL } from './outputShare'

type Rating = 'ready' | 'needs_edit' | 'unusable'

/** Shown once after a successful download: three-level rating, then an optional use-case invite. */
export default function OutputFeedback({ projectId, variant, onDone }: { projectId: string; variant: VariantProperties; onDone: () => void }) {
  const [rated, setRated] = useState<Rating>()
  const rate = (value: Rating) => {
    setRated(value)
    trackOutputRating(projectId, { output_rating: value, ...variant })
  }
  if (!rated) return <div className="studio-output-feedback" role="group" aria-label={t('这条成片能直接用吗？')}>
    <span className="studio-output-hint">{t('这条成片能直接用吗？')}</span>
    <div className="studio-output-feedback-actions">
      <Btn size="sm" variant="text" onClick={() => rate('ready')}>{t('能直接用')}</Btn>
      <Btn size="sm" variant="text" onClick={() => rate('needs_edit')}>{t('改一下能用')}</Btn>
      <Btn size="sm" variant="text" onClick={() => rate('unusable')}>{t('不能用')}</Btn>
      <Btn size="sm" variant="text" onClick={onDone} aria-label={t('关闭')}>×</Btn>
    </div>
  </div>
  return <div className="studio-output-feedback" role="status">
    <span className="studio-output-hint">{rated === 'unusable' ? t('收到，我们会继续改进挑片和剪辑。') : t('谢谢反馈。愿意把这条成片分享为使用案例吗？')}</span>
    <div className="studio-output-feedback-actions">
      {rated !== 'unusable' && <Btn size="sm" variant="text" onClick={() => { trackOutputShare(projectId, { share_target: 'use_case_discussion', ...variant }); void openExternalLink(USE_CASE_URL); onDone() }}>{t('分享使用案例')}</Btn>}
      <Btn size="sm" variant="text" onClick={onDone}>{t('关闭')}</Btn>
    </div>
  </div>
}
