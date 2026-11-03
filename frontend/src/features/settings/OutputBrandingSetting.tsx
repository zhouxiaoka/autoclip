import { settingsApi } from '../../services/api'
import { t } from '../../i18n'
import { beginExperience } from '../../analytics/experience'
import AppSwitchRow from './AppSwitchRow'

export default function OutputBrandingSetting() {
  return <AppSwitchRow
    label={t('自动添加品牌片尾')}
    hint={t('默认开启，为自动成片及修改后的导出添加 1.8 秒 AutoClip 动画。关闭后不影响已生成的视频。')}
    read={async () => (await settingsApi.getOutputBranding()).enabled}
    write={async (value) => {
      const finish = beginExperience('output_branding_save', { section: 'app', brand_outro_enabled: value })
      try {
        const settings = await settingsApi.setOutputBranding(value)
        finish('completed', { brand_outro_enabled: settings.enabled })
        return settings.enabled
      } catch (error) {
        finish('failed', {}, error)
        throw error
      }
    }}
  />
}
