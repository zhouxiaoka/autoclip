# 完成通知和修改记录

Q4、Q9。默认全部关闭。统计关闭时不发这些事件。本机把「制作完成时通知」打开后，结果页仍会提示，但不会因为统计关闭就去请求开关。

## 开关

| 开关 | 默认 | 打开后 |
|---|---|---|
| `notify_on_done` | `false` | 第一条成片做好、整次制作结束、制作失败时，结果页写一行说明。系统允许通知时再发一条系统通知，并在桌面端尝试设置角标 |
| `track_overrides` | `false` | 记录用户改掉的自动决定 |

分组只有在开关被真正赋值（本机覆盖、远程、开发变量或未过期缓存）之后才发新事件。

## 和方案的差别

- 方案里的系统通知写的是 Tauri 通知插件。桌面壳仍是 Tauri 2.0.0-rc，这个环境不能编译壳，也没有现成的通知插件。通知走网页 `Notification`，桌面端在已有的窗口接口上调用 `setBadgeCount`。调用失败就忽略，结果页那一行仍然在。没有做 Dock 角标的真机验证。
- `digest` 是关注频道的早晨汇总，这次没有关注频道，所以不发 `kind=digest`。
- 部分完成和全部完成都用 `kind=all_done`。白名单里没有单独的 partial。
- 打开一个已经做完的项目不会补发通知。只有先看到这次制作还在进行，之后状态变了，才通知一次。
- 统计关闭时，后台观察器不轮询。通知跟结果页的刷新走；统计开着时，已经登记的制作在离开页面后仍由观察器补发。
- 方案写 Q9 不需要开关。这次任务要求每一项默认关闭，所以修改记录用 `track_overrides`。
- 导入页改平台只发一次 `field=platform`。`remember_platforms` 或 `track_overrides` 任一已赋值就发，两个都开也不会记两遍。
- 编辑器保存时才记标题、版式、时长、删片段、换片段。只改顺序、只改简介或话题，不记。
- 「没导出」是离开这个项目（或关掉页面）时记一次，不是每个片段一次。片段标识不能进事件。还在制作、一条成片都没有、或者这次已经复制或下载过，都不记。进入同一项目的编辑器不算离开。
- 没有在 PostHog 里创建远程开关，也没有 validation 环境的真实事件截图。

## 事件

| 事件 | 何时 | 属性 |
|---|---|---|
| `notification_sent` | 需要通知，且 `notify_on_done` 已赋值 | `kind`=`first_clip` / `all_done` / `failed`，`permission`=`granted` / `denied` / `default` |
| `notification_opened` | 用户点了系统通知 | 同上，此时 `permission=granted` |
| `studio_auto_choice_overridden` | 改了自动决定，且对应开关已赋值 | `field`=`platform` / `title` / `layout` / `duration` / `clip_delete` / `clip_swap` / `not_exported`，`stage`=`pre_import` / `editor` / `results_chip` |

通知正文是固定的一句，不含标题、路径或项目标识。

查询见 `ux_notify.sql`。
