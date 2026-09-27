# 前端历史代码清理与导出重构

日期：2026-09-21。分支：`codex/visual-game-ads`。重构前提交：`cc0a2fb4`。

## 完成范围

基于现有三条路由清理没有进入应用的代码，保留当前用户流程，为后续交互设计提供更小的维护范围。

- 删除 50 个历史文件，共 12547 行：未路由的演示/旧页面、重复合集弹窗、未接入的进度/账号/投稿组件、旧 UI primitives，以及失去引用的辅助模块和样式。
- 从切片卡中分离 `features/exports/ClipExportDialog.tsx`、`useClipExport.ts` 和 `pollExportJob.ts`，分别负责面板、任务状态与轮询。
- 页面卸载会中止前端轮询、等待定时器和在途查询；迟到响应不会再更新进度。后台渲染不会因此取消。保留原有一秒轮询、最多 180 次的观察窗口。
- 移除 10 个仅被旧 UI 引用的直接依赖。锁文件移除 46 个包条目，保留包版本没有升级；npm 同时补齐 6 个已有 Tailwind WASM 可选依赖树条目。
- 删除同名 `apiConfigCheck.ts` / `.tsx`：原主路径实际加载 `.ts` 的直接放行实现，`.tsx` 的配置检查未生效。删除并不表示新增配置校验；已更正界面审计中的描述。

## 验证

- TypeScript 模块解析追踪从 `src/main.tsx` 出发，覆盖静态导入、再导出和字符串动态导入。清理后 43 个 TS/TSX 文件中 42 个可达；唯一不在导入图中的是应保留的环境声明 `vite-env.d.ts`。
- `npm run lint`、`npm run typecheck`、`npm run build` 均通过。构建仍有现存的大 chunk 提示。
- `npm test`：7 项回归测试通过，覆盖排队到完成、渲染失败、观察超时、请求前取消、在途取消、等待期间取消和网络异常。
- 使用只读示例接口在浏览器复查首页、项目页、单片导出面板及合集预览；导出平台可切换，字幕与标题卡选项仍在，合集排序/增删入口仍在。
- 浏览器验证未连接真实视频媒体或提交渲染任务，不能替代真实导入→分析→渲染的端到端测试。依赖验证复用本机已安装依赖，未执行全新安装。

## 后续设计边界

当前交互基线见 [界面与交互拆解](CURRENT_UI_INTERACTION_AUDIT.md)。语言配置、独立成片工作区、广告创意对象和统一导出尚待基于该基线设计。此提交不改变后端路由、模型流水线或其他工作区中的更新/Sentry 等改动。

现有可见的「投稿」按钮仍为开发中提示；删除的是无法被用户打开的旧投稿面板，不能将本次清理理解为实现了发布能力。

## 删除清单

以下均可从重构前提交恢复：

- `frontend/src/assets/background.svg`
- `frontend/src/components/AccountHealthMonitor.tsx`
- `frontend/src/components/BilibiliAccountManager.tsx`
- `frontend/src/components/BilibiliManager.css`
- `frontend/src/components/BilibiliManager.tsx`
- `frontend/src/components/ClipDetailModal.tsx`
- `frontend/src/components/CollectionPreviewModal_fixed.tsx`
- `frontend/src/components/CookieHelper.tsx`
- `frontend/src/components/DesktopSettings.tsx`
- `frontend/src/components/FirstRunWizard.tsx`
- `frontend/src/components/InlineProgressBar.tsx`
- `frontend/src/components/NotificationList.tsx`
- `frontend/src/components/OfflineModeIndicator.tsx`
- `frontend/src/components/PipelineControl.tsx`
- `frontend/src/components/ProjectStatusIndicator.tsx`
- `frontend/src/components/RealTimeStatus.tsx`
- `frontend/src/components/SimpleProgressBar.tsx`
- `frontend/src/components/SimpleProjectCard.tsx`
- `frontend/src/components/TaskProgress.tsx`
- `frontend/src/components/TaskProgressDisplay.tsx`
- `frontend/src/components/TaskProgressModal.tsx`
- `frontend/src/components/UploadModal.tsx`
- `frontend/src/components/UploadQueueManager.tsx`
- `frontend/src/components/UploadTaskManager.tsx`
- `frontend/src/components/UploadToBilibili.tsx`
- `frontend/src/components/clipcard.module.css`
- `frontend/src/components/ui/alert.tsx`
- `frontend/src/components/ui/badge.tsx`
- `frontend/src/components/ui/button.tsx`
- `frontend/src/components/ui/card.tsx`
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/label.tsx`
- `frontend/src/components/ui/progress.tsx`
- `frontend/src/components/ui/select.tsx`
- `frontend/src/components/ui/slider.tsx`
- `frontend/src/components/ui/switch.tsx`
- `frontend/src/config/bilibiliPartitions.ts`
- `frontend/src/hooks/useFirstRun.ts`
- `frontend/src/hooks/useNotifications.ts`
- `frontend/src/hooks/useTaskProgress.ts`
- `frontend/src/lib/utils.ts`
- `frontend/src/pages/DebugPage.tsx`
- `frontend/src/pages/ProcessingPage.tsx`
- `frontend/src/pages/SimpleProgressDemo.tsx`
- `frontend/src/pages/UploadStatusPage.tsx`
- `frontend/src/services/uploadApi.ts`
- `frontend/src/utils/apiConfigCheck.ts`
- `frontend/src/utils/apiConfigCheck.tsx`
- `frontend/src/utils/apiUtils.ts`
- `frontend/src/utils/statusUtils.tsx`
