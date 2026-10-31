"""
Whisper 模型管理服务（faster-whisper）

负责 Systran/faster-whisper 模型的下载、状态检查、删除。模型从 HuggingFace 拉取，
统一缓存到 `<data_dir>/whisper-models`（由 whisper_runtime 设置 HF_HOME）。
依赖（huggingface_hub）来自运行时安装目录，所有相关 import 都延迟到函数内。

下载源（AUTOCLIP_WHISPER_MODEL_SOURCE，RC156 Win QA #6）：
- auto（默认）：先连 huggingface.co，失败再走 hf-mirror.com（国内网络常连不上官方）。
- huggingface：只用官方源；hf-mirror：只用镜像。
用户自己设置了 HF_ENDPOINT 时尊重它，不再自动切换。走镜像时必须关掉 hf_xet：
xet 存储直连 cas-server.xethub.hf.co，不经过 HF_ENDPOINT（QA 实测 401）。
"""
import errno
import logging
import os
import threading
import time
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from . import whisper_runtime

logger = logging.getLogger(__name__)


def _silence_download_progress() -> None:
    """关掉 HuggingFace / tqdm 进度条。

    PYTHON-FASTAPI-H / A：桌面端 stdout 不是控制台时，tqdm.status_printer
    写 ``\\r`` 会抛 OSError / BrokenPipeError，下载被中断。
    """
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ.setdefault("TQDM_DISABLE", "1")
    try:
        from huggingface_hub.utils import disable_progress_bars
        disable_progress_bars()
    except Exception:  # noqa: BLE001
        pass


OFFICIAL_ENDPOINT = "https://huggingface.co"
MIRROR_ENDPOINT = "https://hf-mirror.com"
MODEL_SOURCES = ("auto", "huggingface", "hf-mirror")


PROBE_TIMEOUT = 3.0
_SOURCE_FILE = "model_source.json"


def _source_file() -> Path:
    return whisper_runtime.get_models_dir() / _SOURCE_FILE


def saved_model_source() -> str:
    """The choice from 设置 → 默认模型 → 语音转字幕 → 模型下载源 (E3). Default auto."""
    try:
        import json
        value = str(json.loads(_source_file().read_text(encoding="utf-8")).get("source", "auto")).lower()
    except (OSError, ValueError, AttributeError):
        return "auto"
    return value if value in MODEL_SOURCES else "auto"


def save_model_source(source: str) -> str:
    import json
    value = (source or "").strip().lower()
    if value not in MODEL_SOURCES:
        raise ValueError(f"unsupported model source: {source}")
    _source_file().write_text(json.dumps({"source": value}), encoding="utf-8")
    return value


def model_source() -> str:
    """Env override (QA/CI) wins, then the saved setting."""
    env = (os.environ.get("AUTOCLIP_WHISPER_MODEL_SOURCE") or "").strip().lower()
    if env in MODEL_SOURCES:
        return env
    return saved_model_source()


def _reachable(endpoint: str, timeout: float = PROBE_TIMEOUT) -> bool:
    """Cheap HEAD probe so a blocked huggingface.co costs seconds, not a full download timeout."""
    import urllib.request
    try:
        request = urllib.request.Request(endpoint.rstrip("/") + "/api/models?limit=1", method="HEAD")
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except Exception as error:  # noqa: BLE001 - HTTPError still means the host answered
        import urllib.error
        return isinstance(error, urllib.error.HTTPError)


def download_plan() -> List[tuple]:
    """[(source label, endpoint)] in the order they are tried."""
    source = model_source()
    if source == "huggingface":
        return [("huggingface", OFFICIAL_ENDPOINT)]
    if source == "hf-mirror":
        return [("hf-mirror", MIRROR_ENDPOINT)]
    custom = (os.environ.get("HF_ENDPOINT") or "").strip().rstrip("/")
    if custom:
        return [("custom", custom)]
    # auto: probe the official hub; when it is unreachable (typical in mainland China) start
    # with hf-mirror and keep the official one as the fallback.
    if not _reachable(OFFICIAL_ENDPOINT) and _reachable(MIRROR_ENDPOINT):
        return [("hf-mirror", MIRROR_ENDPOINT), ("huggingface", OFFICIAL_ENDPOINT)]
    return [("huggingface", OFFICIAL_ENDPOINT), ("hf-mirror", MIRROR_ENDPOINT)]


