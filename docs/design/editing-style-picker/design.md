# AutoClip 导入页剪辑风格选择器 · 产品设计方案 v0.1（待 Charlie 审）

> 对应 PR #317 的 `TemplatePicker.tsx`（现在是三个纯文字按钮：杂志风 / 街头快剪 / 经典，挂在 `pkg_templates_v1` 后面，默认值写死为 editorial）。这份方案审过后才交给研发。

## 1. 目标
- **一眼看懂**：用真实成片的画面说明每个模板的效果，不靠文字描述。
- **主动+智能**：系统先推荐好模板，并给出一句推荐理由。用户什么都不点也能直接出片，想换只需点一下。
- **丝滑**：悬停后 100ms 内有反馈，切换没有卡顿，布局不跳；低配 Windows 也要流畅。
- **可控**：功能放在开关后面，埋点齐全，可以灰度上线、做 A/B。

非目标：模板市场、自定义模板、给每个片段单独选模板（放到后续版本）。

## 2. 用户流程
1. 用户粘贴链接或拖入视频，前端先显示三张卡，内容是海报帧（poster）。
2. 源分析完成后（一般 ≤ 2 秒，复用现有探测：画面类型、人数、语速、字幕语言），推荐卡上出现「✦ 推荐」角标，卡片下方出现一句推荐理由，同时自动选中这张卡。
   - 分析结果出来之前先预选杂志风；真实推荐一到，选中态就平滑滑到推荐的那张卡上。用户已经手动选过的话，就不再覆盖。
3. 用户可以把鼠标悬停在卡上或用 Tab 聚焦，看 2.5 秒的循环预览；点击或按 Enter/Space 选中，用 ←/→ 方向键切换。
4. 选了非推荐模板后，理由那一行变成「已改为街头快剪 · 推荐是杂志风，[恢复推荐]」。
5. 点「开始出片」后，所选模板随导入一起提交（沿用 `html_template` 字段）。

点击次数：采纳推荐 0 次，改选 1 次。

## 3. 布局方案
| 方案 | 说明 | 优点 | 缺点 |
|---|---|---|---|
| **A. 横排三张 9:16 卡片（推荐）** | 导入框下面并排三张 200×356 的卡 | 三个模板能直接比较；当前只有 3 个模板，刚好放下；做起来简单 | 模板超过 5 个要改成横向滚动 |
| B. 大预览加缩略条 | 左边一个大的 9:16 预览，右边是小缩略图列表 | 预览清楚，模板多了也能扩展 | 只能看一个，不方便比较；占的高度大 |
| C. 收起的推荐条 | 只显示一行「推荐：杂志风 [更换]」，点开是抽屉 | 最省空间，最「主动」 | 模板不容易被发现，用户会以为没得选；改选要多点一次 |

**推荐 A**。窗口宽度小于 900px 时，卡宽缩到 160px；模板超过 5 个时改成横向滚动，并加上左右箭头。C 可以留作以后「连续导入多次的熟练用户」的折叠模式。

## 4. 卡片结构
- **缩略图**：9:16，圆角 10px，`object-fit: cover`，默认显示 poster。
- **预览**：悬停、聚焦或选中时，在 poster 上叠一层 `<video muted loop playsinline>`，循环 2.5 秒。底部 3px 进度条用强调色。右下角放「▶ 2.5s」小标，提示可以预览。
- **推荐角标**：左上角，「✦ 推荐」，强调色 #FF5A36，只给一张卡。
- **名称 + 单选圆点**：名称 15px 粗体，右侧是单选指示。
- **一句话描述**：12.5px 弱色字，格式是「视觉特征 · 适用场景」，最多 18 个字。
- **推荐理由**：放在卡片下方，一句话（≤ 40 字），由后端规则生成，不写在卡片里。

## 5. 状态
| 状态 | 表现 |
|---|---|
| 默认 | 只显示 poster，没有描边，只有一层很淡的阴影 |
| 悬停 / 聚焦 | 卡片上浮 3px，加阴影，开始播放预览；聚焦时再加 2px 焦点环 |
| 选中 | Liquid Glass 玻璃透镜衬在卡片后面（见第 14 节），卡片放大到 1.02 倍，玻璃单选点亮起 ✓，预览保持循环 |
| 禁用（导入中） | 整体不透明度 0.5，不响应悬停，`aria-disabled` |
| 加载（推荐计算中） | 角标位置显示骨架闪烁，理由行显示「正在分析素材…」 |
| 开关关闭 | 完全保持现在的版式，不渲染选择器，也不发 `html_template` |
| 减少动态效果 | 不自动播放，不做位移动画；在 poster 上放一个「预览」按钮，点了才播放 |
| 预览加载失败 | 停在 poster，不报错，只打一个埋点 |
| Intel Mac（intel_mac_unverified） | 选择器照常显示，下方加一行提示「本机暂用经典包装」 |

