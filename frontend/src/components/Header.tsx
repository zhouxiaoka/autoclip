import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React from 'react'
import LanguageSelect from './LanguageSelect'
import { Layout, Button } from 'antd'
import { SettingOutlined, BulbOutlined, MoonOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useTheme } from '../context/ThemeContext'
import { UpdateToast, useAppUpdate } from '../desktop/UpdatePrompt'

const { Header: AntHeader } = Layout

// Calm Premium header — see DESIGN.md
const Header: React.FC = () => {
  useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const isSettings = location.pathname === '/settings'
  const { theme, toggleTheme } = useTheme()
  const appUpdate = useAppUpdate()
  const updatePending = appUpdate.phase === 'downloading' || appUpdate.phase === 'ready' || appUpdate.phase === 'failed' || appUpdate.phase === 'restarting'

  return (
    <AntHeader
      style={{
        padding: '0 clamp(12px, 4vw, 56px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '64px',
        lineHeight: 'normal',
        overflow: 'visible',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        backdropFilter: 'blur(10px)',
        background: 'color-mix(in srgb, var(--ac-bg) 78%, transparent)',
        borderBottom: '1px solid var(--ac-line-2)',
      }}
    >
      {/* Wordmark — serif, italic "Clip" */}
      <div
        style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => navigate('/')}
      >
        <span
          style={{
            fontFamily: 'var(--ac-font-serif)',
            fontSize: '26px',
            color: 'var(--ac-ink)',
            letterSpacing: '0.3px',
          }}
        >
          Auto<em style={{ fontStyle: 'italic' }}>Clip</em>
        </span>
      </div>

      {/* Right side */}
      <div className="ac-header-actions">
        {updatePending && (
          <div className="ac-update-anchor">
            <button
              type="button"
              className="ac-update-icon"
              aria-expanded={appUpdate.toastVisible}
              aria-label={t('有新版本可用')}
              onClick={() => appUpdate.toastVisible ? appUpdate.snooze() : appUpdate.openUpdate()}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <circle cx="12" cy="12" r="8.25" />
                <path d="M12 16V8M9.5 10.5 12 8l2.5 2.5" />
              </svg>
            </button>
            <UpdateToast />
          </div>
        )}
        <div className="ac-header-permanent">
        <LanguageSelect />
        {/* 返回入口由各页面页头承担（见 DESIGN.md App Layer），顶栏只留全局动作 */}
        <Button
          type="text"
          icon={theme === 'dark' ? <BulbOutlined /> : <MoonOutlined />}
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? t("切换到亮色模式") : t("切换到暗色模式")}
          title={theme === 'dark' ? t("切换到亮色模式") : t("切换到暗色模式")}
          style={{
            color: 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            width: '36px',
            height: '36px',
            padding: 0,
            background: 'var(--ac-card)',
          }}
        />
        <Button
          type="text"
          icon={<SettingOutlined />}
          onClick={() => navigate('/settings')}
          aria-current={isSettings ? 'page' : undefined}
          style={{
            color: isSettings ? 'var(--ac-ink)' : 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            height: '36px',
            padding: '0 16px',
            background: isSettings ? 'var(--ac-line-2)' : 'var(--ac-card)',
          }}
        >{t("设置")}</Button>
        </div>
      </div>
    </AntHeader>
  )
}

export default Header
