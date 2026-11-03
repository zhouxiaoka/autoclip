"""Committed regression fixtures for the provider-e2e judge.

``live_24_of_40`` reconstructs GitHub Actions run 38508586808: DeepSeek /
DashScope / Infistar 8/8 succeed + 2/2 block; 88API and Gemini 0/8 succeed
(analysis-stage ``provider_error``, 0 billable) + 2/2 block. Overall 24/40.
The named provider-e2e job stayed GREEN because live failures were not
fail-closed into the aggregate check.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import SCHEMA_VERSION

TESTDATA_DIR = Path(__file__).resolve().parent
LIVE_24_OF_40_PATH = TESTDATA_DIR / 'live_24_of_40.json'
MOCK_PASS_PATH = TESTDATA_DIR / 'mock_pass.json'
VERIFY_UNDER_SAMPLE_PATH = TESTDATA_DIR / 'verify_under_sample.json'

SUCCEED_CLIPS = (
    'talk_zh', 'interview_zh', 'podcast_en', 'with_srt',
    'portrait', 'gameplay', 'sport', 'music',
)
BLOCK_CLIPS = ('too_short', 'no_audio')
HISTORICAL_PROVIDERS = (
    {
        'id': 'api88',
        'label': '88API',
        'model': 'gpt-4o-mini',
        'host': 'api.88api.ai',
        'succeed_ok': False,
        'error_class': 'unknown',
        'error_code': 'provider_error',
        'http_status': None,
        'phase': 'analyze',
    },
    {
        'id': 'deepseek',
        'label': 'DeepSeek',
        'model': 'deepseek-flash',
        'host': 'api.deepseek.com',
        'succeed_ok': True,
        'error_class': None,
        'error_code': None,
        'http_status': None,
        'phase': None,
    },
    {
        'id': 'gemini',
        'label': 'Gemini',
        'model': 'gemini-2.0-flash',
        'host': 'generativelanguage.googleapis.com',
        'succeed_ok': False,
        'error_class': 'unknown',
        'error_code': 'provider_error',
        'http_status': None,
        'phase': 'analyze',
    },
    {
        'id': 'dashscope',
        'label': 'DashScope',
        'model': 'qwen-plus',
        'host': 'dashscope.aliyuncs.com',
        'succeed_ok': True,
        'error_class': None,
        'error_code': None,
        'http_status': None,
        'phase': None,
    },
    {
        'id': 'infistar',
        'label': 'Infistar',
        'model': 'gpt-4o-mini',
        'host': 'infistar.ai',
        'succeed_ok': True,
        'error_class': None,
        'error_code': None,
        'http_status': None,
        'phase': None,
    },
)


def _case(provider: dict[str, Any], clip_id: str, expect: str) -> dict[str, Any]:
    ok = True if expect == 'block' else bool(provider['succeed_ok'])
    return {
        'id': f"{provider['id']}:{clip_id}",
        'label': f"{provider['label']} / {clip_id}",
        'expect': expect,
        'passed': ok,
        'provider_id': provider['id'],
        'clip_id': clip_id,
        'model': provider['model'],
        'error_class': None if ok else provider['error_class'],
        'error_code': None if ok else provider['error_code'],
        'http_status': None if ok else provider['http_status'],
        'phase': None if ok else provider['phase'],
        'billable_calls_before_failure': 0,
        'billable_calls': 0 if not ok or expect == 'block' else 3,
        'estimated_cost_cny': 0.0,
        'base_url_host': provider['host'],
    }


def live_24_of_40_report() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    planned: list[dict[str, Any]] = []
    providers = []
    records = []
    for provider in HISTORICAL_PROVIDERS:
        succeed_rows = [_case(provider, clip_id, 'succeed') for clip_id in SUCCEED_CLIPS]
        block_rows = [_case(provider, clip_id, 'block') for clip_id in BLOCK_CLIPS]
        cases.extend(succeed_rows)
        cases.extend(block_rows)
        for row in succeed_rows + block_rows:
            planned.append({
                'provider_id': row['provider_id'],
                'clip_id': row['clip_id'],
                'expect': row['expect'],
            })
            records.append({
                'run_id': '38508586808',
                'commit': '397b3683',
                'mode': 'historical_full_matrix',
                'provider': row['provider_id'],
                'clip_id': row['clip_id'],
                'expect': row['expect'],
                'passed': row['passed'],
                'model': row['model'],
                'error_class': row['error_class'],
                'http_status': row['http_status'],
            })
        providers.append({
            'id': provider['id'],
            'label': provider['label'],
            'model': provider['model'],
            'model_source': 'default',
            'base_url_host': provider['host'],
            'should_succeed_n': 8,
            'should_succeed_passed': 8 if provider['succeed_ok'] else 0,
            'should_block_n': 2,
            'should_block_passed': 2,
            'spent_cny': 0.0,
        })
    return {
        'schema_version': SCHEMA_VERSION,
        'suite': 'live',
        'status': 'completed',
        'mode': 'historical_full_matrix',
        'commit': '397b3683',
        'run_id': '38508586808',
        'cases': cases,
        'planned': planned,
        'case_records': records,
        'providers': providers,
        'spent_cny': 0.01,
        'note': 'Reconstructed from Actions run 38508586808. 24/40 succeed; 88API and Gemini failed in analysis.',
    }


def verify_under_sample_report() -> dict[str, Any]:
    """Actions 38511841070: nightly subset + paid probes; Gemini and 88API failed."""
    rows = [
        _case(HISTORICAL_PROVIDERS[1], 'talk_zh', 'succeed'),
        _case({**HISTORICAL_PROVIDERS[2], 'model': 'gemini-2.0-flash-lite'}, 'with_srt', 'succeed'),
        _case(HISTORICAL_PROVIDERS[1], 'too_short', 'block'),
        _case(HISTORICAL_PROVIDERS[0], 'talk_zh', 'succeed'),
        _case({**HISTORICAL_PROVIDERS[3], 'model': 'qwen-flash'}, 'talk_zh', 'succeed'),
        _case(HISTORICAL_PROVIDERS[4], 'talk_zh', 'succeed'),
    ]
    return {
        'schema_version': SCHEMA_VERSION,
        'suite': 'live',
        'status': 'completed',
        'mode': 'verify',
        'iso_week': 3,
        'commit': 'e50eadf0',
        'run_id': '38511841070',
        'cases': rows,
        'planned': [{'provider_id': row['provider_id'], 'clip_id': row['clip_id'], 'expect': row['expect']} for row in rows],
        'case_records': [{
            'run_id': '38511841070',
            'provider': row['provider_id'],
            'clip_id': row['clip_id'],
            'expect': row['expect'],
            'passed': row['passed'],
        } for row in rows],
        'providers': [
            {'id': 'deepseek', 'should_succeed_n': 1, 'should_succeed_passed': 1, 'should_block_n': 1, 'should_block_passed': 1},
            {'id': 'gemini', 'should_succeed_n': 1, 'should_succeed_passed': 0, 'should_block_n': 0, 'should_block_passed': 0},
            {'id': 'api88', 'should_succeed_n': 1, 'should_succeed_passed': 0, 'should_block_n': 0, 'should_block_passed': 0},
            {'id': 'dashscope', 'should_succeed_n': 1, 'should_succeed_passed': 1, 'should_block_n': 0, 'should_block_passed': 0},
            {'id': 'infistar', 'should_succeed_n': 1, 'should_succeed_passed': 1, 'should_block_n': 0, 'should_block_passed': 0},
        ],
        'spent_cny': 0.01,
    }


def mock_pass_report() -> dict[str, Any]:
    succeed = [
        {'id': f'mock:{clip_id}', 'expect': 'succeed', 'passed': True, 'billable_calls_before_failure': 3}
        for clip_id in SUCCEED_CLIPS
    ]
    blocked = [
        {'id': f'mock:{clip_id}', 'expect': 'block', 'passed': True, 'billable_calls_before_failure': 0}
        for clip_id in BLOCK_CLIPS
    ]
    return {
        'schema_version': SCHEMA_VERSION,
        'suite': 'mock',
        'status': 'completed',
        'commit': '397b3683',
        'cases': succeed + blocked,
    }
