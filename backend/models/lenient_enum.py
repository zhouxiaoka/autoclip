"""读取时不因未知枚举值抛 LookupError 的 SQLAlchemy Enum。

SQLAlchemy 的 Enum 默认把 PEP 435 成员的 **名字**（``PENDING``）写入数据库，
不是 ``.value``（``pending``）。结果处理器 ``_object_value_for_elem`` 只按名字查找；
对不上就抛 ``LookupError``，``Query.all()`` 整批失败。

桌面 / Docker 的 SQLite 把枚举存成 VARCHAR，旧行可以留下：

- 已从代码删除的成员名，例如 ``ProjectStatus.CANCELLED``（2025-08-06 移除）
- 成员的 value 形式（``pending`` 而不是 ``PENDING``）
- 其它任意字符串（``validate_strings`` 默认为 False，写入时不会拦住）

本类型在查找失败时：能按 value 对上的仍返回该成员；其余返回 ``fallback``。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import Enum as SAEnum

logger = logging.getLogger(__name__)

# 方言适配会复制类型对象，且不会带上自定义构造参数。按枚举类记住 fallback。
_FALLBACKS: dict = {}
_warned: set = set()


def match_enum_member(enum_cls: Optional[type], raw):
    """按成员名或 value 匹配。对不上返回 None，不使用 fallback。"""
    if raw is None or enum_cls is None:
        return None
    if isinstance(raw, enum_cls):
        return raw
    if isinstance(raw, str):
        member = enum_cls.__members__.get(raw)
        if member is not None:
            return member
        for member in enum_cls:
            if raw == member.value:
                return member
    return None


class LenientEnum(SAEnum):
    """未知数据库值读成 fallback，而不是让整次查询失败。"""

    def __init__(self, *enums, fallback=None, **kw):
        enum_cls = None
        if len(enums) == 1 and isinstance(enums[0], type):
            enum_cls = enums[0]
        if enum_cls is not None and fallback is not None:
            _FALLBACKS[enum_cls] = fallback
        super().__init__(*enums, **kw)
        if fallback is not None:
            self.fallback = fallback
        else:
            self.fallback = _FALLBACKS.get(self.enum_class)

    def _object_value_for_elem(self, elem: str):
        try:
            return super()._object_value_for_elem(elem)
        except LookupError:
            enum_cls = self.enum_class
            matched = match_enum_member(enum_cls, elem)
            if matched is not None:
                return matched
            fallback = self.fallback if self.fallback is not None else _FALLBACKS.get(enum_cls)
            if fallback is None:
                raise
            self._warn_once(elem, fallback)
            return fallback

    def _warn_once(self, elem, fallback) -> None:
        key = (getattr(self, "name", None), elem if isinstance(elem, str) else repr(elem))
        if key in _warned:
            return
        _warned.add(key)
        shown = elem if isinstance(elem, str) else repr(elem)
        if len(shown) > 80:
            shown = shown[:80] + "…"
        logger.warning(
            "数据库枚举 %s 含未识别值 %r，读取时按 %s 处理",
            getattr(self, "name", None),
            shown,
            getattr(fallback, "name", fallback),
        )
