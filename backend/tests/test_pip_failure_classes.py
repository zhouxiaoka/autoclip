"""pip 失败分类（W157-F2）和换源后的进度文案（W157-F3）。"""
import sys

import pytest

from backend.services import pip_install
from backend.services.pip_install import NETWORK_EXIT, NO_WHEEL_EXIT, TIMEOUT_EXIT, CANCEL_EXIT, SOURCE_BUILD_EXIT

# Both indexes blocked (hosts file / firewall): pip retries, then says "no matching distribution".
CONNECTION_REFUSED = """\
WARNING: Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x0000>: Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it')': /simple/opencv-python-headless/
ERROR: Could not find a version that satisfies the requirement opencv-python-headless==4.12.0.88 (from versions: none)
ERROR: No matching distribution found for opencv-python-headless==4.12.0.88"""
CONNECTION_RESET = """\
WARNING: Retrying (Retry(total=0)) after connection broken by 'ProtocolError('Connection aborted.', ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host'))': /simple/av/
ERROR: No matching distribution found for av==15.1.0"""
READ_TIMEOUT = """\
WARNING: Retrying (Retry(total=0)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='pypi.org', port=443): Read timed out. (read timeout=30)")': /simple/av/
ERROR: Could not find a version that satisfies the requirement av==15.1.0 (from versions: none)"""
COULD_NOT_FETCH = """\
Could not fetch URL https://pypi.tuna.tsinghua.edu.cn/simple/av/: There was a problem confirming the ssl certificate: HTTPSConnectionPool(host='pypi.tuna.tsinghua.edu.cn', port=443): Max retries exceeded with url: /simple/av/ (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed')))
ERROR: No matching distribution found for av==15.1.0"""
PROXY = """\
WARNING: Retrying (Retry(total=0)) after connection broken by 'ProxyError('Cannot connect to proxy.', OSError('Tunnel connection failed: 407 Proxy Authentication Required'))': /simple/av/
ERROR: No matching distribution found for av==15.1.0"""
DNS = """\
WARNING: Retrying (Retry(total=0)) after connection broken by 'NewConnectionError('<...>: Failed to resolve 'pypi.org' ([Errno 11001] getaddrinfo failed)')': /simple/av/
ERROR: No matching distribution found for av==15.1.0"""
NO_WHEEL = """\
Looking in indexes: https://pypi.org/simple
ERROR: Could not find a version that satisfies the requirement ctranslate2==4.6.0 (from versions: 3.24.0, 4.0.0)
ERROR: No matching distribution found for ctranslate2==4.6.0"""
ONLY_BINARY = """\
ERROR: Could not find a version that satisfies the requirement foo==1.0 (from versions: none)
ERROR: No matching distribution found for foo==1.0 (only-binary=:all: rejected the source distribution)"""
OTHER = "ERROR: Could not install packages due to an OSError: [WinError 5] Access is denied"


@pytest.mark.parametrize("text", [CONNECTION_REFUSED, CONNECTION_RESET, READ_TIMEOUT, COULD_NOT_FETCH, PROXY, DNS],
                         ids=["refused", "reset", "read-timeout", "could-not-fetch-ssl", "proxy", "dns"])
def test_network_errors_are_network_not_no_wheel(text):
    assert pip_install.classify(1, text.splitlines()) == NETWORK_EXIT


@pytest.mark.parametrize("text", [NO_WHEEL, ONLY_BINARY], ids=["no-matching", "only-binary"])
def test_genuine_no_wheel(text):
    assert pip_install.classify(1, text.splitlines()) == NO_WHEEL_EXIT


def test_other_failures_keep_their_exit_code():
    assert pip_install.classify(1, [OTHER]) == 1
    assert pip_install.classify(0, CONNECTION_REFUSED.splitlines()) == 0


@pytest.mark.parametrize("text,expected", [(CONNECTION_REFUSED, NETWORK_EXIT), (NO_WHEEL, NO_WHEEL_EXIT)])
def test_stream_classifies_real_pip_output(text, expected):
    script = f"import sys; sys.stderr.write({text!r} + '\\n'); sys.exit(1)"
    code, _ = pip_install.stream([sys.executable, "-c", script], 30, 30)
    assert code == expected


