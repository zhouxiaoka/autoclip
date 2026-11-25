"""CLI entrypoint for AutoClip's internal viral template discovery pipeline.

Examples:
  # 1. Run multi-platform discovery (YouTube via Apify or yt-dlp fallback + Bilibili)
  python scripts/template_discovery/cli.py run --tracks gaming,interview --limit 3 --out /tmp/ac-discovery

  # 2. Analyze a local folder of reference clips (zero network calls)
  python scripts/template_discovery/cli.py analyze-local /path/to/clips --track gaming --out /tmp/ac-local-discovery
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.template_discovery.analyzer import analyze_candidate  # noqa: E402
from scripts.template_discovery.report import write_report  # noqa: E402
from scripts.template_discovery.sources import (  # noqa: E402
    CandidateVideo,
    fetch_bilibili_search,
    fetch_youtube_apify,
    fetch_youtube_ytdlp,
    scan_local_folder,
)

DEFAULT_CONFIG = Path(__file__).resolve().parent / 'config.yaml'


def _shipping_template_ids() -> set[str]:
    ids: set[str] = {'editorial', 'street', 'news', 'cinema', 'classic'}
    cat = REPO_ROOT / 'templates-catalog'
    if cat.is_dir():
        for p in cat.iterdir():
            if p.is_dir() and (p / 'template.yaml').is_file():
                ids.add(p.name)
    return ids


def cmd_run(args: argparse.Namespace) -> int:
    cfg = yaml.safe_load(Path(args.config).read_text(encoding='utf-8')) or {}
    defaults = cfg.get('defaults') or {}
    tracks_cfg = cfg.get('tracks') or {}
    selected_tracks = [t.strip() for t in args.tracks.split(',') if t.strip()] if args.tracks else list(tracks_cfg.keys())
    limit = int(args.limit or defaults.get('limit_per_query', 5))
    max_dur = float(defaults.get('max_duration_sec', 120))
    actor = str(defaults.get('apify_youtube_actor') or 'streamers~youtube-scraper')
    source_mode = args.source

    candidates: list[CandidateVideo] = []
    for tname in selected_tracks:
        tcfg = tracks_cfg.get(tname)
        if not isinstance(tcfg, dict):
            continue
        yt_queries = list(tcfg.get('youtube_queries') or [])
        bili_queries = list(tcfg.get('bilibili_queries') or [])
        if args.max_queries > 0:
            yt_queries = yt_queries[:args.max_queries]
            bili_queries = bili_queries[:args.max_queries]

        if source_mode in ('auto', 'apify', 'ytdlp') and yt_queries:
            yt_hits: list[CandidateVideo] = []
            if source_mode in ('auto', 'apify') and os.getenv('APIFY_TOKEN'):
                yt_hits = fetch_youtube_apify(yt_queries, track=tname, limit_per_query=limit, actor=actor)
            if not yt_hits and source_mode in ('auto', 'ytdlp'):
                yt_hits = fetch_youtube_ytdlp(yt_queries, track=tname, limit_per_query=limit, max_duration_sec=max_dur)
            candidates.extend(yt_hits)

        if source_mode in ('auto', 'bilibili') and bili_queries:
            candidates.extend(fetch_bilibili_search(bili_queries, track=tname, limit_per_query=limit, max_duration_sec=max_dur))

    out_dir = Path(args.out).resolve()
    existing = _shipping_template_ids()
    analyzed = [(c, analyze_candidate(c, out_dir, existing_catalog_ids=existing)) for c in candidates]
    outputs = write_report(analyzed, out_dir)
    print(f'Discovered & analyzed {len(analyzed)} candidates -> {outputs["markdown"]}')
    return 0


def cmd_analyze_local(args: argparse.Namespace) -> int:
    folder = Path(args.folder).resolve()
    candidates = scan_local_folder(folder, track=args.track)
    out_dir = Path(args.out).resolve()
    existing = _shipping_template_ids()
    analyzed = [(c, analyze_candidate(c, out_dir, existing_catalog_ids=existing)) for c in candidates]
    outputs = write_report(analyzed, out_dir)
    print(f'Analyzed {len(analyzed)} local clips -> {outputs["markdown"]}')
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    parser = argparse.ArgumentParser(description='AutoClip viral template discovery pipeline')
    sub = parser.add_subparsers(dest='command', required=True)

    p_run = sub.add_parser('run', help='Discover viral candidates from YouTube (Apify/yt-dlp) and Bilibili')
    p_run.add_argument('--config', default=str(DEFAULT_CONFIG))
    p_run.add_argument('--tracks', default='', help='Comma-separated track names (default: all)')
    p_run.add_argument('--source', choices=('auto', 'apify', 'ytdlp', 'bilibili'), default='auto')
    p_run.add_argument('--limit', type=int, default=3, help='Results per query')
    p_run.add_argument('--max-queries', type=int, default=2, help='Cap queries per track (0=all)')
    p_run.add_argument('--out', required=True, help='Output directory for report, JSON, and contact sheet')
    p_run.set_defaults(func=cmd_run)

    p_loc = sub.add_parser('analyze-local', help='Analyze a local directory of reference videos')
    p_loc.add_argument('folder', help='Directory containing .mp4/.mov/.mkv/.webm clips')
    p_loc.add_argument('--track', default='gaming', help='Track label (gaming, interview, knowledge)')
    p_loc.add_argument('--out', required=True, help='Output directory for report, JSON, and contact sheet')
    p_loc.set_defaults(func=cmd_analyze_local)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
