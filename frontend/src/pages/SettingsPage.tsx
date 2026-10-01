import { trackExperience } from '../analytics/experience'
import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useState, useEffect, useMemo, useRef } from 'react'
import { Switch, message } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { settingsApi } from '../services/api'
import AIModelSettings from '../features/settings/AIModelSettings'
import OutputBrandingSetting from '../features/settings/OutputBrandingSetting'
import FeedbackDialog from '../components/FeedbackDialog'
import PublishSettings from '../components/PublishSettings'
import { isDesktopMode } from '../utils/desktopMode'
import { openExternalLink } from '../utils/externalLinks'
import { isAnalyticsEnabled, setAnalyticsEnabled } from '../analytics/posthog'
import { getRuntimeInfo } from '../analytics/lifecycle'
import { isCrashReportsEnabled, setCrashReportsEnabled } from '../desktop/sentry'
import { getAppVersion } from '../desktop/updater'
import { useAppUpdate } from '../desktop/UpdatePrompt'
import { FEEDBACK_DISCUSSIONS_URL, FEEDBACK_ISSUES_URL } from '../analytics/feedback'
import { useTheme } from '../context/ThemeContext'
import { Btn, Icon, Row, Section, Segmented } from '../ui'

type SectionKey = 'ai' | 'publish' | 'app' | 'feedback'
const NAV: Array<{ key: SectionKey; label: string }> = [
  { key: 'ai', get label() { return t("AI 模型") } },
  { key: 'publish', get label() { return t("发布") } },
  { key: 'app', get label() { return t("应用") } },
  { key: 'feedback', get label() { return t("反馈") } },
]
// 旧链接（项目卡「模型设置」「转写设置」等）仍能打开，并滚到对应小节
const SECTION_ALIASES: Record<string, { section: SectionKey; anchor?: string }> = {
  model: { section: 'ai', anchor: 'ai-model' },
  analysis: { section: 'ai', anchor: 'ai-model' },
  vision: { section: 'ai', anchor: 'ai-model' },
  speech: { section: 'ai', anchor: 'ai-speech' },
  cover: { section: 'ai', anchor: 'ai-cover' },
}

