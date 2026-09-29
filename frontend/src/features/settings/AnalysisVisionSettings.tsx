import { forwardRef, useEffect, useImperativeHandle, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Input, Switch } from 'antd'
import { t } from '../../i18n'
import api from '../../services/api'
import { observeStudioOperation } from '../../analytics/studio'
import { Btn, Row, Segmented, StatusDot } from '../../ui'
import { studioApi, errorText } from '../studio/api'
import type { AnalysisPreferences } from '../studio/types'

type Mode = AnalysisPreferences['analysis_mode']
type VisionMode = 'text_model' | 'custom'
interface VisionView {
  mode: VisionMode; base_url: string; model: string; timeout: number; source: string
  has_key: boolean; configured: boolean; verified: boolean
}

export interface AnalysisVisionHandle { save: () => Promise<void> }

// 三种方式把「效果 / 费用 / 适合」说清楚，让用户自己权衡；图片 token 远多于文字，不能藏着
const MODES: Array<{ value: Mode; title: () => string; body: () => string; cost: () => string; fit: () => string }> = [
  { value: 'subtitle', title: () => t('字幕分析'), body: () => t('只读字幕文字，找观点、金句和话题。'), cost: () => t('花费最低'), fit: () => t('适合访谈、讲解、直播等有人说话的视频') },
  { value: 'auto', title: () => t('智能选择'), body: () => t('先看字幕；字幕不够时（没对白、游戏录屏）再抽几张画面确认。'), cost: () => t('花费中等，只在需要时看画面'), fit: () => t('不确定素材类型时的推荐选项') },
  { value: 'visual', title: () => t('视觉分析'), body: () => t('抽样画面和字幕一起理解，动作、表情、画面高光更准。'), cost: () => t('花费最高：图片消耗的 token 通常是字幕的数倍'), fit: () => t('适合游戏、运动、没有对白的视频') },
]

