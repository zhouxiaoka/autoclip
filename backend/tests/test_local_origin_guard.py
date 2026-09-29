"""本地后端来源守卫：其他网页不能读 Key、不能发写请求，自家前端和 CLI 不受影响。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.core.local_origin_guard import LocalOriginGuard, allowed_origins


def make_client(enforce_local_host: bool, base_url: str = "http://127.0.0.1:8000") -> TestClient:
    app = FastAPI()
    origins = allowed_origins()
    app.add_middleware(LocalOriginGuard, origins=origins, enforce_local_host=enforce_local_host)
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/settings")
    def read():
        return {"key": "sk-secret"}

    @app.post("/import")
    def write():
        return {"ok": True}

    return TestClient(app, base_url=base_url)


def test_foreign_page_cannot_read_response_via_cors():
    c = make_client(True)
    r = c.get("/settings", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    r = c.get("/settings", headers={"Origin": "tauri://localhost"})
    assert r.headers["access-control-allow-origin"] == "tauri://localhost"


def test_foreign_page_cannot_post_simple_request():
    c = make_client(True)
    r = c.post("/import", data={"url": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert r.json()["error_code"] == "origin_not_allowed"
    r = c.post("/import", headers={"Origin": "null"})
    assert r.status_code == 403


def test_app_origins_and_non_browser_clients_allowed():
    c = make_client(True)
    for origin in ("tauri://localhost", "http://tauri.localhost", "http://localhost:3000"):
        assert c.post("/import", headers={"Origin": origin}).status_code == 200
    # CLI / curl / Tauri reqwest 不带 Origin
    assert c.post("/import").status_code == 200


def test_preflight_from_app_origin_succeeds():
    c = make_client(True)
    r = c.options("/import", headers={"Origin": "tauri://localhost", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200


def test_desktop_rejects_dns_rebinding_host():
    c = make_client(True, base_url="http://attacker.example:8000")
    assert c.get("/settings").status_code == 403
    assert make_client(True, base_url="http://localhost:51234").get("/settings").status_code == 200


def test_web_mode_same_origin_and_extra_origins(monkeypatch):
    # Docker 从局域网 IP 直接访问 :8000 → 同源放行
    c = make_client(False, base_url="http://192.168.1.20:8000")
    assert c.post("/import", headers={"Origin": "http://192.168.1.20:8000"}).status_code == 200
    # 前端在 :3000、后端在 :8000 的局域网部署 → 需要显式加入
    assert c.post("/import", headers={"Origin": "http://192.168.1.20:3000"}).status_code == 403
    monkeypatch.setenv("AUTOCLIP_ALLOWED_ORIGINS", "http://192.168.1.20:3000")
    c = make_client(False, base_url="http://192.168.1.20:8000")
    assert c.post("/import", headers={"Origin": "http://192.168.1.20:3000"}).status_code == 200


def test_debug_routes_not_mounted_by_default():
    from backend.api.v1 import api_router
    assert not any(getattr(r, "path", "").startswith("/debug") for r in api_router.routes)
