"""Fix leftover Chinese copy and recut the current project at 1080p60."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm.attributes import flag_modified

from backend.api.v1.youtube import YOUTUBE_PLAYER_CLIENTS, YOUTUBE_VIDEO_FORMAT
from backend.core.database import SessionLocal
from backend.models.clip import Clip
from backend.models.collection import Collection
from backend.utils.video_processor import VideoProcessor

PROJECT_ID = "62fa0f3e-2217-413c-b624-354458d25eaa"
URL = "https://youtube.com/live/6Kd3CDx96ug?feature=share"


def _project_paths() -> dict[str, Path]:
    project_dir = ROOT / "data" / "projects" / PROJECT_ID
    return {
        "raw": project_dir / "raw" / "input.mp4",
        "clips": project_dir / "output" / "clips",
        "collections": project_dir / "output" / "collections",
        "meta": project_dir / "metadata",
    }


def fix_remaining_chinese() -> None:
    paths = _project_paths()
    clips_meta_path = paths["meta"] / "clips_metadata.json"
    cols_meta_path = paths["meta"] / "collections_metadata.json"
    clips_meta = json.loads(clips_meta_path.read_text(encoding="utf-8"))
    cols_meta = json.loads(cols_meta_path.read_text(encoding="utf-8"))

    (paths["meta"] / "step4_titles.json").write_text(
        json.dumps(clips_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (paths["meta"] / "step5_collections.json").write_text(
        json.dumps(cols_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    by_pipeline_id = {str(item.get("id")): item for item in clips_meta}

    db = SessionLocal()
    try:
        clips = db.query(Clip).filter(Clip.project_id == PROJECT_ID).all()
        for clip in clips:
            meta = dict(clip.clip_metadata or {})
            pipeline_id = str(meta.get("id") or "")
            item = by_pipeline_id.get(pipeline_id)
            if not item:
                continue
            clip.title = (item.get("generated_title") or clip.title or "")[:255]
            reason = item.get("recommend_reason") or clip.recommendation_reason or ""
            clip.recommendation_reason = reason
            clip.description = reason
            meta.update(
                {
                    "generated_title": item.get("generated_title") or clip.title,
                    "outline": item.get("outline") or meta.get("outline"),
                    "recommend_reason": reason,
                    "content": item.get("content") or meta.get("content") or [],
                    "start_time": item.get("start_time") or meta.get("start_time"),
                    "end_time": item.get("end_time") or meta.get("end_time"),
                }
            )
            clip.clip_metadata = meta
            flag_modified(clip, "clip_metadata")

        collections = db.query(Collection).filter(Collection.project_id == PROJECT_ID).all()
        by_name = {c.name: c for c in collections}
        for rec in cols_meta:
            col = by_name.get(rec.get("collection_title"))
            if not col:
                continue
            col.description = rec.get("collection_summary") or col.description
            meta = dict(col.collection_metadata or {})
            meta["clip_ids"] = rec.get("clip_ids") or meta.get("clip_ids") or []
            col.collection_metadata = meta
            flag_modified(col, "collection_metadata")
        db.commit()
        print("updated remaining Chinese copy in database and step JSON")
    finally:
        db.close()


def download_1080p60(dest: Path) -> Path:
    import yt_dlp

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = dest.parent / "_download_1080p"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(tmp_dir / "input.%(ext)s")
    opts = {
        "format": YOUTUBE_VIDEO_FORMAT,
        "format_sort": ["res:1080", "fps", "codec:h264:vp9", "size"],
        "merge_output_format": "mp4",
        "writesubtitles": False,
        "writeautomaticsub": False,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "ignoreconfig": True,
        "config_locations": [],
        "cachedir": False,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "extractor_args": {"youtube": {"player_client": list(YOUTUBE_PLAYER_CLIENTS)}},
    }
    print("downloading 1080p60…")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([URL])

    files = [p for p in tmp_dir.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm"}]
    if not files:
        raise RuntimeError("1080p download produced no video file")
    downloaded = max(files, key=lambda p: p.stat().st_size)

    bak = dest.with_suffix(".mp4.360p.bak")
    if dest.exists() and dest.stat().st_size < 800 * 1024 * 1024:
        dest.replace(bak)
    if dest.exists():
        dest.unlink()
    shutil.move(str(downloaded), dest)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"saved {dest} ({dest.stat().st_size} bytes)")
    return dest


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError as exc:
        print(f"warning: could not delete {path.name}: {exc}")


def recut_outputs(input_video: Path) -> None:
    paths = _project_paths()
    clips_meta = json.loads((paths["meta"] / "clips_metadata.json").read_text(encoding="utf-8"))
    cols_meta = json.loads((paths["meta"] / "collections_metadata.json").read_text(encoding="utf-8"))

    # Write to fresh dirs so locked legacy files do not block the upgrade.
    clips_out = paths["clips"].parent / "clips_1080p60"
    cols_out = paths["collections"].parent / "collections_1080p60"
    if clips_out.exists():
        shutil.rmtree(clips_out, ignore_errors=True)
    if cols_out.exists():
        shutil.rmtree(cols_out, ignore_errors=True)
    clips_out.mkdir(parents=True, exist_ok=True)
    cols_out.mkdir(parents=True, exist_ok=True)

    processor = VideoProcessor(str(clips_out), str(cols_out))
    for old in paths["clips"].glob("*.mp4"):
        _safe_unlink(old)
    for old in paths["collections"].glob("*"):
        if old.is_file():
            _safe_unlink(old)

    clips_data = [
        {
            "id": item["id"],
            "title": item.get("generated_title") or f"clip_{item['id']}",
            "start_time": item["start_time"],
            "end_time": item["end_time"],
        }
        for item in clips_meta
    ]
    print(f"extracting {len(clips_data)} clips…")
    processor.batch_extract_clips(input_video, clips_data)
    print("building collections…")
    processor.create_collections_from_metadata(cols_meta)
    _update_db_paths(paths, clips_meta, cols_meta, clips_out, cols_out)


def _update_db_paths(
    paths: dict[str, Path],
    clips_meta,
    cols_meta,
    clips_out: Path | None = None,
    cols_out: Path | None = None,
) -> None:
    clips_dir = clips_out or paths["clips"]
    cols_dir = cols_out or paths["collections"]
    db = SessionLocal()
    try:
        clips = db.query(Clip).filter(Clip.project_id == PROJECT_ID).all()
        for clip in clips:
            pipeline_id = str((clip.clip_metadata or {}).get("id") or "")
            matches = list(clips_dir.glob(f"{pipeline_id}_*.mp4"))
            if matches:
                clip.video_path = str(matches[0])

        by_title = {rec["collection_title"]: rec for rec in cols_meta}
        collections = db.query(Collection).filter(Collection.project_id == PROJECT_ID).all()
        for col in collections:
            rec = by_title.get(col.name)
            if not rec:
                continue
            safe = VideoProcessor.sanitize_filename(col.name)
            video = cols_dir / f"{safe}.mp4"
            thumbs = list(cols_dir.glob(f"{rec['id']}_{safe}_thumbnail.jpg"))
            if not thumbs:
                thumbs = list(cols_dir.glob(f"*_{safe}_thumbnail.jpg"))
            if not thumbs:
                thumbs = list(cols_dir.glob(f"{safe}_thumbnail.jpg"))
            if video.exists():
                col.export_path = str(video)
                col.video_path = str(video)
            if thumbs:
                col.thumbnail_path = str(thumbs[0])
        db.commit()
        print("updated clip/collection file paths")
    finally:
        db.close()


if __name__ == "__main__":
    fix_remaining_chinese()
    paths = _project_paths()
    raw = paths["raw"]
    if not raw.exists() or raw.stat().st_size < 800 * 1024 * 1024:
        download_1080p60(raw)
    else:
        print(f"using existing source {raw} ({raw.stat().st_size} bytes)")
    recut_outputs(raw)
    print("done")