const AnalysisVisionSettings = forwardRef<AnalysisVisionHandle, { onBeforeTest: () => Promise<boolean> }>(({ onBeforeTest }, ref) => {
  useTranslation()
  const [prefs, setPrefs] = useState<AnalysisPreferences>({ analysis_mode: 'subtitle', allow_visual_screening: false })
  const [vision, setVision] = useState<VisionView | null>(null)
  const [visionMode, setVisionMode] = useState<VisionMode>('text_model')
  const [custom, setCustom] = useState({ base_url: '', model: '', key: '' })
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null)
  const [error, setError] = useState('')

  const loadVision = async () => {
    const v = await api.get<unknown, VisionView>('/studio/vision-settings')
    setVision(v)
    setVisionMode(v.mode)
    if (v.mode === 'custom') setCustom({ base_url: v.base_url, model: v.model, key: '' })
  }

  useEffect(() => {
    let live = true
    studioApi.analysisPreferences().then((p) => { if (live) setPrefs(p) }).catch((e) => live && setError(t(errorText(e))))
    loadVision().catch((e) => live && setError(t(errorText(e))))
    return () => { live = false }
  }, [])

  const visionBody = () => visionMode === 'custom'
    ? { mode: 'custom', base_url: custom.base_url.trim(), model: custom.model.trim(), api_key: custom.key.trim() || null, timeout: vision?.timeout || 180 }
    : { mode: 'text_model', timeout: vision?.timeout || 180 }

  useImperativeHandle(ref, () => ({
    save: async () => {
      await studioApi.saveAnalysisPreferences(prefs)
      // 字幕分析用不到视觉；只有选了用画面的方式才保存视觉配置
      if (prefs.analysis_mode !== 'subtitle' || visionMode !== vision?.mode) {
        if (visionMode === 'custom' && (!custom.base_url.trim() || !custom.model.trim())) throw new Error(t('请填写视觉模型的接口地址和模型名称'))
        const saved = await observeStudioOperation('vision_provider_save', () => api.put<unknown, VisionView>('/studio/vision-settings', visionBody()))
        setVision(saved)
        setCustom((c) => ({ ...c, key: '' }))
      }
    },
  }), [prefs, visionMode, custom, vision])

  const runTest = async () => {
    setTesting(true); setTestResult(null); setError('')
    try {
      // 复用文本模型时，测的是已保存的模型：先把上面的模型设置存下来
      if (visionMode === 'text_model' && !(await onBeforeTest())) return
      const r = await observeStudioOperation('vision_provider_test', () => api.post<unknown, { model?: string }>('/studio/vision-settings/test', visionBody(), { timeout: ((vision?.timeout || 180) + 10) * 1000 }))
      setTestResult({ ok: true, text: t('可以看图') + (r.model ? ` · ${r.model}` : '') })
      await loadVision()
    } catch (e) {
      setTestResult({ ok: false, text: t(errorText(e)) })
    } finally {
      setTesting(false)
    }
  }

  const usesVision = prefs.analysis_mode !== 'subtitle'
  const status = testResult
    ? <StatusDot tone={testResult.ok ? 'ok' : 'error'} label={testResult.text} />
    : vision?.verified && visionMode === vision.mode
      ? <StatusDot tone="ok" label={<>{t('可以看图')} · <span className="ac-mono">{vision.model}</span></>} />
      : <StatusDot tone="muted" label={t('还没测试过能否看图')} />

  return (
    <>
      <div className="ac-mode-cards" role="radiogroup" aria-label={t('分析方式')}>
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={prefs.analysis_mode === m.value}
            className="ac-mode-card"
            onClick={() => setPrefs({ analysis_mode: m.value, allow_visual_screening: m.value === 'subtitle' ? false : prefs.allow_visual_screening })}
          >
            <b>{m.title()}</b>
            <span>{m.body()}</span>
            <small className="cost">{m.cost()}</small>
            <small>{m.fit()}</small>
          </button>
        ))}
      </div>
      <p className="ac-note">{t('费用按你配置的模型服务商计费。先用字幕分析跑通，再按素材决定要不要让 AI 看画面。')}</p>

      {usesVision && (
        <div className="ac-rows">
          <Row label={t('导入时视觉初筛')} hint={t('导入后先抽几张画面判断适合做什么，会产生一次视觉调用费用。关闭时确认后才开始正式分析。')}>
            <Switch checked={prefs.allow_visual_screening} onChange={(on) => setPrefs({ ...prefs, allow_visual_screening: on })} />
          </Row>
          <Row label={t('看画面用的模型')} hint={visionMode === 'text_model' ? t('默认直接用上面的模型，不用再配一遍。模型不支持图片时，再另选一个。') : t('填写支持图片输入的 OpenAI 兼容接口。')}>
            <Segmented size="sm" ariaLabel={t('看画面用的模型')} value={visionMode} onChange={(v) => { setVisionMode(v); setTestResult(null) }}
              options={[{ value: 'text_model', label: t('同上面的模型') }, { value: 'custom', label: t('另选') }]} />
          </Row>
          {visionMode === 'custom' && (
            <>
              <Row wide label={t('接口地址')}>
                <Input className="ac-mono" placeholder="https://…/v1" value={custom.base_url} onChange={(e) => { setCustom({ ...custom, base_url: e.target.value }); setTestResult(null) }} />
              </Row>
              <Row wide label="API Key" hint={vision?.has_key && vision.mode === 'custom' ? t('已配置；留空保留已有密钥') : undefined}>
                <Input.Password className="ac-mono" autoComplete="new-password" placeholder={vision?.has_key && vision.mode === 'custom' ? t('已配置 · 输入可替换') : 'sk-…'} value={custom.key} onChange={(e) => { setCustom({ ...custom, key: e.target.value }); setTestResult(null) }} />
              </Row>
              <Row wide label={t('模型')}>
                <Input className="ac-mono" placeholder={t('例如 doubao-seed-2-1-pro-260915')} value={custom.model} onChange={(e) => { setCustom({ ...custom, model: e.target.value }); setTestResult(null) }} />
              </Row>
            </>
          )}
          <Row label={t('图片理解测试')} hint={t('发送一张内置测试图，不发送你的素材。')}>
            {status}
            <Btn size="sm" loading={testing} onClick={() => void runTest()}>{t('测试图片理解')}</Btn>
          </Row>
        </div>
      )}
      {error && <p className="studio-error" role="alert">{error}</p>}
    </>
  )
})

export default AnalysisVisionSettings
