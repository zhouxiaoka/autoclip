"""Configuration sync compatibility service.

The previous desktop build had a dedicated client-to-backend config sync
service. Current code still imports it, so this small implementation provides
the same surface while using the project data directory as the source of truth.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from backend.core.path_utils import get_data_directory

logger = logging.getLogger(__name__)


class ConfigSyncService:
    def __init__(self):
        data_dir = get_data_directory()
        self.client_config_path = data_dir / "settings.json"
        self.backup_config_path = data_dir / "settings.backup.json"

    def get_client_config_timestamp(self) -> Optional[float]:
        if not self.client_config_path.exists():
            return None
        return self.client_config_path.stat().st_mtime

    def get_backup_config_timestamp(self) -> Optional[float]:
        if not self.backup_config_path.exists():
            return None
        return self.backup_config_path.stat().st_mtime

    def is_sync_needed(self) -> bool:
        client_time = self.get_client_config_timestamp()
        if client_time is None:
            return False
        backup_time = self.get_backup_config_timestamp()
        return backup_time is None or client_time > backup_time

    def sync_from_client(self) -> bool:
        if not self.client_config_path.exists():
            return False

        try:
            with open(self.client_config_path, "r", encoding="utf-8") as source:
                data = json.load(source)
            self.backup_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.backup_config_path, "w", encoding="utf-8") as target:
                json.dump(data, target, ensure_ascii=False, indent=2)
            return True
        except Exception as exc:
            logger.warning("同步客户端配置失败: %s", exc)
            return False


config_sync_service = ConfigSyncService()
