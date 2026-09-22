import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { Layout } from 'antd'
import HomePage from './pages/HomePage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import SettingsPage from './pages/SettingsPage'
import Header from './components/Header'
import { UpdateProvider } from './desktop/UpdatePrompt'
import { trackPageview } from './analytics/posthog'
import { startWorkflowObserver } from './analytics/observer'

const { Content } = Layout

// HashRouter 下手动上报 pageview（init 时已关闭自动 pageview）
function usePageviewTracking() {
  const location = useLocation()
  useEffect(() => {
    trackPageview(location.pathname + location.search)
  }, [location.pathname, location.search])
}

function App() {
  console.log('🎬 App组件已加载');
  usePageviewTracking()
  useEffect(() => startWorkflowObserver(), [])

  return (
    <UpdateProvider>
      <Layout>
        <Header />
        <Content>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/project/:id" element={<ProjectDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Content>
      </Layout>
    </UpdateProvider>
  )
}

export default App
