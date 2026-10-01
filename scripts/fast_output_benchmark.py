"""Run the fast-output regression set through the product API and report time, cost and output.

    python scripts/fast_output_benchmark.py --server http://127.0.0.1:18765 --data-dir <AUTOCLIP_DATA_DIR> \
        [--cases id1,id2] [--baseline benchmarks/fast_output/reports/<old>.json]

Cases come from benchmarks/fast_output/cases.json and run one at a time (renders queue anyway).
Each run writes benchmarks/fast_output/reports/<timestamp>.json and .md. Numbers come from the
project's own records: stage timings and model tokens (metadata/llm_usage.jsonl), the studio state
(clips, variants, burned captions, source height). Nothing is published.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'benchmarks' / 'fast_output' / 'cases.json'
REPORTS = ROOT / 'benchmarks' / 'fast_output' / 'reports'
PRICE_IN, PRICE_OUT = 0.8e-6, 2e-6  # qwen-plus, ¥ per token (estimate; check the provider's price page)
TERMINAL = ('completed', 'partial', 'failed')


def api(server: str, path: str):
    with urllib.request.urlopen(f'{server}/api/v1/studio{path}', timeout=30) as response:
        return json.load(response)


def start(server: str, case: dict) -> str:
    args = ['curl', '-s', '-X', 'POST', f'{server}/api/v1/studio/import', '-F', f"url={case['url']}", '-F', f"name=bench-{case['id']}",
            '-F', 'auto_start=true', '-F', 'brand_outro_enabled=true']
    if 'youtube' in case['url']:
        args += ['-F', 'browser=chrome']
    for platform in case['platforms']:
        args += ['-F', f'platforms={platform}']
    reply = json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)
    if not reply.get('project_id'):
        raise RuntimeError(f'import refused: {reply}')
    return reply['project_id']


def wait(server: str, project_id: str, timeout_min: float) -> dict:
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        state = api(server, f'/{project_id}')
        generation, analysis = state.get('generation') or {}, state.get('analysis') or {}
        if generation.get('status') in TERMINAL or analysis.get('status') == 'failed':
            return state
        time.sleep(20)
    raise TimeoutError(f'{project_id} did not finish in {timeout_min} min')


def _seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    parse = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()  # noqa: E731
    return round(parse(end) - parse(start), 1)


def measure(case: dict, project_id: str, state: dict, data_dir: Path, wall: float) -> dict:
    metadata = data_dir / 'projects' / project_id / 'metadata'
    stages, timings = {}, {}
    usage = metadata / 'llm_usage.jsonl'
    for line in usage.read_text(encoding='utf-8').splitlines() if usage.exists() else []:
        row = json.loads(line)
        if row.get('kind') == 'timing':
            timings[row['stage']] = round(timings.get(row['stage'], 0) + row['seconds'], 1)
            continue
        item = stages.setdefault(row['stage'], {'calls': 0, 'in': 0, 'out': 0})
        item['calls'] += 1
        item['in'] += row.get('prompt_tokens') or 0
        item['out'] += row.get('completion_tokens') or 0
    tokens_in, tokens_out = sum(s['in'] for s in stages.values()), sum(s['out'] for s in stages.values())
    drafts = {d['id']: d for d in state.get('drafts', [])}
    variants = state.get('output_variants', [])
    lengths = sorted(round(sum(sc['end'] - sc['start'] for sc in drafts[v['draft_id']]['scenes'])) for v in variants if v['draft_id'] in drafts)
    generation, meta = state.get('generation') or {}, state.get('source_meta') or {}
    packaged = [drafts[v['draft_id']].get('packaging') for v in variants if v['draft_id'] in drafts and drafts[v['draft_id']].get('packaging')]
    return {
        'id': case['id'], 'project_id': project_id, 'platforms': case['platforms'],
        'outcome': generation.get('status') or (state.get('analysis') or {}).get('status'),
        'wall_min': round(wall / 60, 1), 'generation_min': round((_seconds(generation.get('started_at'), generation.get('finished_at')) or 0) / 60, 1),
        'timings_sec': timings,
        'calls': sum(s['calls'] for s in stages.values()), 'tokens_in': tokens_in, 'tokens_out': tokens_out,
        'yuan': round(tokens_in * PRICE_IN + tokens_out * PRICE_OUT, 3), 'stages': stages,
        'variants': len(variants), 'rendered': sum(v['status'] == 'completed' for v in variants),
        'on_demand': sum(v['status'] == 'on_demand' for v in variants), 'failed': sum(v['status'] == 'failed' for v in variants),
        'clip_sec': {'min': lengths[0], 'median': lengths[len(lengths) // 2], 'max': lengths[-1]} if lengths else None,
        'source_height': meta.get('source_height'), 'subtitle_source': meta.get('subtitle_source', 'speech'),
        'burned_captions': generation.get('source_has_burned_subtitles'), 'burned_caption_language': generation.get('burned_caption_language'),
        'packaging_fallbacks': sum(bool(p.get('fallback')) for p in packaged),
        'captioned_variants': sum(bool(p.get('cues')) for p in packaged),
        'titles': [' / '.join(drafts[v['draft_id']]['packaging']['title_lines']) for v in variants
                   if v['draft_id'] in drafts and (drafts[v['draft_id']].get('packaging') or {}).get('title_lines')][:6],
        'post_titles': [v['post']['title'] for v in variants if v.get('post')][:6],
    }


def markdown(results: list[dict], baseline: dict | None) -> str:
    old = {row['id']: row for row in (baseline or {}).get('results', [])}

    def delta(row, key):
        before = old.get(row['id'], {}).get(key)
        return f" ({row[key] - before:+.1f})" if isinstance(before, (int, float)) and isinstance(row.get(key), (int, float)) else ''

    lines = ['| case | outcome | minutes | transcribe s | clip finder s | render s | calls | tokens in/out | ¥ | clips → rendered | median clip s | source | burned | fallbacks |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for row in results:
        t = row.get('timings_sec', {})
        lines.append(f"| {row['id']} | {row['outcome']} | {row['generation_min']}{delta(row, 'generation_min')} | {t.get('transcribe', 0)} | {t.get('clip_finder', 0)} | "
                     f"{t.get('render', 0)} | {row['calls']} | {row['tokens_in']}/{row['tokens_out']} | {row['yuan']}{delta(row, 'yuan')} | "
                     f"{row['variants']} → {row['rendered']} | {(row['clip_sec'] or {}).get('median', '-')} | {row['source_height']}p {row['subtitle_source']} | "
                     f"{row['burned_captions']} {row['burned_caption_language'] or ''} | {row['packaging_fallbacks']} |")
    lines += ['', '人工检查：每条抽 2 支成片，看开头与结尾是否完整、字幕是否重复或不同步、取景是否对着说话人、封面与文案是否合适。']
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='http://127.0.0.1:18765')
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--cases', default='')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--timeout-min', type=float, default=120)
    args = parser.parse_args()
    cases = [c for c in json.loads(CASES.read_text(encoding='utf-8'))['cases'] if c.get('url')]
    if args.cases:
        by_id = {c['id']: c for c in cases}
        cases = [by_id[i] for i in args.cases.split(',') if i in by_id]  # run in the order given
    baseline = json.loads(args.baseline.read_text(encoding='utf-8')) if args.baseline else None
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M')
    results = []
    for case in cases:
        began = time.time()
        try:
            project_id = start(args.server, case)
            state = wait(args.server, project_id, args.timeout_min)
            results.append(measure(case, project_id, state, args.data_dir, time.time() - began))
        except Exception as error:  # noqa: BLE001 - one bad case must not lose the others
            results.append({'id': case['id'], 'outcome': f'error: {error}'[:200], 'generation_min': None, 'calls': 0, 'tokens_in': 0, 'tokens_out': 0,
                            'yuan': 0, 'variants': 0, 'rendered': 0, 'clip_sec': None, 'source_height': None, 'subtitle_source': None,
                            'burned_captions': None, 'burned_caption_language': None, 'packaging_fallbacks': 0, 'timings_sec': {}})
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
        report = {'created': stamp, 'results': results}
        (REPORTS / f'{stamp}.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
        (REPORTS / f'{stamp}.md').write_text(markdown(results, baseline), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
