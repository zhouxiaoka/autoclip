#!/usr/bin/env python3
"""用本机密钥做一次真实的私密试发：Upload-Post + B 站。

需要的环境变量（不会写进仓库）：

  UPLOAD_POST_API_KEY   Upload-Post API Key
  UPLOAD_POST_USER      已连接账号的 profile（默认 main）
  UPLOAD_POST_PLATFORM  可选，默认 youtube（会带 privacyStatus=private）
  BILIBILI_COOKIE       浏览器请求头 Cookie（SESSDATA / bili_jct / DedeUserID）

用法：

  python3 scripts/verify_live_publish.py

成功时打印 BV 号和 Upload-Post request_id；密钥与 Cookie 不会打印。
失败时以非 0 退出。没有密钥时直接说明缺什么，不假装成功。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _die(message: str, code: int = 1) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(code)


def _need(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        _die(f"缺少环境变量 {name}")
    return value


def _make_sample(path: Path) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=#1a1a19:s=1280x720:d=3",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-movflags", "+faststart",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not path.exists() or path.stat().st_size <= 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        _die("ffmpeg 生成试片失败" + (f"：{detail[-1]}" if detail else ""))


def verify_upload_post(video: Path) -> dict:
    from backend.services import upload_post_publisher as up

    key = _need("UPLOAD_POST_API_KEY")
    user = (os.getenv("UPLOAD_POST_USER") or "main").strip() or "main"
    platform = (os.getenv("UPLOAD_POST_PLATFORM") or "youtube").strip().lower() or "youtube"
    cfg = up.UploadPostConfig(api_key=key, user=user, source="env")
    me = up.me(cfg)
    profiles = up.list_profiles(cfg)
    connected = []
    for profile in profiles:
        if profile.get("username") == user or profile.get("display_name") == user:
            connected = list(profile.get("connected_platforms") or [])
            break
    if not connected and profiles:
        connected = list(profiles[0].get("connected_platforms") or [])
        user = str(profiles[0].get("username") or user)
    if platform not in connected:
        _die(f"profile {user!r} 没有连接 {platform}（已连接：{', '.join(connected) or '无'}）")

    extra: dict[str, str] = {}
    if platform == "tiktok":
        extra["privacy_level"] = "SELF_ONLY"
    elif platform == "youtube":
        extra["privacyStatus"] = "private"
    else:
        _die(f"私密试发目前只支持 tiktok / youtube，收到的是 {platform}")

    request_id = str(uuid.uuid4())
    title = f"AutoClip private check {time.strftime('%Y%m%d-%H%M%S')}"
    form = {
        "user": user,
        "platform[]": [platform],
        "title": title,
        "async_upload": "true",
        "request_id": request_id,
        "external_id": f"autoclip:live-verify:{request_id[:8]}",
        **extra,
    }
    headers = up._headers(cfg)
    headers["Idempotency-Key"] = request_id
    import requests
    with video.open("rb") as handle:
        resp = requests.post(
            f"{cfg.base_url}/api/upload",
            headers=headers,
            data=form,
            files={"video": (video.name, handle, "video/mp4")},
            timeout=(30, 900),
        )
    data = up._raise_for_response(resp, "提交私密试发")
    job_id = data.get("job_id")
    rid = data.get("request_id") or request_id
    print(f"OK upload-post: platform={platform} profile={user} request_id={rid} job_id={job_id or '-'}")
    # 等一轮状态，确认远端接住了；不要求立刻全部完成
    deadline = time.time() + 120
    last = {}
    while time.time() < deadline:
        last = up.get_status(rid, cfg)
        status = str(last.get("status") or "")
        results = last.get("results") or []
        if status in {"completed", "failed", "partial"} or results:
            break
        time.sleep(5)
    print(f"OK upload-post status={last.get('status') or 'pending'} results={len(last.get('results') or [])}")
    return {"request_id": rid, "job_id": job_id, "me": bool(me), "platform": platform, "user": user}


def verify_bilibili(video: Path) -> dict:
    from backend.services import bilibili_publisher as bili

    cookie = _need("BILIBILI_COOKIE")
    info = bili.verify_cookie(cookie)
    uploaded = bili.upload_video(
        info["cookie"],
        video,
        title=f"AutoClip 私密试发 {time.strftime('%Y%m%d-%H%M%S')}",
        description="仅自己可见。来自 scripts/verify_live_publish.py。",
        private=True,
        dtime=None,
    )
    print(f"OK bilibili: nickname={info['nickname']} bvid={uploaded['bvid']} url={uploaded['url']}")
    return uploaded


def main() -> int:
    missing = [name for name in ("UPLOAD_POST_API_KEY", "BILIBILI_COOKIE") if not (os.getenv(name) or "").strip()]
    if missing:
        print("这台机器还不能做真实投稿。请先在环境里设置：", file=sys.stderr)
        for name in missing:
            print(f"  {name}", file=sys.stderr)
        print("可选：UPLOAD_POST_USER（默认 main）、UPLOAD_POST_PLATFORM（默认 youtube）", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="autoclip-live-publish-") as tmp:
        video = Path(tmp) / "private-check.mp4"
        _make_sample(video)
        up = verify_upload_post(video)
        bili = verify_bilibili(video)
    print(f"DONE private upload-post={up['request_id']} bilibili={bili['bvid']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