def _disable_xet() -> None:
    """hf_xet downloads bypass HF_ENDPOINT; a mirror only works over plain HTTP.

    huggingface_hub reads the constant at call time, the env var only at import.
    Process-wide on purpose: plain HTTP also works against huggingface.co.
    """
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    try:
        from huggingface_hub import constants
        constants.HF_HUB_DISABLE_XET = True
    except Exception:  # noqa: BLE001
        pass


def canonical_model_name(model_name: str) -> str:
    # SpeechRecognitionConfig 兼容旧配置的 large 别名。
    return "large-v3" if model_name == "large" else model_name


class ModelStatus(str, Enum):
    AVAILABLE = "available"      # 运行时就绪、可下载
    DOWNLOADING = "downloading"  # 下载中
    DOWNLOADED = "downloaded"    # 已下载
    ERROR = "error"              # 错误（通常是运行时未安装）
    NOT_FOUND = "not_found"


# stable reason code; the message below is also the zh i18n key (8 locales).
WHISPER_DOWNLOAD_ERROR_CODE = "whisper_download_failed"
# User-facing download failure status API must never echo raw exception text
# (URLs, query tokens, auth). Full detail stays in logs only.
WHISPER_DOWNLOAD_USER_ERROR = (
    "Whisper 模型下载失败。请检查网络后到「设置 → 默认模型 → 语音转字幕」重新下载，"
    "或在下载源中改用 hf-mirror 镜像。"
)
# Sentry tag for a download that has reached the error state. The UI keeps
# WHISPER_DOWNLOAD_ERROR_CODE; these four never carry a message, URL or path.
DOWNLOAD_FAILURE_CODES = ("network", "disk", "corrupt", "unexpected")
_DISK_ERRNOS = {errno.ENOSPC, errno.EACCES, errno.EROFS}
_NETWORK_NAMES = {
    "ConnectionError", "ConnectTimeout", "ReadTimeout", "Timeout", "TimeoutException",
    "ConnectError", "ReadError", "WriteError", "WriteTimeout", "PoolTimeout",
    "NetworkError", "ProxyError", "SSLError", "ProtocolError", "RemoteProtocolError",
    "ChunkedEncodingError",
}
_NETWORK_MODULES = ("requests", "httpx", "httpcore", "urllib3")


class ModelDownloadFailed(RuntimeError):
    """Final Whisper download failure. Telemetry keeps `code` and nothing else."""

    def __init__(self, code: str):
        if code not in DOWNLOAD_FAILURE_CODES:
            code = "unexpected"
        super().__init__(code)
        self.code = code


def _is_network_error(error: BaseException) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    return type(error).__module__.startswith(_NETWORK_MODULES) and type(error).__name__ in _NETWORK_NAMES


def download_failure_code(error: BaseException) -> str:
    """network (a connection error or timeout, including an HF error caused by one), disk, corrupt, or unexpected.

    Walks ``__cause__`` only. A source that failed over to the next mirror is not a final failure.
    """
    seen: set[int] = set()
    current: Optional[BaseException] = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ModelDownloadFailed):
            return current.code
        if isinstance(current, OSError) and current.errno in _DISK_ERRNOS:
            return "disk"
        if _is_network_error(current):
            return "network"
        current = current.__cause__
    return "unexpected"


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
    error_code: Optional[str] = None
    source: Optional[str] = None  # 实际下载用的源：huggingface / hf-mirror / custom


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


def _snapshot_is_complete(snapshot: Path) -> bool:
    """HF 会在权重下载完成前创建 snapshot；目录存在不代表可以离线转写。"""
    try:
        required = [snapshot / name for name in ("model.bin", "config.json", "tokenizer.json")]
        vocabulary = list(snapshot.glob("vocabulary.*"))
        return (
            all(path.is_file() and path.stat().st_size > 0 for path in required)
            and any(path.is_file() and path.stat().st_size > 0 for path in vocabulary)
        )
    except OSError:
        return False


