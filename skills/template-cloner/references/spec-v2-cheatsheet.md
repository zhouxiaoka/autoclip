# AutoClip TemplateSpec v2 速查表

## 1. 安全与确定性红线（违反会被 `registry.load_folder` 直接拒绝）

- 画布尺寸固定 `1080×1920`、`30fps`、`aspects: [portrait]`。
- 目录必须包含：`template.yaml`、`index.html`、`style.css`、`template.js`，且 `template.yaml` 里的 `id` 必须与目录名完全一致。
- `template.js` 必须定义：
  - `window.setData(fill)`
  - `window.renderFrame(seconds)` → 返回当前画面状态哈希字符串（相同状态不重复截图，大幅提速）
  - `window.occupiedRects()` → 返回 `[{x, y, w, h}, ...]`
- **严禁出现**：`Date.now`、`performance.now`、`fetch(`、`XMLHttpRequest`、`WebSocket`、`importScripts`、`sendBeacon`、`@keyframes`、`animation:`、任何外部 `http://` / `https://` 资源引用（SVG `xmlns` 除外）。
- `progress_bar.height` 必须是**偶数像素**（`yuva420p` 要求）。

---

## 2. `template.yaml` 核心声明块

```yaml
id: xhs_tech_card
version: 2
name: {zh: "极客干货", en: "Tech Card"}
fit:
  formats: {sit_down_interview: 1.0, keynote_stage: 0.85, podcast_studio: 0.7}
  needs_face: true
canvas: {aspects: [portrait], overlay_px: [1080, 1920], fps: 30}
base:
  framing: full_face          # full_face | window | square
  face_y: 0.38                # 0..1，人脸目标纵坐标比例
  head_zone: [260, 860]       # [top, bottom] px，人脸保护区
  zoom:
    mode: creep               # creep | step
    creep: 0.04
    intro: {from: 1.06, dur: 0.8}
  transitions: {broll: cut, max: 1}
  grade: "eq=contrast=1.04:saturation=1.02"
  step_window: false          # true 时 crop 模式启用节拍裁切窗口
  scrim: {enabled: true, height: 840, color: "0x0E1014", mid_stop: 0.4, mid_alpha: 0.32, bottom_alpha: 0.76}
  progress_bar: {enabled: true, height: 4, inset_x: 48, y_from_bottom: 72, color: "0x5A8BFF@0.9"}
overlay:
  entry: index.html
  slots:
    hook: {top: 180, alt_top: 180}
    subtitle: {top: 1500, max_rows: 2}
  safe_area: xiaohongshu      # xiaohongshu | douyin | tiktok | instagram_reels | youtube_shorts
  limits: {emphasis_gap_s: 3.0}
fields:
  required: [title_lines, cues]
  optional: [kicker, emphasis, numbers, gloss, speakers]
audio: {bgm: none}
cover: {layout: xhs_tech_card_3x4, from_overlay: true}
caption_layout:
  font_px: 48                 # 用于计算每行 CJK 字符预算
  inset_px: 64                # 左右边距 px
  source_limit: 34            # 英文原句预算
  paging_mode: phrase         # phrase | grouped_screen | sentence
  screen_chars: null          # grouped_screen 时可限制单屏字数（如 8）
  screen_sec: null            # grouped_screen 时可限制单屏时长（如 2.6）
  hold_slack: 0               # 短闪句合并容忍字数
  bilingual_align: per_cue    # synced | per_cue | sentence_screens
  strip_speaker_prefix: false # true 时去除字幕里的「讲者：」前缀
  en_key_propagates: true     # 英文关键词命中时是否同步高亮中文
meta:
  desc: {zh: "适合小红书技术访谈与干货观点切片", en: "Clean bilingual tech talk style"}
  tags: [tech, interview, bilingual]
  category: interview
  order: 50
  package_version: "1.0.0"
  preview_layout: blur
qa: {}
```

---

## 3. `window.setData(fill)` 常见字段结构

```js
{
  kicker: "AI ENGINEER CODE",     // 顶部小标签（可选）
  deck: "",                       // 副标题说明（可选）
  moments: [
    {
      t0: 0.2,                    // 出现时间（秒）
      t1: 2.6,                    // 结束时间（秒）
      speaker: "Lauren Tan",      // 当前讲者（可选）
      zh: [
        { s: "核心不是生成代码，", t0: 0.2, t1: 1.4, key: false, acc: false, hl: "" },
        { s: "而是验证代码。",     t0: 1.4, t1: 2.6, key: true,  acc: false, hl: "验证代码" }
      ],
      en: [                       // 英文词用字段 w（不是 s）
        { w: "The", t0: 0.2, t1: 0.4, key: false },
        { w: "bottleneck", t0: 0.4, t1: 0.9, key: true }
      ]
    }
  ],
  cards: [                        // 数字卡 / 术语卡（gloss / numbers）
    { kind: "gloss", t0: 1.0, t1: 4.0, term: "Harness", note: "约束 Agent 的自动化测试与门禁环境" }
  ]
}
```
