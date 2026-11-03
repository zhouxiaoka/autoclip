"""Conservative CNY estimates for live provider-e2e calls.

Rates are public-list overestimates so the monthly cap trips early rather than
late. Actual bills still come from each vendor dashboard.
"""
from __future__ import annotations

from typing import Any

# (prompt, completion) CNY per 1M tokens. Unknown models use the fallback.
RATES_CNY_PER_M: dict[str, tuple[float, float]] = {
    'deepseek-flash': (0.6, 2.4),
    'deepseek-v4-flash': (0.6, 2.4),
    'deepseek-chat': (2.5, 10.0),
    'gemini-2.0-flash-lite': (0.6, 2.4),
    'gemini-2.0-flash': (0.8, 3.2),
    'gemini-2.5-flash-lite': (0.7, 2.8),
    'gemini-2.5-flash': (1.2, 5.0),
    'gemini-3.5-flash-lite': (0.8, 3.2),
    'gpt-4o-mini': (1.2, 4.8),
    'qwen-flash': (0.4, 1.6),
    'qwen-turbo': (0.4, 1.2),
    'qwen-plus': (2.4, 7.2),
}

FALLBACK_RATE_CNY_PER_M = (6.0, 18.0)
DEFAULT_SUCCEED_TOKENS = (15_000, 4_000)
DEFAULT_BLOCK_TOKENS = (0, 0)

MONTHLY_BUDGET_CNY = 300.0
PER_RUN_CAP_CNY = {
    'nightly': 15.0,
    'verify': 25.0,
    'prerelease': 40.0,
    'api88': 8.0,
}
PER_PROVIDER_CAP_CNY = {
    'nightly': 8.0,
    'verify': 10.0,
    'prerelease': 12.0,
    'api88': 8.0,
}


def rate_for(model: str | None) -> tuple[float, float]:
    key = (model or '').strip().lower()
    if key in RATES_CNY_PER_M:
        return RATES_CNY_PER_M[key]
    for prefix, rate in RATES_CNY_PER_M.items():
        if key.startswith(prefix):
            return rate
    return FALLBACK_RATE_CNY_PER_M


def tokens_cny(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = rate_for(model)
    return round(
        (max(0, int(prompt_tokens)) * prompt_rate + max(0, int(completion_tokens)) * completion_rate) / 1_000_000,
        4,
    )


def estimate_case_cny(model: str | None, expect: str) -> float:
    prompt, completion = DEFAULT_BLOCK_TOKENS if expect == 'block' else DEFAULT_SUCCEED_TOKENS
    return tokens_cny(model, prompt, completion)


def estimate_plan_cny(assignments: list[dict[str, Any]]) -> float:
    total = 0.0
    for row in assignments:
        model = row.get('model') or (row.get('provider') or {}).get('default_model')
        expect = (row.get('asset') or {}).get('expect') or row.get('expect') or 'succeed'
        total += estimate_case_cny(model, expect)
    return round(total, 4)


def usage_tokens(rows: list[dict[str, Any]]) -> tuple[int, int]:
    prompt = completion = 0
    for row in rows:
        if row.get('kind') == 'timing':
            continue
        prompt += int(row.get('prompt_tokens') or 0)
        completion += int(row.get('completion_tokens') or 0)
    return prompt, completion


def actual_case_cny(
    model: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    expect: str,
    *,
    passed: bool | None = None,
) -> float:
    if prompt_tokens or completion_tokens:
        return tokens_cny(model, prompt_tokens, completion_tokens)
    if passed is False:
        return 0.0
    return estimate_case_cny(model, expect)


def run_cap_cny(mode: str) -> float:
    return PER_RUN_CAP_CNY.get(mode, PER_RUN_CAP_CNY['nightly'])


def provider_cap_cny(mode: str) -> float:
    return PER_PROVIDER_CAP_CNY.get(mode, PER_PROVIDER_CAP_CNY['nightly'])
