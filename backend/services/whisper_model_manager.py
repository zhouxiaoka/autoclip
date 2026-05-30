"""
Whisper 模型管理服务（mlx-whisper）

负责 mlx-community Whisper 模型的下载、状态检查、删除。模型从 HuggingFace 拉取，
统一缓存到 `<data_dir>/whisper-models`（由 whisper_runtime 设置 HF_HOME）。
依赖（huggingface_hub）来自运行时安装目录，所有相关 import 都延迟到函数内。
"""
import logging
import threading
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from . import whisper_runtime

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    AVAILABLE = "available"      # 运行时就绪、可下载
    DOWNLOADING = "downloading"  # 下载中
    DOWNLOADED = "downloaded"    # 已下载
    ERROR = "error"              # 错误（通常是运行时未安装）
    NOT_FOUND = "not_found"


@dataclass
class ModelInfo:
    name: str
    size: str
    size_bytes: int
    description: str
    accuracy: str
    speed: str
    status: ModelStatus
    repo_id: str = ""
    download_progress: Optional[int] = None
    local_path: Optional[str] = None
    error_message: Optional[str] = None


# 模型名 -> HuggingFace 仓库 + 展示信息（faster-whisper / CTranslate2 模型）
_MODELS = {
    "tiny": {
        "repo_id": "Systran/faster-whisper-tiny",
        "size": "~75 MB", "size_bytes": 75 * 1024 * 1024,
        "description": "最快，准确度较低，适合快速预览", "accuracy": "较低", "speed": "最快",
    },
    "base": {
        "repo_id": "Systran/faster-whisper-base",
        "size": "~145 MB", "size_bytes": 145 * 1024 * 1024,
        "description": "平衡之选，推荐日常使用", "accuracy": "中等", "speed": "快",
    },
    "small": {
        "repo_id": "Systran/faster-whisper-small",
        "size": "~488 MB", "size_bytes": 488 * 1024 * 1024,
        "description": "较好准确度，适合重要内容", "accuracy": "较好", "speed": "中等",
    },
    "medium": {
        "repo_id": "Systran/faster-whisper-medium",
        "size": "~1.5 GB", "size_bytes": 1500 * 1024 * 1024,
        "description": "高准确度，适合专业用途", "accuracy": "高", "speed": "较慢",
    },
    "large-v3": {
        "repo_id": "Systran/faster-whisper-large-v3",
        "size": "~3 GB", "size_bytes": 3000 * 1024 * 1024,
        "description": "最高准确度", "accuracy": "最高", "speed": "最慢",
    },
}


def repo_id_for(model_name: str) -> Optional[str]:
    cfg = _MODELS.get(model_name)
    return cfg["repo_id"] if cfg else None


class WhisperModelManager:
    def __init__(self):
        self.model_configs = _MODELS
        # model_name -> {"status","progress","error"}
        self._download_state: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    # ---- 路径 / 状态 ----
    def _model_cache_dir(self, model_name: str) -> Path:
        repo = self.model_configs[model_name]["repo_id"]
        # HF 缓存目录命名：models--<org>--<name>
        return whisper_runtime.get_models_dir() / "hub" / ("models--" + repo.replace("/", "--"))

    def _is_downloaded(self, model_name: str) -> bool:
        d = self._model_cache_dir(model_name)
        snaps = d / "snapshots"
        return snaps.exists() and any(snaps.iterdir())

    def _check_model_status(self, model_name: str) -> ModelStatus:
        with self._lock:
            st = self._download_state.get(model_name)
        if st and st.get("status") == "downloading":
            return ModelStatus.DOWNLOADING
        if st and st.get("status") == "error":
            return ModelStatus.ERROR
        if self._is_downloaded(model_name):
            return ModelStatus.DOWNLOADED
        if not whisper_runtime.is_installed():
            return ModelStatus.ERROR  # 运行时没装，模型也用不了
        return ModelStatus.AVAILABLE

    def _info(self, model_name: str) -> ModelInfo:
        cfg = self.model_configs[model_name]
        status = self._check_model_status(model_name)
        with self._lock:
            st = self._download_state.get(model_name, {})
        return ModelInfo(
            name=model_name,
            size=cfg["size"], size_bytes=cfg["size_bytes"],
            description=cfg["description"], accuracy=cfg["accuracy"], speed=cfg["speed"],
            status=status, repo_id=cfg["repo_id"],
            download_progress=st.get("progress"),
            local_path=str(self._model_cache_dir(model_name)) if status == ModelStatus.DOWNLOADED else None,
            error_message=st.get("error"),
        )

    def get_all_models_info(self) -> List[ModelInfo]:
        return [self._info(name) for name in self.model_configs]

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        if model_name not in self.model_configs:
            return None
        return self._info(model_name)

    # ---- 下载（后台线程，非阻塞）----
    async def download_model(self, model_name: str) -> bool:
        if model_name not in self.model_configs:
            raise ValueError(f"不支持的模型: {model_name}")
        if not whisper_runtime.is_installed():
            raise RuntimeError("请先安装 Whisper 运行时")
        if self._is_downloaded(model_name):
            return True
        with self._lock:
            st = self._download_state.get(model_name)
            if st and st.get("status") == "downloading":
                return True
            self._download_state[model_name] = {"status": "downloading", "progress": 0, "error": None}
        threading.Thread(
            target=self._download_blocking, args=(model_name,),
            name=f"whisper-dl-{model_name}", daemon=True,
        ).start()
        return True

    def _download_blocking(self, model_name: str) -> None:
        repo_id = self.model_configs[model_name]["repo_id"]
        try:
            whisper_runtime.ensure_on_path()
            from huggingface_hub import snapshot_download
            logger.info(f"开始下载 Whisper 模型 {model_name} ({repo_id})")
            snapshot_download(
                repo_id=repo_id,
                cache_dir=str(whisper_runtime.get_models_dir() / "hub"),
            )
            with self._lock:
                self._download_state[model_name] = {"status": "downloaded", "progress": 100, "error": None}
            logger.info(f"Whisper 模型 {model_name} 下载完成")
        except Exception as e:  # noqa: BLE001
            logger.error(f"下载 Whisper 模型 {model_name} 失败: {e}", exc_info=True)
            with self._lock:
                self._download_state[model_name] = {"status": "error", "progress": 0, "error": str(e)}

    def get_download_progress(self, model_name: str) -> Optional[int]:
        with self._lock:
            st = self._download_state.get(model_name)
        if not st:
            return 100 if self._is_downloaded(model_name) else None
        return st.get("progress")

    def cancel_download(self, model_name: str) -> bool:
        # snapshot_download 不易中断；这里只清状态，已下载分片保留可续传
        with self._lock:
            if model_name in self._download_state and self._download_state[model_name].get("status") == "downloading":
                self._download_state[model_name] = {"status": "available", "progress": 0, "error": None}
                return True
        return False

    def delete_model(self, model_name: str) -> bool:
        if model_name not in self.model_configs:
            return False
        try:
            import shutil
            d = self._model_cache_dir(model_name)
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
            with self._lock:
                self._download_state.pop(model_name, None)
            logger.info(f"Whisper 模型 {model_name} 已删除")
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"删除 Whisper 模型 {model_name} 失败: {e}")
            return False


_model_manager: Optional[WhisperModelManager] = None


def get_model_manager() -> WhisperModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = WhisperModelManager()
    return _model_manager
