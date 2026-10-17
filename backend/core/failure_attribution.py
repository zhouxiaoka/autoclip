"""Which failure a multi-goal attempt is attributed to (R23 #228, PM rule).

One rule for the event and docs/analytics/success_rate.sql: the tiers come from the event catalog's
attribution.success_rate_v4 (the SQL must match it, test_llm_auth_invalid_e2e). A cause is user_hard
(out of both denominators), user_x (out of the product denominator only) or product. The attempt's
primary cause is the first failure of the most product-like tier; the event carries the rest as
secondary causes. So an attempt leaves a denominator only when every cause is a user cause for it."""
from backend.core import event_catalog

PRODUCT, USER_X, USER_HARD = 0, 1, 2


def _v4() -> dict:
    return (event_catalog.load_catalog().get('attribution') or {}).get('success_rate_v4') or {}


def cause_tier(failure: dict) -> int:
    v4 = _v4()
    code, upstream = failure.get('error_code'), failure.get('upstream_error_type')
    if code in v4.get('overall_excluded_error_codes', ()) or upstream in v4.get('overall_excluded_upstream_types', ()):
        return USER_HARD
    if code in v4.get('product_extra_excluded_error_codes', ()):
        return USER_X
    return PRODUCT


def rank_failures(failures: list) -> list:
    """Failures in the order they failed -> primary first (most product-like tier, then earliest)."""
    return sorted(failures, key=cause_tier)  # stable: within a tier the earliest failure stays first