@dataclass(frozen=True)
class _BrokenFile:
    name: str
    etag: Optional[str]
    size: Optional[int]


def _safe_cache_name(name: object) -> Optional[str]:
    if not isinstance(name, str) or name in {"", ".", ".."}:
        return None
    if any(char in name for char in ("/", "\\", "\x00")):
        return None
    return name


def _lfs_sha256(info: object) -> Optional[str]:
    lfs = info.get("lfs") if isinstance(info, dict) else getattr(info, "lfs", None)
    sha = lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
    return _safe_cache_name(sha)


def _info_size(info: object) -> Optional[int]:
    size = info.get("size") if isinstance(info, dict) else getattr(info, "size", None)
    return size if isinstance(size, int) else None


def _info_path(info: object) -> Optional[str]:
    path = info.get("path") if isinstance(info, dict) else getattr(info, "path", None)
    return path if isinstance(path, str) else None


def _symlink_etag(path: Path) -> Optional[str]:
    if not path.is_symlink():
        return None
    return _safe_cache_name(Path(os.readlink(path)).name)


def _broken_files(snapshot: Path, repo_id: str, endpoint: str) -> Optional[List[_BrokenFile]]:
    """Snapshot files whose size — or, for a symlink, blob name — disagrees with the repo.

    None means the metadata could not be read. That still counts as consistent (a mirror
    without the API must not block a download) and is logged once per lookup. Called only
    after a download, never from the readiness poll.
    """
    try:
        if not snapshot.is_dir():
            return []
        names = sorted(path.name for path in snapshot.iterdir() if path.is_file() or path.is_symlink())
        if not names:
            return []
        from huggingface_hub import HfApi
        infos = HfApi(endpoint=endpoint).get_paths_info(repo_id, names, revision=snapshot.name)
    except Exception as error:  # noqa: BLE001 - no metadata must not block a download that used to work
        logger.warning(
            "Whisper 模型 %s 的仓库文件信息暂时读不到（%s），按本地文件是否非空判断",
            repo_id, type(error).__name__,
        )
        return None
    by_name = {path: info for info in infos if (path := _info_path(info))}
    broken: List[_BrokenFile] = []
    for name in names:
        info = by_name.get(name)
        expected = _info_size(info) if info is not None else None
        if expected is None:
            continue
        path = snapshot / name
        etag = _lfs_sha256(info) or _symlink_etag(path)
        try:
            size = path.stat().st_size
        except OSError:
            broken.append(_BrokenFile(name, etag, expected))
            continue
        if size != expected:
            broken.append(_BrokenFile(name, etag, expected))
            continue
        linked = _symlink_etag(path)
        sha = _lfs_sha256(info)
        if linked and sha and linked != sha:
            broken.append(_BrokenFile(name, sha, expected))
    return broken


def _zero_byte_files(snapshot: Path) -> List[_BrokenFile]:
    """Empty required files, used when repo metadata is unavailable (the non-empty check still applies)."""
    found: List[_BrokenFile] = []
    if not snapshot.is_dir():
        return found
    paths = [snapshot / name for name in ("model.bin", "config.json", "tokenizer.json")]
    paths.extend(snapshot.glob("vocabulary.*"))
    for path in paths:
        try:
            empty = (path.is_file() or path.is_symlink()) and path.stat().st_size == 0
        except OSError:
            empty = True
        if empty and (path.is_file() or path.is_symlink()):
            found.append(_BrokenFile(path.name, _symlink_etag(path), None))
    return found


def _blobs_dir(snapshot: Path) -> Path:
    # hub/models--org--name/snapshots/<rev>  →  hub/models--org--name/blobs
    return snapshot.parent.parent / "blobs"


def _blob_inside(path: Path, blobs: Path) -> Optional[Path]:
    try:
        target = path.resolve()
        target.relative_to(blobs.resolve())
    except (OSError, ValueError):
        return None
    return target if target.is_file() else None


def _unlink(path: Path, label: str) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Whisper 模型的坏缓存文件没能删掉（%s）", label)


