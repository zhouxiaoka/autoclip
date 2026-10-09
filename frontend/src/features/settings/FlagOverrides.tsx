import { useSyncExternalStore } from 'react'
import { t } from '../../i18n'
import { Row, Section } from '../../ui'
import {
  FLAG_DEFAULTS, FLAG_NAMES, FLAG_SPEC, flagOverride, setFlagOverride, subscribeFlags,
  type FlagName, type FlagValue,
} from '../../analytics/flags'

const LABELS: Record<FlagName, string> = {
  autoclip_safe_mode: '关闭全部新功能',
  remember_platforms: '记住上次选择的平台',
  one_click_paste_start: '粘贴链接后自动开始',
  link_import_without_whisper: '链接导入不等待本地转写',
  notify_on_done: '制作完成时通知',
  publish_pack_v2: '复制文案并保存视频和封面',
  render_top_first: '先渲染得分最高的几条',
  clip_reasons: '在卡片上写选片理由',
  hide_legacy_entrypoints: '隐藏旧的制作入口',
  import_drop_zone: '首页使用居中的拖放区',
  track_overrides: '记录对自动决定的修改',
}

const VARIANT_LABELS: Record<string, string> = {
  button: '保持现在的按钮',
  autostart: '粘贴后自动开始',
  separate: '分开复制和导出',
  combined: '合成一个动作',
  limit10: '自动渲染前 10 条',
  top3: '自动渲染前 3 条',
}

function choice(override: FlagValue | null): string {
  if (override === null) return ''
  return String(override)
}

/** The panel is a developer tool. `vite build` sets DEV to false, so release builds omit it. */
export function flagOverridesVisible(): boolean {
  return import.meta.env.DEV === true
}

/** Local overrides for internal checks. Remote flags are never requested from here. */
export default function FlagOverrides() {
  useSyncExternalStore(subscribeFlags, () => FLAG_NAMES.map(name => String(flagOverride(name))).join('|'), () => '')
  if (!flagOverridesVisible()) return null
  return <Section title={t('实验功能')} description={t('只在这台电脑上覆盖功能开关。关闭匿名统计后不会请求远程开关，没有覆盖时新功能保持关闭。')}>
    <div className="ac-rows">
      {FLAG_NAMES.map(name => {
        const spec = FLAG_SPEC[name]
        const override = flagOverride(name)
        const options = spec.kind === 'boolean'
          ? [{ value: 'true', label: t('开启') }, { value: 'false', label: t('关闭') }]
          : spec.variants.map(value => ({ value, label: t(VARIANT_LABELS[value] || value) }))
        return <Row key={name} label={t(LABELS[name])} hint={name}>
          <select className="ac-input ac-flag-select" aria-label={t(LABELS[name])} value={choice(override)} onChange={event => {
            const next = event.target.value
            if (!next) setFlagOverride(name, null)
            else if (spec.kind === 'boolean') setFlagOverride(name, next === 'true')
            else setFlagOverride(name, next)
          }}>
            <option value="">{t('跟随默认')} · {spec.kind === 'boolean' ? (FLAG_DEFAULTS[name] ? t('开启') : t('关闭')) : t(VARIANT_LABELS[String(FLAG_DEFAULTS[name])] || String(FLAG_DEFAULTS[name]))}</option>
            {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </Row>
      })}
    </div>
  </Section>
}
