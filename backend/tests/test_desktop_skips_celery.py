"""Desktop Studio must not spawn a Celery worker."""
from pathlib import Path


def test_desktop_main_does_not_launch_celery():
    text = (Path(__file__).resolve().parents[1] / 'desktop_main.py').read_text(encoding='utf-8')
    assert 'Studio 任务在本进程线程池执行' in text
    assert 'celery_app.worker_main' not in text
    assert "'-m', 'celery'" not in text