def _delete_broken(snapshot: Path, items: List[_BrokenFile]) -> None:
    """Remove bad snapshot entries so a normal snapshot_download can write them.

    HuggingFace creates a snapshot path only when it is missing, and on a copy layout
    (Windows without developer mode) it reuses a blob that already exists. A truncated
    blob is removed; a blob whose size already matches the repo is kept and copied back.
    force_download is not used: it rewrites the blob and still leaves the existing copy.
    """
    blobs = _blobs_dir(snapshot)
    for item in items:
        name = _safe_cache_name(item.name)
        if name is None:
            continue
        path = snapshot / name
        if path.is_symlink():
            target = _blob_inside(path, blobs)
            _unlink(path, name)
            if target is not None:
                _unlink(target, name)
        elif path.exists():
            _unlink(path, name)
        etag = _safe_cache_name(item.etag)
        if etag and item.size is not None:
            blob = blobs / etag
            try:
                short = blob.is_file() and not blob.is_symlink() and blob.stat().st_size != item.size
            except OSError:
                short = True
            if short:
                _unlink(blob, name)
        if etag:
            _unlink(blobs / f"{etag}.incomplete", name)


def _fetch_snapshot(snapshot_download, args: dict, repo_id: str, endpoint: str) -> str:
    """One normal download, then at most one more after the bad files have been deleted."""
    snapshot = Path(snapshot_download(**args))
    broken = _broken_files(snapshot, repo_id, endpoint)
    if _snapshot_is_complete(snapshot) and not broken:
        return str(snapshot)
    targets = broken or _zero_byte_files(snapshot)
    if targets:
        _delete_broken(snapshot, targets)
    repaired = Path(snapshot_download(**args))
    broken_after = _broken_files(repaired, repo_id, endpoint)
    if not _snapshot_is_complete(repaired) or broken_after:
        raise ModelDownloadFailed("corrupt")
    return str(repaired)


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

    def get_local_model_path(self, model_name: str) -> Optional[Path]:
        model_name = canonical_model_name(model_name)
        if model_name not in self.model_configs:
            return None
        d = self._model_cache_dir(model_name)
        snaps = d / "snapshots"
        try:
            candidates = sorted(snaps.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
            ref = d / "refs" / "main"
            if ref.is_file():
                revision = ref.read_text(encoding="utf-8").strip()
                # 只选当前缓存内的 snapshot，不使用任意路径。
                candidates.sort(key=lambda path: path.name != revision)
            return next((path for path in candidates if _snapshot_is_complete(path)), None)
        except OSError:
            return None

    def _is_downloaded(self, model_name: str) -> bool:
        return self.get_local_model_path(model_name) is not None

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
            error_code=st.get("error_code"),
            source=st.get("source"),
        )

    def get_all_models_info(self) -> List[ModelInfo]:
        return [self._info(name) for name in self.model_configs]

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        if model_name not in self.model_configs:
            return None
        return self._info(model_name)

    # ---- 下载（后台线程，非阻塞）----
    async def download_model(self, model_name: str) -> str:
        """Start a background download. Returns "installed" or "downloading", never "done".

        The download finishes (or fails) later: callers poll get_model_info (RC156 Win QA #5).
        """
        if model_name not in self.model_configs:
            raise ValueError(f"不支持的模型: {model_name}")
        if not whisper_runtime.is_installed():
            raise RuntimeError("请先安装 Whisper 运行时")
        if self._is_downloaded(model_name):
            # A complete resumed cache must recover a previous download error
            # immediately, without requiring an application restart.
            with self._lock:
                st = self._download_state.get(model_name, {})
                if st.get("status") != "downloading":
                    self._download_state[model_name] = {
                        "status": "downloaded", "progress": 100, "error": None,
                    }
            return "installed"
        with self._lock:
            st = self._download_state.get(model_name)
            if st and st.get("status") == "downloading":
                return "downloading"
            self._download_state[model_name] = {"status": "downloading", "progress": 0, "error": None}
        threading.Thread(
            target=self._download_blocking, args=(model_name,),
            name=f"whisper-dl-{model_name}", daemon=True,
        ).start()
        return "downloading"

    def ensure_downloaded(self, model_name: str, poll_seconds: float = 1.0) -> Path:
        """Blocking: the local snapshot, downloading it first (same sources/fallback) when missing.

        Transcription must never let faster-whisper fetch the model itself: that path ignores
        the mirror fallback and leaves no status for the UI.
        """
        model_name = canonical_model_name(model_name)
        if model_name not in self.model_configs:
            raise ValueError(f"不支持的模型: {model_name}")
        local = self.get_local_model_path(model_name)
        if local is not None:
            return local
        with self._lock:
            st = self._download_state.get(model_name)
            running = bool(st and st.get("status") == "downloading")
            if not running:
                self._download_state[model_name] = {"status": "downloading", "progress": 0, "error": None}
        if running:
            while True:
                with self._lock:
                    st = self._download_state.get(model_name) or {}
                if st.get("status") != "downloading":
                    break
                time.sleep(poll_seconds)
        else:
            self._download_blocking(model_name)
        local = self.get_local_model_path(model_name)
        if local is None:
            with self._lock:
                error = (self._download_state.get(model_name) or {}).get("error")
            raise RuntimeError(error or f"Whisper 模型 {model_name} 下载未完成")
        return local

    def _download_blocking(self, model_name: str) -> None:
        repo_id = self.model_configs[model_name]["repo_id"]
        try:
            whisper_runtime.ensure_on_path()
            from huggingface_hub import snapshot_download
            _silence_download_progress()
            plan = download_plan()
            failures = []
            for index, (source, endpoint) in enumerate(plan):
                if endpoint != OFFICIAL_ENDPOINT:
                    _disable_xet()
                logger.info("开始下载 Whisper 模型 %s (%s, 源 %s)", model_name, repo_id, source)
                try:
                    args = dict(repo_id=repo_id, cache_dir=str(whisper_runtime.get_models_dir() / "hub"), endpoint=endpoint)
                    # A bad snapshot file is deleted and fetched again with a normal download.
                    # force_download only refreshes the blob and leaves a copy-layout file in place.
                    _fetch_snapshot(snapshot_download, args, repo_id, endpoint)
                except Exception as e:  # noqa: BLE001
                    failures.append(f"{source}: {type(e).__name__}: {e}")
                    if index + 1 < len(plan):
                        logger.warning("Whisper 模型 %s 从 %s 下载失败（%s），改用 %s",
                                       model_name, source, type(e).__name__, plan[index + 1][0])
                        continue
                    if len(failures) > 1:
                        raise RuntimeError("；".join(failures)) from e
                    raise
                with self._lock:
                    self._download_state[model_name] = {
                        "status": "downloaded", "progress": 100, "error": None, "source": source,
                    }
                logger.info("Whisper 模型 %s 下载完成（源 %s）", model_name, source)
                return
        except Exception as e:  # noqa: BLE001
            # 换源过程中的失败只 warning。状态变成 error 时上报一次，事件里只有错误码。
            # warning 而不是 error：LoggingIntegration(event_level=ERROR) 会把可恢复错误打进 Sentry。
            logger.warning(
                "下载 Whisper 模型 %s 失败: %s: %s",
                model_name, type(e).__name__, e,
            )
            from backend.core import sentry_setup
            sentry_setup.capture_studio_exception(ModelDownloadFailed(download_failure_code(e)), phase="model_download")
            with self._lock:
                self._download_state[model_name] = {
                    "status": "error", "progress": 0, "error": WHISPER_DOWNLOAD_USER_ERROR,
                    "error_code": WHISPER_DOWNLOAD_ERROR_CODE,
                }

    def download_status(self, model_name: str) -> Optional[str]:
        """In-process download state only ("downloading" / "downloaded" / "error"); no disk or network."""
        with self._lock:
            return (self._download_state.get(canonical_model_name(model_name)) or {}).get("status")

    def get_download_progress(self, model_name: str) -> Optional[int]:
        with self._lock:
            st = self._download_state.get(model_name)
        if not st or st.get("status") == "downloaded":
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
