# 导入流程开关

Q1、Q2、Q3、Q8 和首页拖放区。默认全部关闭。统计关闭时不发这些事件。

## 开关

| 开关 | 默认 | 行为 |
|---|---|---|
| `remember_platforms` | 关 | 记住上次平台。第一次按界面语言：中文是小红书和抖音，其他语言是 TikTok。选择器收成一行。 |
| `one_click_paste_start` | `button` | `autostart` 时，粘贴或拖入 HTTPS 的 B 站 / YouTube 链接，或拖入视频文件，3 秒后开始。期间可以撤销。 |
| `link_import_without_whisper` | 关 | 链接导入不再因为本地转写没装好而被拦住。文件导入仍然要转写或 SRT。打开后，若本机还没装 Whisper，会在后台开始安装，不挡住这一次导入。 |
| `import_drop_zone` | 关 | 首页改成居中的拖放区，链接和文件放在一起。 |
| `hide_legacy_entrypoints` | 关 | 智能项目里隐藏「调整制作方案」、新建合集和导出确认。高级偏好改到设置。经典项目的「开始处理」保留。 |

`platform_source=accounts` 留在枚举里。导入页目前没有一份可靠的「已连接发布账号」列表，这次不据此推断平台。

链接是否真的带平台字幕，前端在提交前不知道。开关打开后放行链接，事件里的 `transcription_route=platform_subs` 表示「这次没拦住本地转写，交给后端先找平台字幕」。

## 事件

只在对应开关真正分配到（远程、缓存、开发覆盖或本机覆盖）之后发送。

| 事件 | 属性 |
|---|---|
| `studio_one_click_started` | `trigger`、`platform_count`、`platform_source`、`has_subtitle`、`transcription_route`、`flow_id` |
| `studio_one_click_undone` | `trigger` |
| `studio_auto_choice_overridden` | `field=platform`、`stage=pre_import` |
| `studio_legacy_entry_used` | `legacy_action` |

不上传链接、文件名、标题或偏好里的自由文本。
