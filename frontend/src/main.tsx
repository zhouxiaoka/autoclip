import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import { theme as antdTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'dayjs/locale/en'
import relativeTime from 'dayjs/plugin/relativeTime'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import { useTranslation } from 'react-i18next'
import './i18n'
import App from './App.tsx'
import ErrorBoundary from './components/ErrorBoundary'
import { ThemeProvider, useTheme } from './context/ThemeContext'
import { initAnalytics } from './analytics/posthog'
import { trackLaunch } from './analytics/lifecycle'
import './index.css'

// 初始化产品分析 / 埋点（无 key 时自动 no-op，不发任何网络请求）
initAnalytics()
// 注册全局属性 + 上报启动/安装/更新事件
void trackLaunch()

// 配置dayjs插件
dayjs.extend(relativeTime)
dayjs.extend(timezone)
dayjs.extend(utc)

// 设置dayjs中文和时区
dayjs.locale('zh-cn')
dayjs.tz.setDefault('Asia/Shanghai')

function Root() {
  // 统一在根节点接入错误边界，避免运行时异常导致白屏
  return (
    <ErrorBoundary showDetails={import.meta.env.DEV}>
      <App />
    </ErrorBoundary>
  )
}

function ThemedApp() {
  const { theme } = useTheme()
  const { i18n } = useTranslation()
  const isDark = theme === 'dark'
  const isEn = i18n.language?.startsWith('en')
  const antdLocale = isEn ? enUS : zhCN

  return (
    <ConfigProvider
      locale={antdLocale}
      theme={{
      algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
      token: {
        // Calm Premium tokens — see DESIGN.md
        colorPrimary: isDark ? '#5A8BFF' : '#2D6BFF',
        colorText: isDark ? '#ECEAE6' : '#1A1A19',
        colorTextSecondary: isDark ? '#A6A29B' : '#6E6B66',
        colorBgBase: isDark ? '#19181A' : '#F6F5F3',
        colorBgContainer: isDark ? '#211F22' : '#FFFFFF',
        colorBorder: isDark ? '#2C2A2D' : '#EBE9E4',
        colorBorderSecondary: isDark ? '#232124' : '#F0EEEA',
        borderRadius: 10,
        fontFamily: '"Geist","PingFang SC","Noto Sans SC",system-ui,-apple-system,sans-serif',
        controlHeight: 38,
      },
      components: {
        Button: { borderRadius: 999, controlHeight: 40, fontWeight: 500 },
        Select: { borderRadius: 10 },
        Card: { borderRadiusLG: 16 },
      },
    }}
    >
    <React.StrictMode>
      <HashRouter>
        <Root />
      </HashRouter>
    </React.StrictMode>
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ThemeProvider>
    <ThemedApp />
  </ThemeProvider>,
)
