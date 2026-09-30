# 快速出片重构进度

本记录在每个独立工作包完成时更新。工作分支：`worktree-project-diagnosis`。主计划：[快速出片与平台策略重构计划](../../../../.claude/plans/nifty-purring-hejlsberg.md)。

## 包 1：平台策略 registry 与旧预设兼容

状态：已完成，待合入。

### 完成内容

- 新增 `backend/services/platform_strategy.py`，作为平台输出策略唯一来源。
- 定义抖音、TikTok、Instagram Reels、YouTube Shorts、YouTube 长视频、B站、小红书和原画策略。
- 明确区分 `youtube_shorts` 与 `youtube_long`：两者可共用 YouTube 传输能力，但画幅、时长和视觉策略不同。
- `backend/services/publish_export.py` 的旧 `PRESETS` 改为 registry 的兼容投影，保留 `douyin`、`xiaohongshu`、`shorts`、`bilibili`、`original` 既有键。
- `backend/services/upload_post_publisher.py` 的旧默认预设判断改为读取 registry，不再维护第二份“竖屏平台”规则。
- 新增 `GET /studio/platform-strategies`，供后续首页平台选择器读取受控策略摘要。
- 新增 registry 单测与 Studio API 回归测试。

### 已验证

```text
/Users/zhoukk/autoclip/venv/bin/pytest \
  backend/tests/test_platform_strategy.py \
  backend/tests/test_publish_export.py \
  backend/tests/test_upload_post_publisher.py \
  backend/tests/test_studio.py -q

124 passed in 72.35s
```

```text
/Users/zhoukk/autoclip/venv/bin/ruff check \
  backend/services/platform_strategy.py \
  backend/tests/test_platform_strategy.py

All checks passed
```

### 兼容边界

- 不改变首页、导入、Studio 确认页或渲染行为。
- 历史发布请求未指定策略时，保持旧行为：含 Upload-Post 竖屏目标时默认 `shorts`，否则原画；B站独立为横屏策略。
- 没有新增账号、credits、自动发布或品牌片尾。

### 下一包

Studio v2 数据契约与自动编排：导入选择平台后，自动完成理解、候选草稿生成和渲染，结果页直接显示 OutputVariant；旧 `awaiting_confirmation` 项目继续兼容原流程。

### 主要风险

- 目前 registry 只统一“规则定义”，尚未让发布系统按不同 OutputVariant 分组上传。
- `youtube_long` 的 3 分钟以上要求是内容资格的软门槛，不能用导出层截断或填充处理；需要在候选生成层实现。
- 后续自动编排必须保证一次多平台请求只做一次理解，且单个 variant 失败不覆盖已完成结果。

## 包 2A：Studio v2 数据契约与兼容状态

状态：已完成，待合入。

### 完成内容

- `ImportOptions` 新增规范化的 `platforms`、显式 `auto_start`、`BrandingOptions`。
- 新增 `OutputVariant` 与 `AppendPlatformsRequest` 类型，为后续不可变交付版本和追加平台 API 准备契约。
- `/studio/import` 接收平台、自动启动和品牌片尾偏好，并将规范化结果写入项目设置与 Studio workspace。
- 新导入的 workspace 写入 `schema_version=2`、`generation` 与空的 `output_variants`；历史 workspace 读取时惰性补默认字段，不做强迁移。
- 仍保持 `auto_start=false` 默认值，筛查完成后继续进入旧的 `awaiting_confirmation` 流程；`generation.status` 与该旧状态同步。
- 修复 `jobs._analyze()` 失败路径的 Python 异常闭包错误：错误消息与诊断在异常作用域内固化，保证失败状态能持久化。

### 已验证

```text
/Users/zhoukk/autoclip/venv/bin/pytest \
  backend/tests/test_smart_import.py \
  backend/tests/test_studio.py \
  backend/tests/test_platform_strategy.py -q

154 passed in 84.65s
```

### 下一包

包 2B：仅在首页新客户端显式传 `auto_start=true` 时，自动从筛查进入理解、候选草稿、平台 variant 和渲染。需增加 output variant 聚合状态、单版本重试和历史确认流兼容回归。

### 主要风险

- 当前 `OutputVariant` 只是数据契约，尚未关联 render job 或用户可见结果卡，不能提前在 API/UI 暴露“追加平台”。
- 自动路径必须把理解、制作和渲染分成可恢复阶段，不能将一次 executor 中断误报为所有结果失败。
- 多平台必须共享理解结果；平台差异只在草稿派生与渲染阶段产生。