## 6. 动效与性能（丝滑要求）
- **悬停 < 100ms 出反馈**：poster 一直在显示，悬停后马上上浮并开始 `video.play()`。视频已经预加载过，所以首帧应在 100ms 内出来；首帧没到之前继续显示 poster，不出现黑屏。
- **布局零跳动**：缩略图容器固定宽高比（`aspect-ratio: 9/16`），视频绝对定位叠在上面；角标和理由行预留高度，内容晚到也不会把布局撑开（CLS = 0）。
- **选中过渡**：描边、阴影和单选点的过渡时长 180ms，曲线 `cubic-bezier(.2,.8,.2,1)`。只动 transform、opacity、box-shadow，不改宽高。
- **预加载**：选择器挂载后，在 `requestIdleCallback` 里按顺序预加载「推荐卡 → 可见卡」的 webm（`preload="auto"`），总共不超过 600KB。屏幕外的卡（以后模板多了会有）只在 IntersectionObserver 判断进入视口后才加载。
- **低配 Windows**：预览固定为 216×384、24fps、VP9 约 250kbps，解码开销很低。同一时间最多播放 2 个视频（悬停的 + 选中的）；不可见或窗口失焦时 `pause()`；不加 CSS 滤镜和 backdrop-filter。
- **键盘**：用 ←/→ 切换选中（roving tabindex），焦点跟着移动；切换时预览从第 0 秒开始播，过渡同样是 180ms。
- **减少动态效果**：`prefers-reduced-motion` 生效时，关掉自动播放和位移，只保留描边颜色变化。
- **性能验收**：在 2 vCPU 的 Windows 云机上，连续快速悬停切换 20 次，Performance 面板里不应出现超过 50ms 的长任务，帧率不低于 55fps。

## 7. 预览素材规格
- **来源**：直接用 #316 的金样渲染（template-goldens）生成，保证预览和真实成片一模一样。每个模板截一段 2.5 秒最有代表性的片段（含标题出场和字幕高亮）。
- **产物**（每个模板一套）：`<id>.poster.webp`（270×480，≤ 30KB），`<id>.preview.webm`（VP9，216×384，24fps，2.5 秒，无音频，≤ 120KB），另配一个 `<id>.preview.mp4`（H.264）作为不支持 webm 时的兜底。三个模板加起来 ≤ 500KB。
- **生成方式**：写一个脚本 `scripts/build_template_previews`，从金样渲染出发，用 ffmpeg 生成上面的产物，并在 CI 里检查体积。模板一改，素材自动重新生成。
- **打包**：放进应用资源目录，离线可用，不走 CDN。**已定（Charlie，10/10）**：预览素材用 Jensen Huang 和马斯克访谈的真实渲染帧（来源：packaging-benchmark/renders/out、xhs-batch2/musk_*）。
- 本次样稿用的是现有渲染（Jensen 访谈）。其中「经典」那张是拿 pod_clip1 裁成竖版代替的，不代表最终素材。

## 8. 无障碍
- 选择器整体是 `role="radiogroup"`，每张卡是 `role="radio"`，带 `aria-checked`，用方向键导航。
- 推荐理由行用 `aria-live="polite"`，推荐结果到达时读出来。
- 视频设为 `aria-hidden`，卡片的可读名称形如「杂志风，推荐，衬线大标题，适合坐姿访谈」。
- 浅色和深色主题下，文字对比度都要 ≥ 4.5:1；焦点环始终可见。

## 9. 多语言
- 名称、描述、理由全部走 i18n key（`editing_style.editorial.name/desc` 等，分组标题用 `editing_style.title`：中文「剪辑风格」，英文「Editing style」），覆盖现有的 7 种语言。推荐理由用模板句加槽位拼出来（比如 `reason.seated_interview`），不在前端拼中文。
- 不同语言的字长差别大，描述行最多两行，超出加省略号；卡片高度固定。

