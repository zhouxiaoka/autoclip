import React from 'react'
import { createRoot } from 'react-dom/client'
import './tokens.css'
import '../src/ui/ac.css'
import '../src/features/studio/studio.css'
import UrlPreview, { type UrlInspectPreview } from '../src/features/studio/UrlPreview'

const scene = new URLSearchParams(location.search).get('scene') || 'platform-sub'

const platformSub: UrlInspectPreview = {
  title: '【访谈】如何把长视频做成可发布短片',
  duration: 1260,
  thumbnail: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect fill="#2D6BFF" width="320" height="180"/><text x="160" y="96" text-anchor="middle" fill="#fff" font-size="18" font-family="sans-serif">封面</text></svg>'),
  has_manual_subtitle: true,
  has_audio: true,
  preview_route: 'platform_subtitle',
  recommended_analysis: 'subtitle',
  language: 'zh',
  max_height: 1080,
}

const needInstall: UrlInspectPreview = {
  title: '无字幕播客：本地转写预览',
  duration: 1800,
  thumbnail: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect fill="#6E6B66" width="320" height="180"/><text x="160" y="96" text-anchor="middle" fill="#fff" font-size="18" font-family="sans-serif">播客</text></svg>'),
  has_manual_subtitle: false,
  has_audio: true,
  preview_route: 'local_transcription',
  recommended_analysis: 'subtitle',
}

const visual: UrlInspectPreview = {
  title: '静音素材：按画面制作',
  duration: 480,
  thumbnail: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect fill="#1A1A19" width="320" height="180"/><text x="160" y="96" text-anchor="middle" fill="#fff" font-size="18" font-family="sans-serif">无音轨</text></svg>'),
  has_manual_subtitle: false,
  has_audio: false,
  preview_route: 'visual',
  recommended_analysis: 'visual',
}

function Frame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div style={{ maxWidth: 560, margin: '40px auto', padding: 24 }} data-testid={`f4-${scene}`}>
      <h2 style={{ fontSize: 15, marginBottom: 4 }}>F4 URL 预览</h2>
      <p className="studio-muted" style={{ marginBottom: 16 }}>{label}</p>
      <label className="studio-field">
        <span className="studio-sr">视频链接</span>
        <textarea readOnly value="https://www.youtube.com/watch?v=example" style={{ width: '100%', minHeight: 44 }} />
      </label>
      {children}
    </div>
  )
}

function App() {
  if (scene === 'need-install') {
    return (
      <Frame label="无平台字幕 → 需先安装本地转写（下载前）">
        <UrlPreview
          preview={needInstall}
          needsTranscriptionInstall
          onInstallTranscription={() => {}}
          onConfirm={() => {}}
          onDismiss={() => {}}
        />
      </Frame>
    )
  }
  if (scene === 'visual') {
    return (
      <Frame label="无音轨 → 视觉路线">
        <UrlPreview preview={visual} onConfirm={() => {}} onDismiss={() => {}} />
      </Frame>
    )
  }
  return (
    <Frame label="有平台字幕，不需要本地转写">
      <UrlPreview preview={platformSub} onConfirm={() => {}} onDismiss={() => {}} />
    </Frame>
  )
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)
