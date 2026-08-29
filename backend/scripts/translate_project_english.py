"""Translate existing clip/collection text for one project into English."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm.attributes import flag_modified

from backend.core.database import SessionLocal
from backend.models.clip import Clip
from backend.models.collection import Collection
from backend.utils.llm_client import LLMClient

PROJECT_ID = "62fa0f3e-2217-413c-b624-354458d25eaa"


def main() -> None:
    db = SessionLocal()
    try:
        clips = db.query(Clip).filter(Clip.project_id == PROJECT_ID).all()
        collections = db.query(Collection).filter(Collection.project_id == PROJECT_ID).all()
        payload = {
            "clips": [
                {
                    "id": str(c.id),
                    "title": c.title or "",
                    "outline": (c.clip_metadata or {}).get("outline", ""),
                    "recommend_reason": (c.clip_metadata or {}).get("recommend_reason")
                    or (c.recommendation_reason or ""),
                    "content": (c.clip_metadata or {}).get("content") or [],
                }
                for c in clips
            ],
            "collections": [
                {
                    "id": str(col.id),
                    "name": col.name or "",
                    "description": col.description or "",
                }
                for col in collections
            ],
        }

        prompt = """Translate this project's clip and collection copy into natural English for a gaming VOD.
Keep JSON shape. Do not change ids. Keep content as a list of short bullets.
Return JSON only:
{"clips": {"<id>": {"title": "", "outline": "", "recommend_reason": "", "content": []}},
 "collections": {"<id>": {"name": "", "description": ""}}}
"""
        client = LLMClient()
        raw = client.call_with_retry(prompt, payload)
        translated = client.parse_json_response(raw)
        clip_map = translated.get("clips") or {}
        col_map = translated.get("collections") or {}

        old_clip_keys = {
            str(c.id): {
                "title": c.title or "",
                "outline": (c.clip_metadata or {}).get("outline", ""),
            }
            for c in clips
        }
        old_col_names = {str(col.id): col.name or "" for col in collections}

        for clip in clips:
            item = clip_map.get(str(clip.id)) or {}
            if item.get("title"):
                clip.title = item["title"][:255]
            meta = dict(clip.clip_metadata or {})
            if item.get("outline"):
                meta["outline"] = item["outline"]
            if item.get("recommend_reason"):
                meta["recommend_reason"] = item["recommend_reason"]
                clip.recommendation_reason = item["recommend_reason"]
            if item.get("content"):
                meta["content"] = item["content"]
            if item.get("title"):
                meta["generated_title"] = item["title"]
            clip.clip_metadata = meta
            flag_modified(clip, "clip_metadata")

        for col in collections:
            item = col_map.get(str(col.id)) or {}
            if item.get("name"):
                col.name = item["name"][:255]
            if item.get("description") is not None:
                col.description = item["description"]

        db.commit()
        print(f"updated {len(clips)} clips, {len(collections)} collections")
        _update_metadata_files(clip_map, old_clip_keys, col_map, old_col_names)
    finally:
        db.close()


def _update_metadata_files(clip_map, old_clip_keys, col_map, old_col_names) -> None:
    meta_dir = ROOT / "data" / "projects" / PROJECT_ID / "metadata"
    clips_path = meta_dir / "clips_metadata.json"
    cols_path = meta_dir / "collections_metadata.json"

    if clips_path.exists():
        data = json.loads(clips_path.read_text(encoding="utf-8"))
        for rec in data:
            for clip_id, old in old_clip_keys.items():
                item = clip_map.get(clip_id) or {}
                if rec.get("generated_title") == old["title"] or rec.get("outline") == old["outline"]:
                    if item.get("title"):
                        rec["generated_title"] = item["title"]
                    if item.get("outline"):
                        rec["outline"] = item["outline"]
                    if item.get("recommend_reason"):
                        rec["recommend_reason"] = item["recommend_reason"]
                    if item.get("content"):
                        rec["content"] = item["content"]
                    break
        clips_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if cols_path.exists():
        data = json.loads(cols_path.read_text(encoding="utf-8"))
        for rec in data:
            for col_id, old_name in old_col_names.items():
                item = col_map.get(col_id) or {}
                if rec.get("collection_title") == old_name:
                    if item.get("name"):
                        rec["collection_title"] = item["name"]
                    if item.get("description") is not None:
                        rec["collection_summary"] = item["description"]
                    break
        cols_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
