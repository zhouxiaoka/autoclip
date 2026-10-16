"""R11 #392: privacy.json writes are atomic; unreadable privacy never allows collection."""
import threading

from backend.core import sentry_setup
from backend.services.studio.qa import telemetry


def test_concurrent_reader_never_sees_collection_allowed_while_opted_out(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    sentry_setup.write_privacy(analytics=False)
    stop = threading.Event()
    allowed = []

    def writer():
        flip = False
        while not stop.is_set():
            flip = not flip
            sentry_setup.write_privacy(crash_reports=flip, analytics=False)

    def reader():
        for _ in range(3000):
            if telemetry._analytics_allowed():
                allowed.append(True)

    threads = [threading.Thread(target=writer) for _ in range(2)]
    for t in threads:
        t.start()
    try:
        reader()
    finally:
        stop.set()
        for t in threads:
            t.join()
    assert allowed == []
    assert not list(tmp_path.glob('.privacy-*.tmp'))


def test_unreadable_privacy_file_defaults_to_not_collecting(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"analytics": tr', encoding='utf-8')
    assert telemetry._analytics_allowed() is False
    (tmp_path / 'privacy.json').write_text('[]', encoding='utf-8')
    assert telemetry._analytics_allowed() is False


def test_missing_privacy_file_keeps_product_default(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    assert telemetry._analytics_allowed() is True


def test_corrupt_file_rewritten_for_crash_reports_stays_opted_out(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{oops', encoding='utf-8')
    sentry_setup.write_privacy(crash_reports=True)
    assert telemetry._analytics_allowed() is False
