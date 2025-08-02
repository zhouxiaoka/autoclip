import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { Layout, Tabs } from 'antd'
import HomePage from './pages/HomePage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import SettingsPage from './pages/SettingsPage'
import Header from './components/Header'
import { RealTimeStatus } from './components/RealTimeStatus'
import { SimpleTest } from './components/SimpleTest'

const { Content } = Layout

function App() {
  console.log('🎬 App组件已加载');
  
  return (
    <Layout>
      <Header />
      <Content>
        <Tabs
          defaultActiveKey="main"
          onChange={(key) => console.log('🔄 切换到标签页:', key)}
          items={[
            {
              key: 'main',
              label: '主界面',
              children: (
                <Routes>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/project/:id" element={<ProjectDetailPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Routes>
              )
            },
            {
              key: 'realtime',
              label: '实时状态',
              children: <RealTimeStatus userId="frontend-user" />
            },
            {
              key: 'test',
              label: '简单测试',
              children: <SimpleTest />
            }
          ]}
        />
      </Content>
    </Layout>
  )
}

export default App