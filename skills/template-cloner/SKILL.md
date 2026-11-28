---
name: template-cloner
description: >-
  将一条爆款切片参考视频（.mp4/.mov）、几张小红书/抖音截图，或风格需求描述，
  逆向拆解并克隆成符合 AutoClip TemplateSpec v2 契约的动态成片模板包，
  完成安全与契约校验、一键热安装到本机 AutoClip，或打包发布到 GitHub Releases catalog.json。
  当用户说「克隆这个视频样式」「扒一下这条切片模板」「做一个类似小红书/访谈风格的成片模板」时使用。
---

# AutoClip Template Cloner：参考视频 → 可热更新成片模板

把任意爆款切片样式（如小红书技术访谈、播客金句、街头快剪、双语演讲）逆向还原成**确定性、离线安全、可热更新**的 AutoClip 模板包，无需修改任何 AutoClip 源码或重新发版。

开始写模板前，先快速查阅 [references/spec-v2-cheatsheet.md](references/spec-v2-cheatsheet.md) 里的 `TemplateSpec v2` 字段与 `window.setData` 数据结构。

---

## 工作流（5 步闭环）

### 第 1 步：抽取参考帧与元信息

用户提供本地参考视频或截图时，先运行抽帧分析脚本：

```bash
python scripts/template_cloner.py extract-ref /path/to/reference.mp4 --out /tmp/ref_work --frames 6
```

如果用户发的是多张截图：

```bash
python scripts/template_cloner.py extract-ref /path/to/shot1.png /path/to/shot2.png --out /tmp/ref_work
```

用图像查看工具读取输出的 `contact_sheet.jpg`（或各张 `frame_*.jpg`）和 `reference_brief.json`。

### 第 2 步：按 7 个维度拆解视觉语法

不要凭感觉写样式，逐项把参考画面的视觉语法映射到 AutoClip 的声明式契约：

1. **画布与构图（`base.framing` / `head_zone` / `zoom`）**：满屏人像（`full_face`）、画框窗口（`window`）还是方形（`square`）？镜头是缓慢推进（`creep`）还是节拍跳切（`step` + `step_window: true`）？
2. **调色与底部暗角（`base.grade` / `base.scrim`）**：冷调、暖胶片还是高对比？底部字幕区是否需要渐变暗角衬托（用 `base.scrim` 声明，由 FFmpeg 单帧循环合成，不要在 CSS 里做大面积模糊）。
3. **进度条（`base.progress_bar`）**：是否有底部/边距进度条？用 `progress_bar` 声明高度（偶数像素）、边距、颜色和透明度，由 FFmpeg 随视频时钟驱动，避免每帧重绘 PNG。
4. **字幕排版与分页（`caption_layout`）**：字号（`font_px`）、左右留白（`inset_px`）、短屏分句（`grouped_screen`）还是逐句（`phrase` / `sentence`）、中英双语对齐方式（`synced` / `per_cue` / `sentence_screens`）。
5. **关键词高亮与色彩系统（`style.css` + `template.js`）**：主字幕颜色、强调词高亮色（`seg.hl` / `seg.key`）、描边/阴影/胶囊底色、英文字幕层级。
6. **辅助包装元素（`overlay.slots` & `fields.optional`）**：顶部 `kicker` 标签、讲者名片（`speakers`）、数字弹卡（`numbers`）、术语注释卡（`gloss`）。注意成片默认不烧入封面大标题（由 `paint_fill` 清空 `title_lines`）。
7. **平台安全区与避脸铁律（`overlay.safe_area`）**：小红书（`xiaohongshu`）、抖音（`douyin`）、TikTok（`tiktok`）等，确保口播字幕严格落入**避脸安全区**（`y: 1220..1520` 或头顶 `y: 160..320`），**严禁**在清晰人脸上直接盖大字；只有配合 FFmpeg 时间轴虚化（`base.grade: "gblur=sigma=14:enable='lt(t,1.35)'"`）或全屏纯色节奏插卡时，才允许短暂居中放巨幅标题。
8. **3 层本地 ONNX 人像景深（`1.6.3+` 可选，「大字穿人像背后」）**：
   - 在 `template.yaml` 中声明 `base.subject_layer: true`、`overlay.back_entry: back.html`、`meta.min_app_version: "1.6.3"`；
   - `back.html` + `back.js` 渲染在人物头肩**背后**（建议放在发际线景深带 `y=505..535`，保证上部 75%~80% 清晰可读、底部被发丝自然遮挡），且必须**随每句口播动态进场 → 停留 → 淡出**，不要常驻死字；
   - `index.html` + `template.js` 渲染在人物**前景**安全区字幕与标签。
