"""项目枚举旧值不能让列表查询失败。

SQLAlchemy Enum 只按成员名查找。库里的 CANCELLED / pending 会在
``_object_value_for_elem`` 抛 LookupError，``Query.all()`` 整批失败
（Sentry PYTHON-FASTAPI-D，get_projects → get_all）。
"""

import enum

import pytest
from sqlalchemy import Column, Enum, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.core.project_enum_migration import normalize_legacy_project_enums
from backend.models.base import Base
from backend.models.project import Project, ProjectStatus, ProjectType
from backend.repositories.project_repository import ProjectRepository


def _insert(conn, project_id, status, project_type):
    conn.execute(
        text(
            "INSERT INTO projects "
            "(id, name, status, project_type, created_at, updated_at) "
            "VALUES (:id, :name, :status, :project_type, :created_at, :updated_at)"
        ),
        {
            "id": project_id,
            "name": project_id,
            "status": status,
            "project_type": project_type,
            "created_at": "2020-01-01 00:00:00",
            "updated_at": "2020-01-01 00:00:00",
        },
    )


def _engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Project.__table__])
    return engine


def test_stock_enum_lookup_error_on_legacy_values():
    """对照：标准 Enum 读到旧值时，整次 all() 失败。"""

    class Status(str, enum.Enum):
        PENDING = "pending"
        FAILED = "failed"

    BaseLocal = declarative_base()

    class Row(BaseLocal):
        __tablename__ = "rows"
        id = Column(String, primary_key=True)
        status = Column(Enum(Status), nullable=False)

    engine = create_engine("sqlite://")
    BaseLocal.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO rows (id, status) VALUES ('a', 'CANCELLED')"))
    session = sessionmaker(bind=engine)()
    with pytest.raises(LookupError, match="CANCELLED"):
        session.query(Row).all()


def test_legacy_rows_do_not_fail_project_list():
    engine = _engine()
    with engine.begin() as conn:
        _insert(conn, "ok", "PENDING", "KNOWLEDGE")
        _insert(conn, "cancelled", "CANCELLED", "DEFAULT")
        _insert(conn, "lower", "pending", "knowledge")
        _insert(conn, "weird", "not-a-status", "not-a-type")
    session = sessionmaker(bind=engine)()
    rows = {p.id: p for p in ProjectRepository(session).get_all(limit=100)}
    assert set(rows) == {"ok", "cancelled", "lower", "weird"}
    assert rows["ok"].status is ProjectStatus.PENDING
    assert rows["ok"].project_type is ProjectType.KNOWLEDGE
    assert rows["cancelled"].status is ProjectStatus.FAILED
    assert rows["lower"].status is ProjectStatus.PENDING
    assert rows["lower"].project_type is ProjectType.KNOWLEDGE
    assert rows["weird"].status is ProjectStatus.FAILED
    assert rows["weird"].project_type is ProjectType.DEFAULT


def test_normalize_rewrites_legacy_values_and_is_idempotent():
    engine = _engine()
    with engine.begin() as conn:
        _insert(conn, "cancelled", "cancelled", "speech")
        _insert(conn, "name", "COMPLETED", "DEFAULT")
    assert normalize_legacy_project_enums(engine) == 2
    with engine.connect() as conn:
        stored = {
            row.id: (row.status, row.project_type)
            for row in conn.execute(text("SELECT id, status, project_type FROM projects"))
        }
    assert stored["cancelled"] == ("FAILED", "SPEECH")
    assert stored["name"] == ("COMPLETED", "DEFAULT")
    assert normalize_legacy_project_enums(engine) == 0


def test_orm_write_still_persists_enum_names():
    engine = _engine()
    session = sessionmaker(bind=engine)()
    session.add(Project(
        id="new",
        name="new",
        status="pending",
        project_type=ProjectType.BUSINESS,
    ))
    session.commit()
    with engine.connect() as conn:
        status, project_type = conn.execute(
            text("SELECT status, project_type FROM projects WHERE id = 'new'")
        ).one()
    assert status == "PENDING"
    assert project_type == "BUSINESS"