## 10. 埋点（PostHog）
| 事件 | 属性 |
|---|---|
| `studio_template_picker_shown` | recommended, reason_code, flag_variant, source_kind, latency_ms（推荐耗时） |
| `studio_template_preview_played` | template, trigger(hover/focus/keyboard/button), first_frame_ms, is_recommended |
| `studio_template_overridden`（已有） | from_template, to_template, recommended, stage, input(mouse/keyboard) |
| `studio_template_restore_recommended` | from_template |
| `studio_template_preview_failed` | template, error_kind |
| `generation_finished` / download / share（已有） | 补上 recommended_template 和 accepted_recommendation |

核心指标：推荐采纳率、改选率、改选后的下载/分享率对比、预览首帧 P95。Sentry 打 `phase=template_picker` 标签，不带路径。

## 11. 开关
- `pkg_templates_v1` 不变，管整个模板功能。
- 新增 `pkg_template_picker_visual`，灰度可视化选择器。关掉时退回 #317 现在的文字版，方便做 A/B 对比采纳率。
- 两个开关都要在 PostHog 里建好（目前都还没建）。`autoclip_safe_mode` 打开时，两个开关一起压成关。

## 12. 研发验收标准
1. 开关关闭时，导入页和现在逐像素一致，请求里不带 `html_template`。
2. 开关打开、不做任何操作，推荐模板被提交；推荐理由能显示出来；推荐超过 3 秒没回来时退回默认值，而且不会覆盖用户已经做的选择。
3. 每张卡都有 poster；悬停后预览首帧 P95 < 100ms（素材已预加载的情况下），CLS = 0。
4. 选中过渡 150–200ms；全程只用键盘（Tab、←/→、Enter）就能完成选择。
5. 减少动态效果模式下没有自动播放。屏幕外或窗口失焦时视频暂停；同一时间最多 2 个视频在播。
6. 2 vCPU Windows 上快速切换 20 次：没有超过 50ms 的长任务，帧率 ≥ 55fps。
7. 预览素材由脚本从金样生成，总体积 ≤ 500KB，CI 检查体积；断网时也能正常显示。
8. 浅色和深色主题都过对比度检查。PR 里附四张截图（浅色/深色 × 默认/改选），再附一段 10 秒操作录屏。
9. 第 10 节的埋点全部能在 PostHog 里看到，属性完整。

## 13. 样稿
- `mockups/picker-light.png`、`mockups/picker-dark.png`：默认状态，推荐杂志风。
- `mockups/picker-dark-hover.png`：悬停在街头快剪上，预览进度条走了 60%。
- `mockups/picker-light-override.png`：改选街头快剪后，出现「恢复推荐」。
- `mockups/hover-select.mp4`：默认 → 悬停预览 → 选中的过程，用静态帧拼成，只示意节奏，不代表真实帧率。

## 14. Liquid Glass 选中态（v2）
**依据**：
- Apple HIG · Materials：https://developer.apple.com/design/human-interface-guidelines/materials
- WWDC25「Meet Liquid Glass」：https://developer.apple.com/videos/play/wwdc2025/219/
- WWDC25「Build a SwiftUI app with the new design」：https://developer.apple.com/videos/play/wwdc2025/323/
- Adopting Liquid Glass：https://developer.apple.com/documentation/TechnologyOverviews/adopting-liquid-glass

**要点**：
- Liquid Glass 用在交互控件这一层，不用在内容层。所以玻璃只用来做「选中指示器」，缩略图本身保持原样，不加玻璃。
- 用 Regular 这个变体就够了。
- 系统里的分段控件在切换时会把指示器「变形」滑到新位置，对应的是 glassEffectID 做的 morph 效果。
- 必须适配三项系统设置：减少透明度、增强对比度、减少动态效果。

**视觉**：
- 一块透明的玻璃透镜衬在选中卡后面，比卡片四周各大 14px，圆角 30px。
- 顶边一道高光，左上角一抹弧形反光。
- 外面一圈淡淡的强调色光晕，蓝色 #0A84FF，扩散约 40px。
- 选中的卡放大到 1.02 倍，并略微浮起。
- 单选点做成玻璃小圆片：没选中时是半透明白，选中时填满强调色渐变，打 ✓。
- 「推荐」角标也是玻璃小胶囊。
- 页面整体改成 Apple 风格：背景 #F5F5F7（浅色）/ #000（深色），去掉多余描边，层次靠留白和柔和阴影区分；标题 34px 粗体，字距收紧到 -0.02em；主按钮是蓝色胶囊。

