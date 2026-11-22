#!/usr/bin/env python3
"""Check a desktop build's telemetry environment without changing it.

A release launcher always injects production. Validation is a separate build:
frontend VITE_TELEMETRY_VALIDATION=true and a backend started with
AUTOCLIP_BUILD_ENVIRONMENT=validation. This script refuses to treat a
validation observation as a release package, and it does not rewrite either.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ALLOWED = ('AUTOCLIP_BUILD_ENVIRONMENT', 'AUTOCLIP_APP_VERSION', 'AUTOCLIP_MODE')
ENVIRONMENTS = frozenset({'production', 'validation', 'development'})

VALIDATION_BUILD = {
    'frontend': 'VITE_TELEMETRY_VALIDATION=true',
    'backend': 'AUTOCLIP_BUILD_ENVIRONMENT=validation',
    'not_the_release_launcher': (
        'BackendManager::start overwrites AUTOCLIP_BUILD_ENVIRONMENT to '
        'production on a release build. Do not add an opt-in on that path.'
    ),
}


def read_observation(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise SystemExit('observation must be a JSON object')
    extra = sorted(set(data) - set(ALLOWED))
    if extra:
        raise SystemExit('observation has keys outside the allow list')
    environment = data.get('AUTOCLIP_BUILD_ENVIRONMENT')
    version = data.get('AUTOCLIP_APP_VERSION')
    mode = data.get('AUTOCLIP_MODE')
    if environment not in ENVIRONMENTS:
        raise SystemExit('build environment missing or not a closed value')
    if not isinstance(version, str) or not version.strip() or version.strip().lower() == 'unknown':
        raise SystemExit('app version required')
    if mode != 'desktop':
        raise SystemExit('desktop mode required')
    return {
        'AUTOCLIP_BUILD_ENVIRONMENT': environment,
        'AUTOCLIP_APP_VERSION': version.strip(),
        'AUTOCLIP_MODE': mode,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Verify telemetry environment')
    parser.add_argument('--observed', type=Path)
    parser.add_argument('--expect', choices=('production', 'validation'), default='production')
    parser.add_argument('--print-validation-build', action='store_true')
    args = parser.parse_args(argv)
    if args.print_validation_build and args.observed is None:
        json.dump(VALIDATION_BUILD, sys.stdout, ensure_ascii=True)
        sys.stdout.write('\n')
        return 0
    if args.observed is None:
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / 'scripts'))
        import macos_release_contract as contract
        raise SystemExit('pass --observed, or --print-validation-build; launcher contract is production-only via ' + contract.__name__)
    observed = read_observation(args.observed)
    if observed['AUTOCLIP_BUILD_ENVIRONMENT'] != args.expect:
        raise SystemExit(
            f"observed {observed['AUTOCLIP_BUILD_ENVIRONMENT']} != expected {args.expect}; "
            'a release package stays production'
        )
    json.dump({'ok': True, **observed}, sys.stdout, ensure_ascii=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
