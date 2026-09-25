"""文件 SQLite 不能再把连接囤在 QueuePool 里（#175）。

桌面端多个入口同时打出 QueuePool limit of size 5 overflow 10 reached。
根因是 next(get_db()) 丢掉生成器，finally 里的 close() 不会执行，连接不归还。
症状栈停在 get_multi，漏的是更早打开、没关掉的会话。
"""

from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, StaticPool

from backend.core.database import is_memory_sqlite, sqlite_engine_kwargs


def test_memory_sqlite_keeps_static_pool_file_sqlite_uses_null_pool():
    assert is_memory_sqlite("sqlite://")
    assert is_memory_sqlite("sqlite:///:memory:")
    assert not is_memory_sqlite("sqlite:///autoclip.db")
    assert sqlite_engine_kwargs("sqlite:///:memory:")["poolclass"] is StaticPool
    assert sqlite_engine_kwargs("sqlite://")["poolclass"] is StaticPool
    file_kwargs = sqlite_engine_kwargs("sqlite:///autoclip.db")
    assert file_kwargs["poolclass"] is NullPool
    assert file_kwargs["poolclass"] is not StaticPool


def test_configured_engine_matches_url():
    from backend.core import database as db

    url = str(db.engine.url)
    if "sqlite" not in url:
        pytest.skip("non-sqlite engine")
    if is_memory_sqlite(url):
        assert isinstance(db.engine.pool, StaticPool)
    else:
        assert isinstance(db.engine.pool, NullPool)
        assert not isinstance(db.engine.pool, StaticPool)


def test_abandoned_get_db_exhausts_queue_pool_session_scope_does_not(tmp_path):
    """同一条小池：丢掉生成器会超时；session_scope 可以反复借用。"""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'pool.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.2,
    )
    Session = sessionmaker(bind=engine)

    def get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    leaked = []

    def leak_once():
        gen = get_db()
        leaked.append(gen)
        db = next(gen)
        db.execute(text("SELECT 1"))

    leak_once()
    with pytest.raises(SATimeoutError):
        leak_once()

    for gen in leaked:
        gen.close()
    assert engine.pool.checkedout() == 0

    @contextmanager
    def session_scope():
        db = Session()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    for _ in range(8):
        with session_scope() as db:
            db.execute(text("SELECT 1"))
    assert engine.pool.checkedout() == 0
    engine.dispose()


def test_session_scope_returns_connection_after_error(tmp_path, monkeypatch):
    from backend.core import database as dbmod

    engine = create_engine(
        f"sqlite:///{tmp_path / 'scope.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.2,
    )
    monkeypatch.setattr(dbmod, "SessionLocal", sessionmaker(bind=engine))

    with pytest.raises(RuntimeError):
        with dbmod.session_scope() as db:
            db.execute(text("SELECT 1"))
            raise RuntimeError("boom")

    assert engine.pool.checkedout() == 0
    with dbmod.session_scope() as db:
        db.execute(text("SELECT 1"))
    assert engine.pool.checkedout() == 0
    engine.dispose()


def test_pipeline_adapter_closes_only_sessions_it_creates(tmp_path, monkeypatch):
    from backend.services import pipeline_adapter as pad

    closed = []

    class FakeSession:
        def close(self):
            closed.append("owned")

        def rollback(self):
            return None

    monkeypatch.setattr(pad, "SessionLocal", lambda: FakeSession())
    owned = pad.PipelineAdapter(str(tmp_path))
    assert owned._owns_db
    owned.close()
    assert closed == ["owned"]
    owned.close()
    assert closed == ["owned"]

    external = FakeSession()

    def _close_external():
        closed.append("external")

    external.close = _close_external
    borrowed = pad.PipelineAdapter(str(tmp_path), task_id="task-1", db=external)
    assert not borrowed._owns_db
    borrowed.close()
    assert closed == ["owned"]


def test_request_and_worker_paths_do_not_drop_get_db():
    root = Path(__file__).resolve().parents[2]
    for rel in (
        "backend/api/v1/projects.py",
        "backend/services/account_health_service.py",
        "backend/services/upload_queue_service.py",
        "backend/tasks/import_processing.py",
        "backend/tasks/processing.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "next(get_db())" not in text, rel
