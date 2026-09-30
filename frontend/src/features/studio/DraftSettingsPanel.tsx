import { Select, Switch } from 'antd'
import { t } from '../../i18n'
import { Btn, ProgressLine, Row, Segmented, StatusDot } from '../../ui'
import { CropPoint, Draft, FramingStatus, Scene, cropAt, frameModeAt, languages, shotIndexAt, subtitleStyles } from './types'
import { titlePresets, titleVersions, isArtworkStyle, titleDesignThumbnails } from './titlePresets'
import PackagingSettings from './PackagingSettings'

const ACCENT_DEFAULT: Record<string, string> = { comic: '#ffe52d', neon: '#ccff00', editorial: '#ff4826', pixel: '#ed327c', frosted: '#00e6dc' }

export interface FramingState {
  status?: FramingStatus
  /** Auto framing is running against the current scenes. */
  busy: boolean
  /** Set after a run: scenes with a track, shots found, and how many shots are shown whole. */
  result?: { framed: number; total: number; shots: number; fit: number }
  error?: string
}

/**
 * Right-hand settings of the Studio editor as one column of setting rows (see DESIGN.md → Row).
 * Top to bottom: name → subtitles (whole clip) → audio → frame + speaker framing → opening title
 * (optional, folded) → text language → cover. Everything has a working default.
 */
