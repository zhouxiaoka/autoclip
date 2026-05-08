"""
桌面模式Celery配置
使用SQLite作为Broker和Backend，适合单机桌面应用
"""
import os

if os.getenv("AUTOCLIP_DESKTOP_MODE", "").lower() not in {"1", "true", "yes"}:
    raise RuntimeError("此模块仅在桌面模式下可用")

from celery import Celery
from pathlib import Path

# 文件系统 broker + sqlite backend（示例）
app_dir = Path(os.getenv("AUTOCLIP_APP_DIR", "~/Library/Application Support/AutoClip")).expanduser()
app_dir.mkdir(parents=True, exist_ok=True)

# 创建Celery目录
celery_dir = app_dir / "celery"
celery_dir.mkdir(parents=True, exist_ok=True)
(celery_dir / "in").mkdir(exist_ok=True)
(celery_dir / "out").mkdir(exist_ok=True)
(celery_dir / "processed").mkdir(exist_ok=True)

celery_app = Celery(
    "autoclip_desktop",
    broker="filesystem://",
    backend=f"db+sqlite:///{app_dir}/celery/results.sqlite3",
)

celery_app.conf.update(
    broker_transport_options={"data_folder_in": str(app_dir / "celery" / "in"),
                              "data_folder_out": str(app_dir / "celery" / "out"),
                              "data_folder_processed": str(app_dir / "celery" / "processed")},
    task_ignore_result=False,
)

if __name__ == '__main__':
    celery_app.start()
