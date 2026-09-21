# 官网与桌面端八语支持

2026-09-21：桌面分支 `codex/eight-languages` 基于 `codex/observability-i18n`，保留 Sentry、源码映射上传及 PostHog V2 的已有改动。官网独立仓库的分支为 `codex/website-eight-languages`。

## 语言与行为

- 简体中文 `zh`、英语 `en`、日语 `ja`、韩语 `ko`、西班牙语 `es`、巴西葡萄牙语 `pt`、俄语 `ru`、法语 `fr`。
- 桌面首次启动按系统偏好语言列表选择支持的语言；均不支持时使用英语。`zh-TW` 暂使用简体中文，`pt-PT` 暂使用巴西葡语，西语各地区使用通用表达。
- 顶栏语言选择器含「跟随系统」，手动偏好保存在 `autoclip.language`。切换即时生效，不重载页面、不重置尚未保存的表单，也不更改素材。
- 表单组件（Ant Design）、相对日期（dayjs）、本地时间格式和原生托盘跟随界面语言。托盘在 WebView 初始化前暂显示英语，初始化完成后同步所选语言。
- 官网保留既有中英日韩文案，新增西葡俄法。URL `?lang=es` 优先于已保存偏好和浏览器语言，手动切换同时更新可分享的 URL。

## 翻译范围和边界

桌面每种语言有 618 条资源，覆盖当前路由实际加载的首页、链接/文件导入、分类、处理阶段、项目详情、切片和合集、标题编辑、导出、Bilibili 账号/投稿界面、反馈、模型设置、Whisper、隐私开关及错误边界。官网每种语言有 89 条主文案，以及导航辅助标签。

项目名、用户视频标题、字幕、生成内容、模型标识和 URL 保留原文。后端和第三方返回的诊断原文、日志、外部文档、GitHub/飞书表单仍以原服务提供的语言展示；界面语言不改变 LLM 提示词或生成内容的语言，也不改变语音识别的自动语言检测。未挂载的旧演示页面不在这次产品界面覆盖范围内。

文案已做关键流程与术语校对，尚未经过每种语言的母语用户审校。可按真实用户反馈继续调整措辞。

## 维护

- 字典：`frontend/src/i18n/locales/{zh,en,ja,ko,es,pt,ru,fr}.json`。当前使用中文原文作为稳定键，`keySeparator` 和 `nsSeparator` 关闭。
- 渲染：组件调用 `useTranslation()` 订阅语言变化，再用统一 `t()` 获取当前文案。模块级展示配置使用 getter，避免首次加载时固定语言。
- 可变量使用插值；数量展示使用“标签：数量”避免拼接不同语言的量词。用户数据只作为 React 文本渲染，不用 `innerHTML`。
- `language.ts` 管理检测和持久化，原生托盘文案在 `src-tauri/src/tray.rs`。
- 不翻译状态枚举、API 参数键、模型 ID、统计事件名称等协议值。
- 新增 UI 文案必须同步八份字典；CI 检查键一致性、变量一致性和静态调用缺失。

## 验证记录

- 桌面：原有 17 项 Sentry/PostHog 检查和 5 项国际化检查；typecheck、lint、生产前端构建通过。
- Rust：macOS 上 `cargo check --offline` 通过，使用已有 macOS 26.5 SDK。
- 浏览器：生产前端配只读模拟 API，逐一切换八语；模型设置、Whisper、项目详情、合集创建与导出对话框正常。未保存表单值在语言切换后保留，刷新后语言偏好保留，用户原始标题不变。
- 官网：三项运行时/资源检查通过；版本同步脚本覆盖八语版本文案；八语在桌面与约 400 CSS 像素宽度下无横向溢出。
- 原生托盘的实际点击、Windows 安装包及真实视频全流程尚未在本次回归中重测。
- 八语已合入 v1.3.1 发布分支。前端验证构建关闭遥测凭据和源码映射上传；发布时继续使用已有 CI secrets 及 Sentry 构建检查。

## 本地检查

```bash
cd frontend
npm ci
npm run typecheck
npm run lint
node --test tests/*.test.cjs
SENTRY_UPLOAD_SOURCEMAPS=false npm run build
```

官网：`node --test scripts/i18n.test.cjs`。官网仍为零构建静态页面，现有 Release 自动同步脚本继续适用。
