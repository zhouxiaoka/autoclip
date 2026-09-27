# Windows connection reset 修复（待发布）

日期：2026-09-27；问题：[PYTHON-FASTAPI-3](https://autoclip-ts.sentry.io/issues/PYTHON-FASTAPI-3)。

## 证据与范围

正式后端 `autoclip-backend@1.4.0` 最近 7 天查询快照为 121 次，均为同一错误组、desktop 环境；该组跨版本累计约 9,079 次，不能将累计数当成 1.4.0 的次数或用户数。验收版本 `1.4.0-telemetry-validation` 不在此统计中。数据会继续变化。

代表事件堆栈为 `events.py:_run` → `proactor_events.py:165:_call_connection_lost`。桌面包固定 CPython 3.13.13；同一标准库实现中第 165 行调用 socket.shutdown。原实现若在这里抛出 ConnectionResetError，会跳过 close、server._detach 和 _called_connection_lost 标记。测试调用真实标准库 transport 配合模拟 reset socket，已复现这一清理中断。

尚不能由脱敏堆栈确定具体请求、用户操作、影响人数或业务任务失败率，也不能把模拟复现视为已复现原用户完整操作。

## 修复

在桌面应用创建时，仅对 Windows CPython 3.13 安装一个兼容补丁，保持原 Proactor 清理顺序，只容忍 shutdown 本身的 ConnectionResetError，随后执行关闭和解绑。协议回调错误（包括 ConnectionResetError）及其他 shutdown 错误仍抛出。保留 Proactor 与异步子进程能力，未修改 Sentry 过滤规则。

补丁依赖 CPython 私有 transport 方法，升级打包 Python 时必须重新审查；3.14 等其他版本不安装此补丁。参考 [CPython 标准库实现](https://github.com/python/cpython/blob/v3.13.13/Lib/asyncio/proactor_events.py)。

## 验证与发布前检查

- 本地后端全量：631 passed、1 skipped（Windows IOCP 集成测试在 macOS 跳过），33 条既有弃用告警；隔离数据目录，禁用 Sentry DSN。定向测试 12 passed。
- 覆盖原实现清理中断、修复后关闭/解绑/幂等、正常/已关闭 socket/pipe、协议异常保留、未知异常保留、平台与版本范围。
- 独立 Windows CI 使用与安装包相同的 Python 版本 3.13.13（GitHub Actions 分发，非最终便携安装包）：20 次真实 TCP RST、服务器关闭完成、无事件循环未处理异常，以及异步子进程输出。[CI run 36308742972](https://github.com/zhouxiaoka/autoclip/actions/runs/36308742972) 在修复提交 `c6979acf` 上 **13 passed，无跳过**。
- 发布前仍需 Windows 安装包冒烟：启动、导入/制作、取消与退出、重新打开；CI 不能替代 Tauri/WebView2 真机链路。
- 小版本发布后按新 release 观察此错误是否复发，并对照 Studio 失败事件。当前没有发布、打 tag 或手动关闭 Sentry issue。