// Calm Premium settings — left nav + setting rows (see DESIGN.md → App Layer)
const SettingsPage: React.FC = () => {
  useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const requested = new URLSearchParams(location.search).get('section') || ''
  const initialSection = useMemo<SectionKey>(() => (
    SECTION_ALIASES[requested]?.section || (NAV.find((n) => n.key === requested)?.key as SectionKey) || 'ai'
  ), [requested])
  const [active, setActive] = useState<SectionKey>(initialSection)
  const [analyticsOn, setAnalyticsOn] = useState(isAnalyticsEnabled())
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const runtime = getRuntimeInfo()
  const viewedSection = useRef<SectionKey | null>(null)
  useEffect(() => {
    if (viewedSection.current === active) return
    viewedSection.current = active
    trackExperience('settings_section_viewed', { section: active, entry_source: location.state?.settingsEntry === 'home_setup' ? 'home_setup' : 'direct' })
  }, [active])
  useEffect(() => { setActive(initialSection) }, [initialSection])
  return (
    <div className="ac-page">
      <header>
        {/* 与详情页一致：页内返回，不依赖顶栏 logo */}
        <button className="ac-back" onClick={() => navigate('/')}>
          <Icon.Back />{t("项目")}</button>
        <h1 className="ac-title">{t("设置")}</h1>
        <div className="ac-meta">
          <span className="ac-mono">{runtime.version !== 'unknown' ? `v${runtime.version}` : 'dev'}</span>
          <span className="dot" />
          <span className="ac-mono">{runtime.os}/{runtime.arch}</span>
        </div>
      </header>

      <div className="ac-settings" style={{ marginTop: 36 }}>
        <nav className="ac-settings-nav" aria-label={t("设置分类")}>
          {NAV.map((n) => (
            <button key={n.key} aria-current={active === n.key} onClick={() => navigate(`/settings?section=${n.key}`, { replace: true })}>{n.label}</button>
          ))}
        </nav>

        <div className="ac-settings-body">
          <div hidden={active !== 'ai'}>
            <AIModelSettings requestedSection={requested} />
          </div>

          {/* ---------------- 应用 ---------------- */}
          {active === 'app' && (
            <AppSection analyticsOn={analyticsOn} onAnalyticsChange={(on) => { setAnalyticsEnabled(on); setAnalyticsOn(on) }} />
          )}

          {active === 'publish' && <PublishSettings />}

          {/* ---------------- 反馈 ---------------- */}
          {active === 'feedback' && (
            <Section title={t("反馈")} description={t("哪里不对、想要什么，直接说。运行环境会自动附上，不含视频内容与 API 密钥。正文会公开出现在 GitHub。")}>
              <div className="ac-rows">
                <Row label={t("发送反馈")} hint={t("在应用内写一句话即可。故障会进 GitHub Issue，想法会进 Discussions。")}>
                  <Btn variant="cta" size="sm" style={{ height: 32, fontSize: 13, padding: '0 16px' }} onClick={() => setFeedbackOpen(true)}>
                    <Icon.Chat size={13} />{t("写反馈")}</Btn>
                </Row>
                <Row label={t("出了问题")} hint={t("版本、平台和模型写在 Issue 里，方便复现。")}>
                  <Btn size="sm" onClick={() => openExternalLink(FEEDBACK_ISSUES_URL)}>{t("报告问题")}<Icon.External size={12} /></Btn>
                </Row>
                <Row label={t("想法与用法")} hint={t("希望支持的能力和你的用法发到 Discussions，不要为此开 Issue。")}>
                  <Btn size="sm" onClick={() => openExternalLink(FEEDBACK_DISCUSSIONS_URL)}>{t("去讨论")}<Icon.External size={12} /></Btn>
                </Row>
                <Row label={t("当前状态与已知问题")} hint={t("发版节奏、已知 bug 与解决办法都在这条置顶 Issue 里。")}>
                  <Btn variant="text" size="sm" onClick={() => openExternalLink('https://github.com/zhouxiaoka/autoclip/issues/96')}>#96 <Icon.External size={12} /></Btn>
                </Row>
              </div>
            </Section>
          )}
        </div>
      </div>

      <FeedbackDialog open={feedbackOpen} onClose={() => setFeedbackOpen(false)} context={{ source: 'settings' }} />
    </div>
  )
}

