"""Concurrent API reads must not observe/roll back another worker's transaction."""
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from backend.core.database import create_database_engine


def test_file_sqlite_keeps_worker_and_reader_transactions_separate(tmp_path):
    engine = create_database_engine('sqlite:///' + str(tmp_path / 'connections.sqlite'))
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT)'))
            connection.execute(text("INSERT INTO items VALUES (1, 'original')"))
        with engine.connect() as worker:
            transaction = worker.begin()
            worker.execute(text("UPDATE items SET value='updated' WHERE id=1"))
            with engine.connect() as reader:
                assert reader.execute(text('SELECT value FROM items WHERE id=1')).scalar() == 'original'
            transaction.commit()
        with engine.connect() as reader:
            assert reader.execute(text('SELECT value FROM items WHERE id=1')).scalar() == 'updated'
    finally:
        engine.dispose()


def test_memory_sqlite_preserves_database_across_connections():
    engine = create_database_engine('sqlite:///:memory:')
    try:
        assert isinstance(engine.pool, StaticPool)
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE items (id INTEGER)'))
            connection.execute(text('INSERT INTO items VALUES (1)'))
        with engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM items')).scalar() == 1
    finally:
        engine.dispose()


def test_file_sqlite_wal_allows_commit_while_reader_holds_snapshot(tmp_path):
    engine = create_database_engine('sqlite:///' + str(tmp_path / 'wal.sqlite'))
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE items (value INTEGER)'))
            connection.execute(text('INSERT INTO items VALUES (1)'))
        with engine.connect() as reader, engine.connect() as writer:
            assert reader.exec_driver_sql('PRAGMA journal_mode').scalar() == 'wal'
            assert writer.exec_driver_sql('PRAGMA busy_timeout').scalar() == 30000
            reader.exec_driver_sql('BEGIN')
            assert reader.execute(text('SELECT value FROM items')).scalar() == 1
            writer.execute(text('UPDATE items SET value=2'))
            writer.commit()
            assert reader.execute(text('SELECT value FROM items')).scalar() == 1
            reader.rollback()
            assert reader.execute(text('SELECT value FROM items')).scalar() == 2
    finally:
        engine.dispose()
