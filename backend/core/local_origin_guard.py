"""
本地后端的来源守卫。

后端没有登录态，任何能发 HTTP 请求到它的页面都能读设置里的 API Key、触发导入和发布。
浏览器里打开的普通网页也能向 127.0.0.1 发请求，所以要在服务端拦：

1. CORS 只对 AutoClip 自己的前端放行，其他网页读不到响应。
2. 带 Origin 的写请求（POST/PUT/PATCH/DELETE）必须来自允许的来源，或与请求 Host 同源。
   表单 / multipart 这类“简单请求”不会触发预检，只靠 CORS 拦不住。
3. 桌面模式只接受 Host 为 127.0.0.1 / localhost 的请求，挡住 DNS 重绑定。

CLI、curl、Tauri 的 reqwest 不带 Origin，照常放行。
Docker 通过局域网 IP 或自定义域名访问时，用 AUTOCLIP_ALLOWED_ORIGINS 追加来源（逗号分隔）。
"""
from __future__ import annotations

import os
from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Tauri 2：macOS / Linux 为 tauri://localhost，Windows 为 http(s)://tauri.localhost；3000 是 Vite 开发端口
DEFAULT_ALLOWED_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)

LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1", "[::1]"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def allowed_origins() -> list[str]:
    extra = [o.strip().rstrip("/") for o in os.getenv("AUTOCLIP_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    return list(dict.fromkeys([*DEFAULT_ALLOWED_ORIGINS, *extra]))


def _header(scope: Scope, name: bytes) -> str:
    for key, value in scope.get("headers") or ():
        if key == name:
            return value.decode("latin-1")
    return ""


def _hostname(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if ":" in host else host


def is_same_origin(origin: str, host: str) -> bool:
    """Origin 的 host:port 与请求 Host 一致（Docker 直接访问 :8000 或反代保留 Host 的情况）。"""
    if not origin or not host:
        return False
    parsed = urlsplit(origin)
    return bool(parsed.netloc) and parsed.netloc.lower() == host.strip().lower()


class LocalOriginGuard:
    def __init__(self, app: ASGIApp, origins: Iterable[str], enforce_local_host: bool) -> None:
        self.app = app
        self.origins = {o.lower() for o in origins}
        self.enforce_local_host = enforce_local_host

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        host = _header(scope, b"host")
        if self.enforce_local_host and host and _hostname(host) not in LOCAL_HOSTNAMES:
            await self._reject(scope, receive, send, "host_not_allowed")
            return

        origin = _header(scope, b"origin").rstrip("/").lower()
        method = scope.get("method", "GET").upper()
        cross_site_write = scope["type"] == "http" and method not in SAFE_METHODS
        if origin and (cross_site_write or scope["type"] == "websocket"):
            forwarded_host = _header(scope, b"x-forwarded-host")
            trusted = (
                origin in self.origins
                or is_same_origin(origin, host)
                or is_same_origin(origin, forwarded_host)
            )
            if not trusted:
                await self._reject(scope, receive, send, "origin_not_allowed")
                return

        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send, code: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        response = JSONResponse(
            status_code=403,
            content={"detail": "请求来源不被允许", "error_code": code},
        )
        await response(scope, receive, send)
