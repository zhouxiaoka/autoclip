import React from 'react'
import { Layout, Button } from 'antd'
import { SettingOutlined, HomeOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'

const { Header: AntHeader } = Layout

const Header: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const isHomePage = location.pathname === '/'

  return (
    <AntHeader 
      className="glass-effect"
      style={{ 
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '72px',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        backdropFilter: 'blur(20px)',
        background: 'rgba(26, 26, 26, 0.9)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
      }}
    >
      {/* Logo */}
      <div 
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          cursor: 'pointer',
          transition: 'all 0.2s ease'
        }}
        onClick={() => navigate('/')}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'scale(1.05)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'scale(1)'
        }}
      >
        <span
          style={{
            fontSize: '24px',
            fontWeight: '700',
            background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
            letterSpacing: '-0.5px',
            textShadow: '0 0 20px rgba(79, 172, 254, 0.3)',
            filter: 'drop-shadow(0 2px 4px rgba(79, 172, 254, 0.2))'
          }}
        >
          AutoClip
        </span>
      </div>
      
      {/* Navigation Buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {!isHomePage && (
          <Button 
            type="primary"
            icon={<HomeOutlined />}
            onClick={() => navigate('/')}
            style={{
              background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
              border: 'none',
              borderRadius: '8px',
              height: '40px',
              padding: '0 20px',
              fontWeight: 500,
              boxShadow: '0 2px 8px rgba(79, 172, 254, 0.3)'
            }}
          >
            返回首页
          </Button>
        )}
        <Button 
          type="text" 
          icon={<SettingOutlined />}
          onClick={() => navigate('/settings')}
          style={{
            color: '#cccccc',
            border: '1px solid transparent',
            borderRadius: '8px',
            height: '40px',
            padding: '0 16px'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#2d2d2d'
            e.currentTarget.style.borderColor = '#404040'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
            e.currentTarget.style.borderColor = 'transparent'
          }}
        >
          设置
        </Button>
      </div>
    </AntHeader>
  )
}

export default Header