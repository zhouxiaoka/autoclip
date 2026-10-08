"""Startup removal of leftover project directories with no DB row (RC156 PR4 leftover)."""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.base import Base
from backend.models.project import Project, ProjectStatus
from backend.services.project_orphan_cleanup import cleanup_orphan_project_directories


@pytest.fixture
def setup(tmp_path):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(Project(id='kept-1', name='kept', status=ProjectStatus.COMPLETED))
        db.commit()
    root = tmp_path / 'data' / 'projects'
    root.mkdir(parents=True)
    yield factory, root
    engine.dispose()


def _dir(root, name, files=('input.mp4',)):
    folder = root / name
    (folder / 'metadata').mkdir(parents=True)
    for file in files:
        (folder / file).write_bytes(b'x')
    return folder


def test_removes_only_directories_without_a_db_row(setup, caplog):
    factory, root = setup
    kept = _dir(root, 'kept-1')
    orphan = _dir(root, 'd34f5025-0000-4000-8000-000000000000')
    caplog.set_level('INFO')
    assert cleanup_orphan_project_directories(factory, root) == ['d34f5025-0000-4000-8000-000000000000']
    assert kept.is_dir() and (kept / 'input.mp4').is_file()
    assert not orphan.exists()
    assert 'd34f5025-0000-4000-8000-000000000000' in caplog.text  # what was removed is logged


def test_database_read_failure_removes_nothing(setup, caplog):
    _factory, root = setup
    orphan = _dir(root, 'orphan')
    def broken():
        raise RuntimeError('database is locked')
    assert cleanup_orphan_project_directories(broken, root) == []
    assert orphan.is_dir()
    assert 'database read failed' in caplog.text


def test_query_failure_inside_the_session_removes_nothing(setup):
    _factory, root = setup
    orphan = _dir(root, 'orphan')
    engine = create_engine('sqlite:///:memory:')  # no tables: the query itself fails
    try:
        assert cleanup_orphan_project_directories(sessionmaker(bind=engine), root) == []
    finally:
        engine.dispose()
    assert orphan.is_dir()


def test_never_touches_files_odd_names_or_anything_outside_the_root(setup, tmp_path):
    factory, root = setup
    (root / 'notes.txt').write_text('keep')
    odd = root / 'not a project id'
    odd.mkdir()
    outside = tmp_path / 'outside-target'
    (outside / 'precious').mkdir(parents=True)
    link = root / 'linked-orphan'
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('symlinks unavailable')
    assert cleanup_orphan_project_directories(factory, root) == []
    assert (root / 'notes.txt').is_file() and odd.is_dir()
    assert (outside / 'precious').is_dir() and link.exists()
    assert root.parent.is_dir() and (tmp_path / 'data').is_dir()


def test_missing_projects_root_is_a_no_op(setup, tmp_path):
    factory, _root = setup
    assert cleanup_orphan_project_directories(factory, tmp_path / 'nope') == []
    assert not (tmp_path / 'nope').exists()


def test_empty_project_table_removes_nothing(tmp_path):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    root = tmp_path / 'projects'
    orphan = _dir(root, 'some-project')
    try:
        assert cleanup_orphan_project_directories(sessionmaker(bind=engine), root) == []
    finally:
        engine.dispose()
    assert orphan.is_dir()
