# 开发快速开始（兼容入口）

当前源码环境、Redis、启动和停止命令统一维护在 [STARTUP_GUIDE.md](../STARTUP_GUIDE.md)。桌面安装见 [用户安装指南](USER_INSTALLATION_GUIDE.md)，容器部署见 [DOCKER.md](../DOCKER.md)，桌面打包见 [BUILD_GUIDE.md](../BUILD_GUIDE.md)。

前端依赖在 `frontend/` 执行 `npm ci`，Python 依赖以根目录 `requirements.txt` 为准。根目录不再维护另一套 Node/Tauri CLI 依赖。
