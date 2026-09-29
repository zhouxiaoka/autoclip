import { forwardRef, useEffect, useImperativeHandle, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import api from '../../services/api'
import { studioApi, errorText } from '../studio/api'
import type { AnalysisPreferences } from '../studio/types'

type Mode = AnalysisPreferences['analysis_mode']
interface VisionView { mode: 'text_model' | 'custom'; model: string; source: string; configured: boolean }

export interface AnalysisVisionHandle { save: () => Promise<void> }

// 三种方式把「效果 / 花费 / 适合」写清楚，让用户自己权衡；图片 token 远多于文字，不藏着
const MODES: Array<{ value: Mode; title: () => string; body: () => string; cost: () => string; fit: () => string }> = [
  { value: 'auto', title: () => t('智能选择（推荐）'), body: () => t('先看字幕；字幕不够时（没对白、游戏录屏）再抽几张画面判断。'), cost: () => t('花费中等，只在需要时看画面'), fit: () => t('不确定素材类型时选这个') },
  { value: 'subtitle', title: () => t('字幕分析'), body: () => t('只读字幕文字，找观点、金句和话题。'), cost: () => t('花费最低'), fit: () => t('适合访谈、讲解、直播等有人说话的视频') },
  { value: 'visual', title: () => t('视觉分析'), body: () => t('抽样画面和字幕一起理解，动作、表情、画面高光更准。'), cost: () => t('花费最高：图片消耗的 token 通常是字幕的数倍'), fit: () => t('适合游戏、运动、没有对白的视频') },
]

/**
 * 分析方式。能不能看画面由「模型」里选的模型决定（多模态 / 仅文字），这里不再单独配置视觉模型。
 * 选「智能 / 视觉」即同意在需要时发送抽样画面；想完全不看画面选字幕分析。
 */
const AnalysisVisionSettings = forwardRef<AnalysisVisionHandle, { multimodal: boolean | null }>(({ multimodal }, ref) => {
  useTranslation()
  const [mode, setMode] = useState<Mode>('auto')
  const [legacy, setLegacy] = useState<VisionView | null>(null)
  const [followModel, setFollowModel] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let live = true
    studioApi.analysisPreferences().then((p) => { if (live) setMode(p.analysis_mode) }).catch((e) => live && setError(t(errorText(e))))
    api.get<unknown, VisionView>('/studio/vision-settings')
      .then((v) => { if (live && v.mode === 'custom' && v.configured) setLegacy(v) })
      .catch(() => undefined)
    return () => { live = false }
  }, [])

  useImperativeHandle(ref, () => ({
    save: async () => {
      await studioApi.saveAnalysisPreferences({ analysis_mode: mode, allow_visual_screening: mode !== 'subtitle' })
      if (followModel) {
        await api.put('/studio/vision-settings', { mode: 'text_model' })
        setLegacy(null)
        setFollowModel(false)
      }
    },
  }), [mode, followModel])

  // 旧版单独配了视觉接口的，继续用它看画面，除非用户选择改为跟随模型
  const legacyActive = !!legacy && !followModel
  const canSee = legacyActive ? true : multimodal
  const note = mode === 'subtitle'
    ? t('不会发送任何画面。')
    : canSee === false
      ? (mode === 'visual'
        ? t('当前模型只能处理文字，视觉分析用不了。换一个标着「多模态」的模型，或改选智能 / 字幕分析。')
        : t('当前模型只能处理文字，智能选择会只用字幕。换成多模态模型后才会在需要时看画面。'))
      : t('需要时会发送抽样画面，按模型服务商计费。')

  return (
    <>
      <div className="ac-mode-cards" role="radiogroup" aria-label={t('分析方式')}>
        {MODES.map((m) => (
          <button key={m.value} type="button" role="radio" aria-checked={mode === m.value} className="ac-mode-card" onClick={() => setMode(m.value)}>
            <b>{m.title()}</b>
            <span>{m.body()}</span>
            <small className="cost">{m.cost()}</small>
            <small>{m.fit()}</small>
          </button>
        ))}
      </div>
      <p className="ac-note">{note}</p>
      {legacyActive && legacy && (
        <p className="ac-note">
          {t('看画面目前用的是之前单独配置的')} <span className="ac-mono">{legacy.model}</span>{legacy.source === 'environment' ? t('（来自环境变量）') : ''}。
          {' '}<a className="ac-link" onClick={() => setFollowModel(true)}>{t('改为使用上面的模型')}</a>
        </p>
      )}
      {followModel && <p className="ac-note">{t('保存后，看画面将使用上面选的模型。')}</p>}
      {error && <p className="studio-error" role="alert">{error}</p>}
    </>
  )
})

export default AnalysisVisionSettings