export default function DraftSettingsPanel({ draft, patch, scene, currentTime, onShot, framing, onAutoFrame, onInstallFraming, onPortrait, coverHref, onOpenCover }: {
  draft: Draft
  patch: (changes: Partial<Draft>) => void
  /** Scene currently shown in the preview; the framing slider edits this one. */
  scene?: Scene
  currentTime: number
  /** Change the shot under the playhead (position or crop/fit). */
  onShot: (sceneId: string, changes: Partial<CropPoint>) => void
  framing: FramingState
  onAutoFrame: () => void
  onInstallFraming: () => void
  onPortrait: () => void
  coverHref?: string
  onOpenCover: (href: string) => void
}) {
  const artwork = isArtworkStyle(draft.title_style)
  const style = draft.title_style || 'plain'
  const cropping = draft.aspect !== 'original' && draft.layout === 'crop'
  const sceneCrop = cropAt(scene, currentTime, draft.crop_x ?? .5)
  const tracked = !!scene?.crop_track?.length
  const shotMode = frameModeAt(scene, currentTime)
  const shotIndex = shotIndexAt(scene, currentTime)
  const runtime = framing.status?.status
  return <aside className="studio-edit-panel">
    <div className="studio-panel-head">
      <h2>{t("成片设置")}</h2>
      <Btn size="sm" variant="text" onClick={onPortrait}>{t("一键竖屏")}</Btn>
    </div>
    <div className="ac-rows">
      <Row stack label={t("成片名称")}>
        <input className="ac-input" aria-label={t("成片名称")} maxLength={200} value={draft.title} onChange={e => patch({ title: e.target.value })} />
      </Row>

      {!draft.packaging && <Row label={t("字幕")} hint={t("把字幕压进画面，整条成片统一样式。")}>
        <Switch size="small" checked={draft.subtitles} onChange={value => patch({ subtitles: value })} />
      </Row>}
      {!draft.packaging && draft.subtitles && <Row stack label={t("字幕样式")}>
        <div className="studio-tiles" role="radiogroup" aria-label={t("字幕样式")}>
          {subtitleStyles.map(preset => <button type="button" key={preset.value} className="studio-tile" role="radio" aria-checked={(draft.subtitle_style || 'clean') === preset.value} onClick={() => patch({ subtitle_style: preset.value })}>
            <span className="studio-tile-sample"><span className={`studio-caption studio-caption--${preset.value}`}>{t("这里是字幕效果")}</span></span>
            <span className="studio-tile-label">{t(preset.label)}</span>
          </button>)}
        </div>
      </Row>}

      <Row label={t("原声")} hint={t("关闭后成片静音。")}>
        <Switch size="small" checked={draft.original_audio} onChange={value => patch({ original_audio: value })} />
      </Row>

      <Row label={t("画幅")}>
        <Segmented size="sm" ariaLabel={t("画幅")} value={draft.aspect}
          options={[{ value: 'original', label: t("原画幅") }, { value: 'portrait', label: '9:16' }, { value: 'landscape', label: '16:9' }]}
          onChange={value => patch({ aspect: value, ...(value === 'portrait' ? { layout: 'crop' as const } : {}) })} />
      </Row>
      {draft.aspect !== 'original' && <Row label={t("构图")} hint={cropping ? t("主体铺满画面，自动对准说话的人。") : t("保留完整画面，两侧留边或模糊背景。")}>
        <Segmented size="sm" ariaLabel={t("构图")} value={draft.layout}
          options={[{ value: 'crop', label: t("满屏") }, { value: 'blur', label: t("模糊背景") }, { value: 'fit', label: t("留边") }]}
          onChange={value => patch({ layout: value })} />
      </Row>}
      {cropping && <Row stack label={t("取景")} hint={
        runtime === 'not_installed' ? t("首次使用需下载人物识别组件（约 {{size}} MB），之后按镜头自动对准说话的人；没有人物的画面（引用卡、PPT）会完整显示。", { size: framing.status?.size_mb ?? 45 })
        : runtime === 'installing' ? t("正在下载人物识别组件…")
        : framing.busy ? t("正在按镜头识别人物位置…")
        : framing.error ? framing.error
        : framing.result ? (framing.result.framed ? t("已按 {{shots}} 个镜头自动取景，{{fit}} 个没有人物的镜头改为完整显示。播放到某个镜头时可单独调整它。", framing.result) : t("没有识别到人物，请手动调整取景位置。"))
        : tracked ? t("按镜头跟随说话人取景；播放到某个镜头时可单独调整它。")
        : t("拖动调整当前镜头的取景位置。")}>
        {runtime === 'not_installed' && <Btn size="sm" onClick={onInstallFraming}>{t("下载并自动取景")}</Btn>}
        {runtime === 'installing' && <ProgressLine percent={framing.status?.progress ?? 5} />}
        {runtime === 'error' && <StatusDot tone="error" label={framing.status?.message} />}
        {runtime === 'installed' && !framing.busy && <Btn size="sm" onClick={onAutoFrame}>{framing.result ? t("重新自动取景") : t("自动取景")}</Btn>}
        {scene && <div className="studio-shot-controls">
          {tracked && <span className="studio-muted ac-mono">{t("镜头 {{n}}/{{total}}", { n: shotIndex + 1, total: scene.crop_track!.length })}</span>}
          <Segmented size="sm" ariaLabel={t("当前镜头显示方式")} value={shotMode} disabled={framing.busy}
            options={[{ value: 'crop', label: t("对准人物") }, { value: 'fit', label: t("完整画面") }]}
            onChange={value => onShot(scene.id, { mode: value })} />
        </div>}
        <input aria-label={t("取景位置")} type="range" min="0" max="1" step=".01" value={sceneCrop} disabled={framing.busy || shotMode === 'fit'}
          onChange={e => scene ? onShot(scene.id, { crop_x: Number(e.target.value) }) : patch({ crop_x: Number(e.target.value) })} />
      </Row>}

      {draft.packaging ? <PackagingSettings draft={draft} patch={patch} /> : <details className="ac-disclosure" open={!!draft.hook.trim() || undefined}>
        <summary>{t("片头文字（可选）")}</summary>
        <Row stack label={t("片头文字")} hint={t("在第一个镜头上显示最多 4 秒的大字，适合游戏、推广类内容；访谈、讲解可以留空。")}>
          <textarea className="ac-input ac-textarea" style={{ minHeight: 56 }} aria-label={t("片头标题文字")} maxLength={120} value={draft.hook} placeholder={t("例如：一个问题，或一句结论")} onChange={e => patch({ hook: e.target.value })} />
        </Row>
        {!!draft.hook.trim() && <>
          <Row stack label={t("片头样式")} hint={t("缩略图为设计参考，实际文字效果见左侧预览。")}>
            <div className="studio-tiles studio-tiles--3" role="radiogroup" aria-label={t("片头样式")}>
              {titlePresets.map(preset => <button type="button" key={preset.value} className="studio-tile" role="radio" aria-checked={style === preset.value}
                onClick={() => patch({ title_style: preset.value, title_template_version: isArtworkStyle(preset.value) ? 6 : 1, title_accent: null })}>
                {titleDesignThumbnails[preset.value]
                  ? <img className="studio-tile-image" src={titleDesignThumbnails[preset.value]} alt="" width={360} height={240} />
                  : <span className="studio-tile-sample studio-tile-sample--center"><span className={`studio-hook studio-hook--${preset.value}`}>{t("片头")}</span></span>}
                <span className="studio-tile-label">{t(preset.label)}</span>
              </button>)}
            </div>
          </Row>
          {artwork && <details className="ac-disclosure">
            <summary>{t("调整文字样式")}</summary>
            <Row label={t("样式版本")}>
              <Select aria-label={t("样式版本")} size="small" style={{ width: 160 }} value={draft.title_template_version ?? 1}
                options={titleVersions(draft.title_style).map(v => ({ value: v.value, label: t(v.label) }))}
                onChange={value => patch({ title_template_version: value as Draft['title_template_version'] })} />
            </Row>
            <Row label={t("强调色")}>
              <input type="color" aria-label={t("标题强调色")} value={draft.title_accent || ACCENT_DEFAULT[style] || '#dfff00'} onChange={e => patch({ title_accent: e.target.value })} />
            </Row>
            <Row stack label={t("文字大小")}>
              <input type="range" aria-label={t("文字大小")} min=".75" max="1.2" step=".05" value={draft.title_scale ?? 1} onChange={e => patch({ title_scale: Number(e.target.value) })} />
            </Row>
            <Row stack label={t("文字位置")}>
              <input type="range" aria-label={t("文字位置")} min=".06" max=".70" step=".01" value={draft.title_y ?? .12} onChange={e => patch({ title_y: Number(e.target.value) })} />
            </Row>
            {!['pixel', 'frosted'].includes(style) && <Row label={t("入场动效")} hint={t("翻译与动效以渲染结果为准；支持手动换行。")}>
              <Switch size="small" checked={draft.title_motion ?? true} onChange={value => patch({ title_motion: value })} />
            </Row>}
          </details>}
        </>}
      </details>}

      {!draft.packaging && <Row label={t("文字语言")} hint={t("选择翻译语言后，渲染时会翻译片头文字与字幕。")}>
        <Select aria-label={t("文字语言")} size="small" style={{ width: 140 }} value={draft.language}
          options={languages.map(l => ({ value: l.value, label: l.value === 'source' ? t('原语言') : l.label }))}
          onChange={value => patch({ language: value as Draft['language'] })} />
      </Row>}
      <Row label={t("封面")} hint={coverHref ? t("发布时按平台生成带标题的封面，也可以用视频截帧。") : t("导出成片后，在发布页生成带标题的封面。")}>
        {coverHref && <Btn size="sm" variant="text" onClick={() => onOpenCover(coverHref)}>{t("去生成")}</Btn>}
      </Row>
    </div>
  </aside>
}