9. **包装引擎 v2：品牌变量 & `ACMotion` 原子动效库（`1.6.4+` 推荐）**：
   - 在 `template.yaml` 顶层声明 `variables:`（支持 `kind: color | number | boolean | select`，如 `accent_color`、`font_scale` (`S/M/L`)、`depth_enabled`），用户选中模板后即可在单行工具条实时改色/调字号/开关景深，渲染前引擎自动注入 `fill.vars`；
   - 共享 SDK `./ac-template-sdk.js` 内置 `window.ACMotion` 原子动效套件（`springPop` / `blurIn` / `clipWipe` / `kineticSlam` / `staggerIndex` / `chunkCaption` / `safeBands` / `renderVignette` / `renderGrain` / `getVar`），以及面向 GSAP 模板的 `ACMotion.bindTimeline(tl)` 确定性暂停时间轴桥接（`motion_runtime: gsap`）。
   - 支持 `.zip` 模板包标准互传：用户可在 AutoClip 桌面端模板栏直接点击「导入模板包」导入 `.zip`，或在已安装模板下点击「导出」分享给他人。

### 第 3 步：生成骨架并编写模板

先用模板工厂生成标准骨架目录（slug 仅允许小写字母、数字、下划线或连字符，2–32 字符）：

```bash
python scripts/template_factory.py scaffold <slug> \
  --name-zh "中文风格名" \
  --name-en "English Style Name" \
  --desc-zh "一句话中文适用场景" \
  --desc-en "One-line English description" \
  --out ./custom_templates
```

再按第 2 步的拆解结果编辑生成的 4 个文件（脚手架已自动内嵌共享 SDK `./ac-template-sdk.js`，可直接调用 `ACTemplate.momentAt / moments / zhHtml / enText / activeGloss / occupiedRects / labels`）：
- `template.yaml`：声明 `caption_layout`、`base.scrim`、`base.progress_bar`、`base.grade`、`meta`（3D 景深模版加 `base.subject_layer: true` 与 `overlay.back_entry: back.html`）
- `index.html`：透明背景 `1080×1920` 舞台，仅引用本地 `./style.css` 和 `./template.js`（可捆绑 OFL 开源 `.ttf` 字体到 `./fonts/`）
- `style.css`：严格确定性样式（**禁止 `@keyframes`、`animation:`、外部 `http(s)://` 字体/图片**）
- `template.js`（及可选 `back.js`）：必须暴露 `window.setData(fill)`、`window.renderFrame(seconds)` 和 `window.occupiedRects()`（**禁止 `Math.random`、`Date.now`、`performance.now`、`fetch(`、`XMLHttpRequest`、`WebSocket`**）：
  - **空帧兜底**：`renderFrame(seconds)` 在无字幕的静默帧也必须返回非空字符串（例如 `return capD || 'IDLE'`），否则采集器会判定截屏失败；
  - **时间轴字段**：`ACTemplate.moments(state)` 返回的每条 cue 起止时间字段是 `t0` / `t1`（兼容 `start` / `end`）；
  - **SVG 字体引号**：在 SVG 字符串中写 `font-family` 属性时，内部字体名用单引号（如 `var SANS = "'ACSpace', Inter, sans-serif"`），避免嵌套双引号导致 XML 静默回退为默认衬线体。

### 第 4 步：自动化校验并热安装到本机 AutoClip

```bash
python scripts/template_factory.py verify ./custom_templates/<slug>
python scripts/template_cloner.py install-local ./custom_templates/<slug>
```

安装完成后，模板已原子写入 `<AUTOCLIP_DATA_DIR>/templates/<slug>/`：
- 无需重启或重编桌面端，AutoClip 的风格选择器、`GET /api/v1/studio/templates`、CLI `--template <slug>` 和 MCP `list_styles` / `start_quick_output` 会立即识别并可直接出片。

### 第 5 步：打包并发布到云端目录（可选）

要把新模板推送给所有 AutoClip 用户热更新：

```bash
python scripts/template_factory.py pack ./custom_templates/<slug> --out ./dist-templates
python scripts/template_factory.py build-catalog ./dist-templates \
  --base-url "https://github.com/zhouxiaoka/autoclip-templates/releases/download/<tag>" \
  --out ./dist-templates/catalog.json
```

或将模板文件夹合入仓库后，直接触发 GitHub Actions 工作流 `.github/workflows/publish-templates.yml` 自动校验、打包并发布 Release。