/* ---------------- 应用 ---------------- */
const AppSection: React.FC<{ analyticsOn: boolean; onAnalyticsChange: (on: boolean) => void }> = ({ analyticsOn, onAnalyticsChange }) => {
  useTranslation()
  const { theme, setTheme } = useTheme()
  const [autostart, setAutostart] = useState(false)
  const [busy, setBusy] = useState(false)
  const [desktop, setDesktop] = useState(false)
  const [crashOn, setCrashOn] = useState(isCrashReportsEnabled())
  const [version, setVersion] = useState('')
  const appUpdate = useAppUpdate()

  useEffect(() => {
    (async () => {
      try {
        const isDesktop = await isDesktopMode()
        setDesktop(isDesktop)
        setVersion(await getAppVersion())
        if (isDesktop) {
          const { invoke } = await import('@tauri-apps/api/core')
          setAutostart(Boolean(await invoke('is_autostart_enabled')))
        }
        try {
          const privacy = await settingsApi.getPrivacy()
          if (typeof privacy?.crash_reports === 'boolean') {
            setCrashReportsEnabled(privacy.crash_reports)
            setCrashOn(privacy.crash_reports)
          }
        } catch {
          /* 后端未起或非桌面数据目录时用 localStorage */
        }
      } catch (err) {
        console.error('检查自动启动状态失败:', err)
      }
    })()
  }, [])

  const toggleAutostart = async (enabled: boolean) => {
    if (!desktop) { message.error(t("此功能仅在桌面应用中可用")); return }
    setBusy(true)
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke(enabled ? 'enable_autostart' : 'disable_autostart')
      setAutostart(enabled)
    } catch (err) {
      console.error('切换自动启动状态失败:', err)
      message.error(t("操作失败: {{value1}}", { value1: err }))
    } finally {
      setBusy(false)
    }
  }

  const toggleCrashReports = async (enabled: boolean) => {
    setCrashReportsEnabled(enabled)
    setCrashOn(enabled)
    try {
      await settingsApi.updatePrivacy({ crash_reports: enabled })
    } catch {
      message.warning(t("前端开关已生效，但后端隐私设置保存失败，请重试。"))
    }
  }

  const handleCheckUpdate = async () => {
    if (!desktop && !appUpdate.preview) { message.info(t('检查更新仅在桌面应用中可用')); return }
    try {
      const result = await appUpdate.checkNow()
      if (result === 'current') {
        const current = appUpdate.currentVersion || version
        message.success(current ? t('已是最新版本（{{version}}）', { version: current }) : t('已是最新版本'))
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err)
      if (text === 'desktop-only') message.info(t('检查更新仅在桌面应用中可用'))
      else message.error(t('检查更新失败: {{error}}', { error: text.split('{{').join('{') }))
    }
  }

  const shownVersion = appUpdate.currentVersion || version
  const versionHint = appUpdate.phase === 'ready' || appUpdate.phase === 'restarting'
    ? t('可更新到 {{version}}', { version: appUpdate.version })
    : appUpdate.phase === 'downloading'
      ? t('正在准备 {{version}}', { version: appUpdate.version })
      : appUpdate.phase === 'failed'
        ? t('更新没有下载完：{{error}}', { error: appUpdate.error })
        : shownVersion
          ? t('当前 {{version}}', { version: shownVersion })
          : t('桌面应用可检查 GitHub Release 上的更新。')

  return (
    <Section title={t("应用")} description={t("外观、启动与隐私。")}>
      <div className="ac-rows">
        <Row label={t("外观")} hint={t("首次启动跟随系统。")}>
          <Segmented size="sm" ariaLabel={t("外观")} value={theme} onChange={setTheme} options={[{ value: 'light', label: t("浅色") }, { value: 'dark', label: t("深色") }]} />
        </Row>
        <Row label={t("开机自动启动")} hint={t("启用后随系统启动，可从托盘打开。仅桌面应用可用。")}>
          <Switch checked={autostart} onChange={toggleAutostart} loading={busy} disabled={!desktop} />
        </Row>
        <OutputBrandingSetting />
        {(desktop || appUpdate.preview) && (
          <Row label={t('版本')} hint={versionHint}>
            {appUpdate.phase === 'ready' || appUpdate.phase === 'restarting' ? (
              <Btn size="sm" variant="cta" loading={appUpdate.phase === 'restarting'} onClick={() => void appUpdate.restart()}>{t('更新并重启')}</Btn>
            ) : appUpdate.phase === 'downloading' ? (
              <Btn size="sm" onClick={appUpdate.showToast}>{t('查看进度')}</Btn>
            ) : appUpdate.phase === 'failed' ? (
              <Btn size="sm" onClick={() => void appUpdate.retry()}>{t('重试')}</Btn>
            ) : (
              <Btn size="sm" loading={appUpdate.phase === 'checking'} onClick={() => void handleCheckUpdate()}>{t('检查更新')}</Btn>
            )}
          </Row>
        )}
        <Row label={t("匿名使用统计")} hint={t("只采集功能使用、出片成功 / 失败等匿名事件，不含视频内容、字幕文本或 API 密钥。关闭后仍可在反馈里主动发送。")}>
          <Switch checked={analyticsOn} onChange={onAnalyticsChange} />
        </Row>
        <Row label={t("崩溃报告")} hint={t("把崩溃栈发到 Sentry，便于修复。不含视频内容、字幕或 API 密钥。未配置上报地址时不会发送。")}>
          <Switch checked={crashOn} onChange={toggleCrashReports} />
        </Row>
      </div>
    </Section>
  )
}

export default SettingsPage
