"""把 projects.status / projects.project_type 里的旧值改成当前枚举名。

启动时运行，幂等。桌面端和 Docker 都没有单独的 Alembic 迁移步骤，
``create_all`` 也不会改已有 SQLite 行，所以清洗放在建表之后。

规则（只改这两个字段，不删除项目）：

- 已经是成员名（``PENDING``）的保持不动
- 成员 value（``pending``）改成对应的名字（``PENDING``）
- 无法识别的 status（含已删除的 ``cancelled`` / ``CANCELLED``）改成 ``FAILED``
- 无法识别的 project_type 改成 ``DEFAULT``

手工查看（升级前可选）::

    SELECT status, COUNT(*) FROM projects GROUP BY status;
    SELECT project_type, COUNT(*) FROM projects GROUP BY project_type;
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from backend.models.lenient_enum import match_enum_member
from backend.models.project import ProjectStatus, ProjectType

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("status", ProjectStatus, ProjectStatus.FAILED),
    ("project_type", ProjectType, ProjectType.DEFAULT),
)


def normalize_legacy_project_enums(engine: Engine) -> int:
    """改写无法被当前枚举直接读出的项目行。返回更新的行数。"""
    inspector = inspect(engine)
    if not inspector.has_table("projects"):
        return 0
    present = {col["name"] for col in inspector.get_columns("projects")}
    updated = 0
    with engine.begin() as conn:
        for column, enum_cls, fallback in _COLUMNS:
            if column not in present:
                continue
            updated += _rewrite_column(conn, column, enum_cls, fallback)
    return updated


def _rewrite_column(conn, column: str, enum_cls, fallback) -> int:
    rows = conn.execute(text(f"SELECT DISTINCT {column} FROM projects")).fetchall()
    changed = 0
    for (raw,) in rows:
        if not isinstance(raw, str):
            continue
        matched = match_enum_member(enum_cls, raw)
        target = matched.name if matched is not None else fallback.name
        if target == raw:
            continue
        result = conn.execute(
            text(f"UPDATE projects SET {column} = :target WHERE {column} = :raw"),
            {"target": target, "raw": raw},
        )
        count = result.rowcount or 0
        changed += count
        logger.info("项目 %s：%r → %s（%s 行）", column, raw, target, count)
    return changed
