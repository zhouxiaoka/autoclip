#!/usr/bin/env python3
"""#414 v5: writes the verdict that winqa_chain.verify_chain decided. This file judges nothing (M6).

    winqa_verdict.py final --out OUT --run-id ID --dest FILE      exit 0 only when the chain passed; 70 when the
                                                                  log_channel step failed; 1 otherwise
R31 I438: run once, after logpipe_close and the log_channel receipt. Nothing rewrites the verdict afterwards: the
same evidence gives the same verdict.json and steps.txt, byte for byte.
"""
import json, sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
import winqa_plan as wp  # noqa: E402
import winqa_chain as wc  # noqa: E402

SCHEMA = wc.SCHEMA
step_results = wc.step_results


def evaluate(out: Path, run_id: str):
    return wc.verify_chain(out, run_id, 'final').as_dict(run_id)


def check_binding(out: Path, verdict) -> bool:
    """summarize.py: a verdict is rendered only if verify_chain(render) recomputed now gives the same result."""
    try:
        now = wc.verify_chain(out, verdict['run_id'], 'render')
    except Exception:
        return False
    return now.binding == verdict.get('binding') and now.overall == verdict.get('overall')


def main(a):
    if not a or a[0] != 'final':
        print(__doc__, file=sys.stderr); return 2
    out = Path(wp._arg(a, '--out'))
    R = wc.verify_chain(out, wp._arg(a, '--run-id'), 'final')
    v = R.as_dict(wp._arg(a, '--run-id'))
    dest = Path(wp._arg(a, '--dest'))
    dest.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'steps.txt').write_text(''.join(f'{k}={v_}\n' for k, v_ in sorted(v['steps'].items())), encoding='utf-8')
    if R.passed:
        return 0
    return 70 if v['steps'].get(wc.LOG_CHANNEL) == 'FAIL' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