**CSS 做法**：
- 透镜是一个单独的 `.lens` 元素，绝对定位在卡片行的底层。
- 材质：`backdrop-filter: blur(24px) saturate(180%)`；背景是一层 160° 的线性渐变（高光色 → 半透明 → 半透明 → 微亮）；再叠 `box-shadow` 组合：`inset 0 1px 0` 做顶边高光，`inset 0 0 0 .5px` 做镜边，外加投影和强调色光晕；`:after` 用一个 radial-gradient 做弧形反光。
- 切换时，透镜用 `transform: translateX()` 滑到目标卡，时长 320ms，曲线 `cubic-bezier(.3,1.3,.5,1)`，带一点点回弹，像分段控件那样。卡片本身的缩放用 200ms。（样稿里为了方便用的是 left，实现时请改成 transform，走 GPU 合成。）

**降级**：
- 用 `@supports not (backdrop-filter: blur(1px))` 检测不支持的环境；另外，在低端机（第一次滑动时测出掉帧，或 `navigator.hardwareConcurrency <= 2`）上也走降级。降级做法：去掉模糊，换成实色半透明层（浅色 rgba(255,255,255,.85)、深色 rgba(44,44,46,.9)），保留高光和光晕。
- 减少透明度（`prefers-reduced-transparency`）时，用实色加 1px 边。
- 增强对比度（`prefers-contrast: more`）时，用 2px 强调色边。
- 减少动态效果时，透镜直接跳到目标位置，不滑动、不回弹。
- 整个页面只有一块透镜用 backdrop-filter，严格控制模糊面积。

样稿：`mockups/v2/picker-light.png`、`picker-dark.png`、`picker-dark-hover.png`、`picker-light-override.png`（源文件 `mock2.html`）。

## 15. 嵌入现有导入页（v3）
依据：`CreativeImport.tsx`（#317 的 head 是 d6b56f6c）以及 #317 里的截图。不新建页面，也不新增导航。

**页面原有内容全部保留，顺序不变**：标题「放入视频，直接生成可发布成片。」→ 链接导入/文件导入切换 → 链接输入框或文件选择 → 「准备发布到哪里？」平台多选 → **剪辑风格**（替换 #317 的纯文字版选择器，位置不变）→「有特别要求？（选填）」→ 底栏：「会按所选平台自动制作…」+「高级偏好」+「生成成片」。

**各状态**：
1. **还没放入素材**：剪辑风格这一节只占一行标题、一行说明，下面一个虚线提示条：「放入链接或文件后，这里会出现三种剪辑风格的预览，并自动选好最合适的一种」。这样页面高度几乎不变，用户也知道这里会有东西。
2. **已放入链接或文件，正在轻量探测**：输入框下方出现一行「已识别：频道 × 嘉宾 · 时长 · 画面类型 · 字幕」。探测用链接元数据、前几秒画面和已有字幕，不跑完整分析（完整分析仍然在点「生成成片」之后）。同时三张卡出现，先显示 poster，杂志风预选。
3. **探测完成**：选中态滑到推荐的卡，打上「✦ 推荐」角标；卡片下方出现玻璃质感的理由条：「推荐理由：检测到…，衬线标题更显质感。不满意可直接点选其他风格。」探测失败的话就维持预选杂志风，理由条写「默认推荐，可按需切换」。
4. **用户改选**：理由条变为「已选街头快剪 · 推荐的是杂志风 [恢复推荐]」。

**有哪些变化**：
- 原来横排三格的纯文字按钮，换成 150×267 的竖版缩略卡，靠左紧凑排列，选中态用玻璃透镜。
- 「竖版版式」下拉框的逻辑沿用 #317：只有选「经典」时才出现，并放在理由条下方。
- 只选了 B 站、YouTube 视频或「原版」这类不需要竖版包装的平台时，整节剪辑风格隐藏，和 #317 现有逻辑一致。
- 开关关闭时，页面恢复成原来的「竖版版式」下拉框，和现在的截图一致。
- 「生成成片」按钮和底栏完全不动；不管有没有探测结果，都可以随时点。

**需要研发补的**：一个轻量的推荐接口 `POST /studio/template-recommend`，输入 url 或文件头部，返回 `{template, reason_code, signals}`，P95 要在 2 秒以内，超时就用默认值。理由文案前端用 i18n 模板来渲染。

**经典的缩略图**：原渲染是 1:1 的，改成 9:16 竖版——上下用同一帧模糊压暗做背景，正方形画面完整居中，字幕不被裁掉，这也和经典样式竖版成片的实际观感一致。

**样稿**：`mockups/v3/import-empty-light.png`、`import-empty-dark.png`、`import-picker-light.png`、`import-picker-dark.png`（源文件 `mock3.html`）。
