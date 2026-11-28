import { settingsApi } from '../../services/api'
import { t } from '../../i18n'
import { beginExperience } from '../../analytics/experience'
import AppSwitchRow from './AppSwitchRow'

export function readOutputBranding(): Promise<boolean> {
  return settingsApi.getOutputBranding().then(settings => settings.enabled)
}

export function writeOutputBranding(value: boolean): Promise<boolean> {
  const finish = beginExperience('output_branding_save', { section: 'app', brand_outro_enabled: value })
  return settingsApi.setOutputBranding(value).then(
    settings => {
      finish('completed', { brand_outro_enabled: settings.enabled })
      return settings.enabled
    },
    error => {
      finish('failed', {}, error)
      throw error
    },
  )
}

export function OutputBrandingSwitch({ label, hint }: { label: string; hint: string }) {
  return <AppSwitchRow label={label} hint={hint} read={readOutputBranding} write={writeOutputBranding} />
}

export default function OutputBrandingSetting() {
  return <OutputBrandingSwitch
    label={t('自动添加品牌片尾')}
    hint={t('默认开启，为自动成片及修改后的导出添加 1.8 秒 AutoClip 动画。关闭后不影响已生成的视频。')}
  />
}
