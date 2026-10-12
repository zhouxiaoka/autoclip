"""共用 pip 安装：源顺序、回退、进度解析。"""
import sys

from backend.services import pip_install


def test_plan_order_and_pip_index_url(monkeypatch):
    for name in ("AUTOCLIP_PIP_INDEX", "PIP_INDEX_URL"):
        monkeypatch.delenv(name, raising=False)
    assert [label for label, _ in pip_install.index_plan()] == ["pypi", "mirror"]
    monkeypatch.setenv("PIP_INDEX_URL", "https://example.invalid/simple")
    assert pip_install.index_plan() == [("custom", "https://example.invalid/simple")]
    assert pip_install.index_plan("https://x.invalid/simple") == [("custom", "https://x.invalid/simple")]


def test_run_plan_stops_on_success_and_records_failures():
    seen = []

    def run(cmd, timeout, stall, label):
        seen.append((label, timeout))
        return {"pypi": pip_install.TIMEOUT_EXIT, "mirror": 0}[label]

    switches = []
    code, failures = pip_install.run_plan([("pypi", "a"), ("mirror", "b")], lambda url: [url], run,
                                          on_switch=lambda old, new, why: switches.append((old, new, why)))
    assert code == 0 and failures == ["pypi: 超时"]
    assert seen == [("pypi", pip_install.PIP_OFFICIAL_TIMEOUT_SECONDS), ("mirror", pip_install.PIP_MIRROR_TIMEOUT_SECONDS)]
    assert switches == [("pypi", "mirror", "pypi: 超时")]


def test_progress_parses_pip_output():
    progress = pip_install.PipProgress("mirror")
    steps = [progress.feed(line) for line in [
        "Looking in indexes: https://pypi.tuna.tsinghua.edu.cn/simple",
        "Collecting opencv-python-headless>=4.10",
        "  Downloading opencv_python_headless-4.12.0.88-cp37-abi3-win_amd64.whl (38.9 MB)",
        "Collecting numpy<2.3.0,>=2",
        "  Downloading numpy-2.2.6-cp313-cp313-win_amd64.whl (12.6 MB)",
        "Installing collected packages: numpy, opencv-python-headless",
        "Successfully installed numpy-2.2.6 opencv-python-headless-4.12.0.88",
    ]]
    assert steps[0] is None
    percents = [s[0] for s in steps if s]
    assert percents == sorted(percents) and percents[0] > 5 and percents[-1] == 98
    assert "从清华镜像下载 opencv_python_headless（38.9 MB）" in steps[2][1]
    assert "已下载 2/2 个包，共 51.5 MB" in steps[4][1]
    assert steps[5][1] == "正在安装依赖（清华镜像）…"


def test_progress_handles_kb_and_unsized_lines():
    progress = pip_install.PipProgress("pypi")
    progress.feed("Collecting click")
    step = progress.feed("Downloading click-8.5.0-py3-none-any.whl (125 kB)")
    assert "0.1 MB" in step[1] and "官方 PyPI" in step[1]
    assert progress.feed("Downloading something") is not None


def test_stream_reports_lines_and_detects_source_builds():
    seen = []
    script = "print('Collecting av', flush=True);print('Building wheel for av (pyproject.toml): started', flush=True);print('never')"
    code, _ = pip_install.stream([sys.executable, "-c", script], 30, 30, lambda line, lines: seen.append(line))
    assert code == pip_install.SOURCE_BUILD_EXIT
    assert seen == ["Collecting av"]
