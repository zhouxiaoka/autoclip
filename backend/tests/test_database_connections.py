"""Concurrent API reads must not observe/roll back another worker's transaction."""
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
import sqlite3
import time
import pytest
from sqlalchemy.exc import DatabaseError, OperationalError
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


def legacy_database(path):
    connection = sqlite3.connect(path)
    connection.execute('CREATE TABLE items (value INTEGER)')
    connection.execute('INSERT INTO items VALUES (1)')
    connection.commit()
    assert connection.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
    return connection


def test_legacy_database_reader_does_not_block_connection_or_lose_data(tmp_path):
    path = tmp_path / 'old-project.sqlite'
    old_reader = legacy_database(path)
    engine = create_database_engine('sqlite:///' + str(path))
    try:
        old_reader.execute('BEGIN')
        assert old_reader.execute('SELECT value FROM items').fetchone()[0] == 1
        started = time.monotonic()
        with engine.connect() as connection:
            assert connection.exec_driver_sql('SELECT value FROM items').scalar() == 1
            assert connection.exec_driver_sql('PRAGMA journal_mode').scalar() == 'delete'
            assert connection.exec_driver_sql('PRAGMA busy_timeout').scalar() == 30000
        assert time.monotonic() - started < 5  # Old code fails after a 30s lock wait.
        old_reader.rollback()
        with engine.begin() as connection:
            assert connection.exec_driver_sql('PRAGMA journal_mode').scalar() == 'wal'
            connection.exec_driver_sql('UPDATE items SET value=2')
        with engine.connect() as connection:
            assert connection.exec_driver_sql('SELECT value FROM items').scalar() == 2
    finally:
        old_reader.close()
        engine.dispose()


def test_readonly_legacy_database_can_be_inspected_but_not_written(tmp_path):
    path = tmp_path / 'readonly.sqlite'
    legacy_database(path).close()
    engine = create_database_engine('sqlite:///file:' + path.as_posix() + '?mode=ro&uri=true')
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql('SELECT value FROM items').scalar() == 1
            with pytest.raises(OperationalError) as exc:
                connection.exec_driver_sql('UPDATE items SET value=2')
            assert exc.value.orig.sqlite_errorcode & 0xff == sqlite3.SQLITE_READONLY
    finally:
        engine.dispose()


def test_corrupt_database_error_is_not_suppressed(tmp_path):
    path = tmp_path / 'corrupt.sqlite'
    path.write_bytes(b'invalid database fixture')
    engine = create_database_engine('sqlite:///' + str(path))
    try:
        with pytest.raises(DatabaseError) as exc:
            engine.connect()
        assert exc.value.orig.sqlite_errorcode & 0xff == sqlite3.SQLITE_NOTADB
    finally:
        engine.dispose()
