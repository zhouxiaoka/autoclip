import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { Layout } from 'antd'
import HomePage from './pages/HomePage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import PublishClipPage from './pages/PublishClipPage'
import PublishListPage from './pages/PublishListPage'
import PublishWeekPage from './pages/PublishWeekPage'
import SettingsPage from './pages/SettingsPage'
import Header from './components/Header'
import { UpdatePrompt } from './desktop/UpdatePrompt'
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
    <Layout>
      <Header />
      <UpdatePrompt />
      <Content>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/project/:id/publish/week" element={<PublishWeekPage />} />
          <Route path="/project/:id/publish/:clipId" element={<PublishClipPage />} />
          <Route path="/project/:id/publish" element={<PublishListPage />} />
          <Route path="/project/:id" element={<ProjectDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Content>
    </Layout>
  )
}

export default App
