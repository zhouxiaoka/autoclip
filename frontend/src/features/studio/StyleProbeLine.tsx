import { useEffect, useState } from 'react'
import { t } from '../../i18n'
import { captionsKey, durationKey, paceKey, sceneKey } from './editingStyle'
import { readStyle, subscribeStyle, type StyleSnapshot } from './editingStyleSession'

/** One recognition line under the import field. Cards stay in the style section. */
export default function StyleProbeLine({ sourceKey }: { sourceKey: string | null }) {
  const [snap, setSnap] = useState<StyleSnapshot>(() => readStyle())
  useEffect(() => subscribeStyle(() => setSnap(readStyle())), [])
  if (!sourceKey) return null
  const current = snap.key === sourceKey ? snap : null
  if (!current || current.status !== 'ready' || !current.result) {
    return <p className="studio-style-probe" role="status">{t('editing_style.probing')}</p>
  }
  const signals = current.result.signals
  return <p className="studio-style-probe" role="status">{t('editing_style.probe', {
    scene: t(sceneKey(signals.scene)),
    duration: t(durationKey(signals.duration_bucket)),
    pace: t(paceKey(signals.pace)),
    captions: t(captionsKey(signals.captions)),
  })}</p>
}
