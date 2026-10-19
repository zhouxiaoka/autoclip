import { settingsApi } from '../../services/api'
import { t } from '../../i18n'
import AppSwitchRow from './AppSwitchRow'

export default function OutputCaptionsSetting() {
  return <AppSwitchRow
    label={t('自动成片压字幕')}
    hint={t('默认开启。关闭后，新建的自动成片不压字幕，标题仍在。已有项目不受影响，单条成片可以在编辑里重新打开字幕。')}
    read={async () => (await settingsApi.getOutputCaptions()).enabled}
    write={async (value) => (await settingsApi.setOutputCaptions(value)).enabled}
  />
}
