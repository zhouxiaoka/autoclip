#!/usr/bin/env python3
"""Save kill-time heartbeat fields and a closed downloader token.

Prints JSON only. Does not echo downloader text, URLs, hosts, or keys.
Does not kill processes and does not change hosts or firewall rules.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INSTANCE = re.compile(r'^[0-9a-f]{32}$')
STAGES = frozenset({'screening', 'download', 'subtitle', 'analyze', 'render', 'idle'})


def heartbeat_rows(marker_dir: Path, observed_pid: int | None = None) -> list[dict]:
    """One row per ``<instance>.hb``. Only ts, stage, and optional pids."""
    rows = []
    if not marker_dir.is_dir():
        return rows
    for path in sorted(marker_dir.glob('*.hb')):
        instance = path.name[:-3]
        if path.name.startswith('.') or not INSTANCE.fullmatch(instance):
            continue
        row: dict = {'instance': instance, 'readable': False, 'ts': None, 'stage': None}
        try:
            data = json.loads(path.read_text(encoding='ascii'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            rows.append(row)
            continue
        if isinstance(data, dict):
            ts = data.get('ts')
            stage = data.get('stage')
            row['readable'] = True
            row['ts'] = ts if isinstance(ts, (int, float)) else None
            row['stage'] = stage if stage in STAGES else None
            file_pid = data.get('pid')
            if isinstance(file_pid, int) and not isinstance(file_pid, bool):
                row['file_pid'] = file_pid
        if observed_pid is not None:
            row['observed_pid'] = observed_pid
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Sanitized acceptance capture')
    sub = parser.add_subparsers(dest='command', required=True)

    beat = sub.add_parser('heartbeat')
    beat.add_argument('--marker-dir', required=True)
    beat.add_argument('--pid', type=int)

    down = sub.add_parser('download-error')
    down.add_argument('--exception-type', required=True)
    down.add_argument('--seconds', type=float, required=True)
    down.add_argument('--text-file', required=True)

    args = parser.parse_args(argv)
    if args.command == 'heartbeat':
        payload = {'rows': heartbeat_rows(Path(args.marker_dir), args.pid)}
    else:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', args.exception_type):
            raise SystemExit('exception type must be a plain identifier')
        if args.seconds < 0:
            raise SystemExit('seconds must be >= 0')
        text = Path(args.text_file).read_text(encoding='utf-8', errors='replace')
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root))
        from backend.utils.download_failure_observe import observe_download_failure
        observed = observe_download_failure(text)
        payload = {
            'exception_type': args.exception_type,
            'seconds': args.seconds,
            'token': observed['token'],
            'code': observed['code'],
        }
    json.dump(payload, sys.stdout, ensure_ascii=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
