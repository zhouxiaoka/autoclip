import React from 'react'
import { Layout, Button } from 'antd'
import { SettingOutlined, BulbOutlined, MoonOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useTheme } from '../context/ThemeContext'

const { Header: AntHeader } = Layout

// Calm Premium header — see DESIGN.md
const Header: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const isSettings = location.pathname === '/settings'
  const { theme, toggleTheme } = useTheme()

  return (
    <AntHeader
      style={{
        padding: '0 56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '64px',
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
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* 返回入口由各页面页头承担（见 DESIGN.md App Layer），顶栏只留全局动作 */}
        <Button
          type="text"
          icon={theme === 'dark' ? <BulbOutlined /> : <MoonOutlined />}
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
          title={theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
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
        >
          设置
        </Button>
      </div>
    </AntHeader>
  )
}

export default Header
