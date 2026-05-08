import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import relativeTime from 'dayjs/plugin/relativeTime'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import App from './App.tsx'
import ErrorBoundary from './components/ErrorBoundary'
import './index.css'

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

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ConfigProvider locale={zhCN}>
    <React.StrictMode>
      <HashRouter>
        <Root />
      </HashRouter>
    </React.StrictMode>
  </ConfigProvider>,
)
