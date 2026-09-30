# 多模型配置指南（兼容入口）

本页保留已有链接；当前说明统一维护在 [AI 模型配置](AI_MODEL_CONFIGURATION.md)。支持的服务商、环境变量与模型以该指南、设置页和 [env.example](../env.example) 为准。

Python 提供商 SDK 已包含在锁定版本的 `requirements.txt` 中，不需要单独运行安装脚本：

```bash
python -m pip install -r requirements.txt
```

源码启动见 [STARTUP_GUIDE.md](../STARTUP_GUIDE.md)，容器部署见 [DOCKER.md](../DOCKER.md)。不要使用旧指南里的 `python backend/main.py`，也不要另行无约束升级 SDK。
