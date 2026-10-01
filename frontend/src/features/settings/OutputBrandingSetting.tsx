import { useCallback, useEffect, useRef, useState } from 'react'
import { Switch, message } from 'antd'
import { settingsApi } from '../../services/api'
import { t } from '../../i18n'
import { Btn, Row } from '../../ui'
import { beginExperience } from '../../analytics/experience'

export default function OutputBrandingSetting() {
  const [enabled, setEnabled] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  const [saving, setSaving] = useState(false)
  const mounted = useRef(false)
  const load = useCallback(async () => {
    setFailed(false)
    try {
      const settings = await settingsApi.getOutputBranding()
      if (mounted.current) { setEnabled(settings.enabled); setLoaded(true) }
    } catch { if (mounted.current) setFailed(true) }
  }, [])
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false } }, [load])
  const save = async (value: boolean) => {
    const finish = beginExperience('output_branding_save', { section: 'app', brand_outro_enabled: value })
    setSaving(true)
    try {
      const settings = await settingsApi.setOutputBranding(value)
      finish('completed', { brand_outro_enabled: settings.enabled })
      if (mounted.current) setEnabled(settings.enabled)
    } catch (error) { finish('failed', {}, error); if (mounted.current) message.error(t('保存失败，请稍后重试')) }
    finally { if (mounted.current) setSaving(false) }
  }
  return <Row label={t('自动添加品牌片尾')} hint={t('默认开启，为自动成片及修改后的导出添加 1.8 秒 AutoClip 动画。关闭后不影响已生成的视频。')}>
    {failed ? <Btn size="sm" onClick={() => void load()}>{t('重试')}</Btn> :
      <Switch aria-label={t('自动添加品牌片尾')} checked={enabled} disabled={!loaded} loading={saving || !loaded} onChange={value => void save(value)} />}
  </Row>
}