@pytest.mark.parametrize("code,failures,expected", [
    (NETWORK_EXIT, ["pypi: 网络不通", "mirror: 网络不通"], "pip_network"),
    (NETWORK_EXIT, ["pypi: 超时", "mirror: 网络不通"], "pip_network"),
    (TIMEOUT_EXIT, ["pypi: 网络不通", "mirror: 超时"], "pip_network"),
    (TIMEOUT_EXIT, ["pypi: 超时", "mirror: 超时"], "pip_timeout"),
    (NO_WHEEL_EXIT, ["pypi: 网络不通", "mirror: 没有可用 wheel"], "pip_no_wheel"),
    (SOURCE_BUILD_EXIT, ["mirror: 需要源码编译"], "pip_source_build"),
    (CANCEL_EXIT, ["pypi: 已取消"], "pip_cancelled"),
    (1, ["pypi: 退出码 1"], "pip_failed"),
])
def test_error_code(code, failures, expected):
    assert pip_install.error_code(code, failures) == expected


def test_network_message_mentions_network_proxy_and_pip_index_url():
    message = pip_install.failure_message(NETWORK_EXIT, ["pypi: 网络不通", "mirror: 网络不通"], "人物识别组件")
    assert "网络" in message and "代理" in message and "PIP_INDEX_URL" in message
    assert "预编译包" not in message and "更新到最新版" not in message


def test_framing_both_indexes_blocked_says_network(tmp_path, monkeypatch):
    from backend.services.studio import framing
    monkeypatch.setattr(framing, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(framing, "is_installed", lambda: False)
    monkeypatch.setattr(pip_install, "index_plan", lambda url=None: [("pypi", None), ("mirror", "https://m")])
    monkeypatch.setattr(pip_install, "stream", lambda *a, **k: (NETWORK_EXIT, CONNECTION_REFUSED.splitlines()))
    framing._do_install(None)
    status = framing.get_status()
    assert status["status"] == "error" and status["error_code"] == "pip_network"
    assert "PIP_INDEX_URL" in status["message"] and "更新到最新版" not in status["message"]
    framing._set_state(status="unknown", progress=0, message="", error_code="")


def test_whisper_both_indexes_blocked_says_network(tmp_path, monkeypatch):
    from backend.services import whisper_runtime
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: False)
    monkeypatch.setattr(whisper_runtime, "index_plan", lambda url=None: [("pypi", None), ("mirror", "https://m")])
    monkeypatch.setattr(whisper_runtime, "_write_install_error", lambda message: None)
    monkeypatch.setattr(pip_install, "stream", lambda *a, **k: (NETWORK_EXIT, CONNECTION_REFUSED.splitlines()))
    whisper_runtime._do_install(None)
    with whisper_runtime._state_lock:
        state = dict(whisper_runtime._state)
    assert state["status"] == "error" and state["error_code"] == "pip_network"
    assert "PIP_INDEX_URL" in state["message"] and "预编译包" not in state["message"]
    whisper_runtime._set_state(status="unknown", progress=0, message="", error_code="")


def test_every_stage_names_the_mirror_after_a_switch():
    progress = pip_install.PipProgress("mirror")
    messages = [step[1] for step in map(progress.feed, [
        "Collecting opencv-python-headless==4.12.0.88",
        "  Downloading opencv_python_headless-4.12.0.88-cp37-abi3-win_amd64.whl (38.9 MB)",
        "Installing collected packages: numpy, opencv-python-headless",
        "Successfully installed numpy-2.2.6 opencv-python-headless-4.12.0.88",
    ]) if step]
    assert len(messages) == 4
    assert all("清华镜像" in m for m in messages), messages


def test_framing_progress_after_mirror_switch_names_the_mirror(tmp_path, monkeypatch):
    from backend.services.studio import framing
    monkeypatch.setattr(framing, "_data_dir", lambda: tmp_path)
    seen = []
    real_set = framing._set_state
    monkeypatch.setattr(framing, "_set_state", lambda **kw: (seen.append(kw.get("message")), real_set(**kw)))

    def fake_stream(cmd, timeout, stall, on_line=None, **_):
        if "--index-url" not in cmd:
            return TIMEOUT_EXIT, []
        for line in ("Collecting opencv-python-headless", "Installing collected packages: opencv-python-headless"):
            on_line(line, [line])
        return 0, []
    monkeypatch.setattr(pip_install, "index_plan", lambda url=None: [("pypi", None), ("mirror", "https://m")])
    monkeypatch.setattr(pip_install, "stream", fake_stream)
    monkeypatch.setattr(framing, "is_installed", lambda: True)
    framing._do_install(None)
    after = [m for m in seen if m][seen.index(next(m for m in seen if m and "改用" in m)) + 1:]
    stages = [m for m in after if m.startswith("正在") and m != "正在连接清华镜像…"]
    assert stages and all("清华镜像" in m for m in stages), after
    framing._set_state(status="unknown", progress=0, message="", error_code="")
