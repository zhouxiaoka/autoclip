"""把片源下载进度写进项目的 processing_config。

SQLAlchemy 的 JSON 列发现不了原地 ``dict.update()``。YouTube / B 站下载
因此一直停在创建项目时写入的 0%。项目卡第一次渲染又把没有下载字段的
pending 画成 5%，进度条如果记住这个初值，就会一直显示约 5%。
"""

from typing import Any, Dict, Optional

from sqlalchemy.orm.attributes import flag_modified


def merge_processing_config(current: Optional[dict], updates: Dict[str, Any]) -> dict:
    """返回新 dict。保留 download_status、youtube_info 等已有字段。"""
    merged = dict(current or {})
    merged.update(updates)
    return merged


def save_processing_config(project, updates: Dict[str, Any]) -> dict:
    """赋一个新 dict，让本次提交能看到下载进度。"""
    merged = merge_processing_config(getattr(project, "processing_config", None), updates)
    project.processing_config = merged
    flag_modified(project, "processing_config")
    return merged
