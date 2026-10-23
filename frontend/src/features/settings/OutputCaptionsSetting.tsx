import { settingsApi } from '../../services/api'
import { t } from '../../i18n'
import AppSwitchRow from './AppSwitchRow'

/** The one read/write of output-captions.json. The settings page and the main page both use it. */
export function readOutputCaptions(): Promise<boolean> {
  return settingsApi.getOutputCaptions().then(settings => settings.enabled)
}

export function writeOutputCaptions(enabled: boolean): Promise<boolean> {
  return settingsApi.setOutputCaptions(enabled).then(settings => settings.enabled)
}

export function OutputCaptionsSwitch({ label, hint }: { label: string; hint: string }) {
  return <AppSwitchRow label={label} hint={hint} read={readOutputCaptions} write={writeOutputCaptions} />
}

export default function OutputCaptionsSetting() {
  return <OutputCaptionsSwitch
    label={t('自动成片压字幕')}
    hint={t('默认开启。关闭后，新建的自动成片不压字幕。标题只在封面上，不会烧进视频。已有项目不受影响，单条成片可以在编辑里重新打开字幕。')}
  />
}
