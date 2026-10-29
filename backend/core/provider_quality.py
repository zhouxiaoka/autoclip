"""Measured provider success and latency tiers.

The numbers live in ``backend/presets/provider_quality.json`` (next to the
catalog so ``presets/*.json`` ships them in the wheel). Runtime never calls
PostHog. Tiers are derived from the rates; providers missing from the file
have no tier.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

SCHEMA_VERSION = 1
SUCCESS_TIERS = ("high", "mid", "low")
LATENCY_TIERS = ("under_5m", "mid_5_20m", "over_20m")
_TIER_RANK = {"high": 0, "mid": 1, "low": 2}

# Printed by scripts/provider_quality_report.py. Not executed by the app.
REFRESH_HOGQL = """\
-- Device-level product success by provider, last 14 days.
-- One device (person_id) per provider. Success means that device's latest
-- product-qualified attempt in the window is outcome success.
-- Exclusions match docs/analytics/success_rate.sql v4 (user-caused + product extras).
-- Paste into PostHog project 450605. Do not run this from the desktop app.
SELECT
  provider,
  count() AS devices,
  countIf(latest_outcome = 'success') / count() AS success_rate
FROM (
  SELECT
    person_id,
    provider,
    argMax(outcome, ts) AS latest_outcome
  FROM (
    SELECT
      person_id,
      toString(properties.provider) AS provider,
      timestamp AS ts,
      multiIf(
        toString(properties.outcome) IN ('completed', 'success'), 'success',
        toString(properties.outcome) = 'partial', 'partial',
        toString(properties.outcome) IN ('cancelled', 'canceled'), 'cancelled',
        'error'
      ) AS outcome,
      coalesce(toString(properties.error_code), '') AS error_code,
      coalesce(toString(properties.upstream_error_type), '') AS upstream_error_type
    FROM events
    WHERE event IN ('studio_generation_finished', 'studio_production_finished')
      AND timestamp >= now() - INTERVAL 14 DAY
      AND toString(properties.analytics_environment) = 'production'
      AND toString(properties.runtime) = 'desktop'
      AND toString(properties.provider) != ''
  )
  WHERE NOT (
    outcome = 'cancelled'
    OR error_code IN (
      'authentication', 'llm_auth_invalid', 'invalid_key', 'insufficient_quota',
      'llm_not_configured', 'cancelled', 'user_cancelled', 'connection',
      'source_too_short', 'source_no_audio', 'source_unreadable',
      'source_blocked', 'source_not_found'
    )
    OR upstream_error_type IN ('invalid_key', 'insufficient_quota', 'permission_denied')
  )
  GROUP BY person_id, provider
)
GROUP BY provider
ORDER BY success_rate DESC

-- p50 duration of successful attempts, in minutes (success p50).
SELECT
  toString(properties.provider) AS provider,
  quantile(0.5)(toFloat(properties.duration_ms)) / 60000 AS success_p50_minutes
FROM events
WHERE event IN ('studio_generation_finished', 'studio_production_finished')
  AND timestamp >= now() - INTERVAL 14 DAY
  AND toString(properties.analytics_environment) = 'production'
  AND toString(properties.runtime) = 'desktop'
  AND toString(properties.outcome) IN ('completed', 'success')
  AND toString(properties.provider) != ''
GROUP BY provider
ORDER BY provider
"""


@dataclass(frozen=True)
class Thresholds:
    success_high_min: float = 0.8
    success_mid_min: float = 0.6
    latency_under_5m_exclusive_max_minutes: float = 5.0
    latency_mid_inclusive_max_minutes: float = 20.0


@dataclass(frozen=True)
class ProviderQuality:
    provider_id: str
    success_rate: float
    success_p50_minutes: float
    success_tier: str
    latency_tier: str
    caveat_key: Optional[str] = None

    def as_public(self) -> Dict[str, Optional[str]]:
        return {
            "success_tier": self.success_tier,
            "latency_tier": self.latency_tier,
            "caveat_key": self.caveat_key,
        }


@dataclass(frozen=True)
class QualityTable:
    schema_version: int
    thresholds: Thresholds
    providers: Dict[str, ProviderQuality]
    path: Optional[Path]


_cache: Optional[QualityTable] = None


def _number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number:  # NaN
        return None
    return number


def success_tier(rate: float, thresholds: Thresholds = Thresholds()) -> Optional[str]:
    """high ≥ 80%, mid 60–80%, low < 60%. Values outside 0–1 are not a tier."""
    number = _number(rate)
    if number is None or number < 0 or number > 1:
        return None
    if number >= thresholds.success_high_min:
        return "high"
    if number >= thresholds.success_mid_min:
        return "mid"
    return "low"


def latency_tier(minutes: float, thresholds: Thresholds = Thresholds()) -> Optional[str]:
    """under_5m < 5, mid_5_20m is 5–20 inclusive, over_20m > 20."""
    number = _number(minutes)
    if number is None or number < 0:
        return None
    if number < thresholds.latency_under_5m_exclusive_max_minutes:
        return "under_5m"
    if number <= thresholds.latency_mid_inclusive_max_minutes:
        return "mid_5_20m"
    return "over_20m"


def reset_quality_cache() -> None:
    global _cache
    _cache = None


def quality_path() -> Optional[Path]:
    """Sibling of the active provider catalog. Missing file means no tiers."""
    try:
        from backend.core.provider_presets import find_provider_presets_path
        return find_provider_presets_path().parent / "provider_quality.json"
    except (FileNotFoundError, OSError, ValueError):
        return None


def load_quality(path: Path) -> QualityTable:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("provider quality must be a JSON object")
    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported provider quality schema_version: {schema_version!r}")
    raw_thresholds = data.get("thresholds") if isinstance(data.get("thresholds"), Mapping) else {}
    thresholds = Thresholds(
        success_high_min=float(raw_thresholds.get("success_high_min", 0.8)),
        success_mid_min=float(raw_thresholds.get("success_mid_min", 0.6)),
        latency_under_5m_exclusive_max_minutes=float(raw_thresholds.get("latency_under_5m_exclusive_max_minutes", 5)),
        latency_mid_inclusive_max_minutes=float(raw_thresholds.get("latency_mid_inclusive_max_minutes", 20)),
    )
    if not 0 < thresholds.success_mid_min <= thresholds.success_high_min <= 1:
        raise ValueError("provider quality success thresholds are out of order")
    if not 0 < thresholds.latency_under_5m_exclusive_max_minutes <= thresholds.latency_mid_inclusive_max_minutes:
        raise ValueError("provider quality latency thresholds are out of order")
    raw_providers = data.get("providers")
    if not isinstance(raw_providers, Mapping):
        raise ValueError("provider quality missing providers object")
    providers: Dict[str, ProviderQuality] = {}
    for key, raw in raw_providers.items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            continue
        rate = _number(raw.get("success_rate"))
        minutes = _number(raw.get("success_p50_minutes"))
        tier = success_tier(rate, thresholds) if rate is not None else None
        latency = latency_tier(minutes, thresholds) if minutes is not None else None
        if tier is None or latency is None or rate is None or minutes is None:
            continue
        caveat = raw.get("caveat_key")
        caveat_key = caveat.strip() if isinstance(caveat, str) and caveat.strip() else None
        providers[key.strip()] = ProviderQuality(
            provider_id=key.strip(),
            success_rate=rate,
            success_p50_minutes=minutes,
            success_tier=tier,
            latency_tier=latency,
            caveat_key=caveat_key,
        )
    return QualityTable(schema_version=SCHEMA_VERSION, thresholds=thresholds, providers=providers, path=path)


def get_quality() -> QualityTable:
    global _cache
    if _cache is None:
        path = quality_path()
        if path is None or not path.is_file():
            _cache = QualityTable(schema_version=SCHEMA_VERSION, thresholds=Thresholds(), providers={}, path=path)
        else:
            _cache = load_quality(path)
    return _cache


def quality_for(provider_id: Optional[str]) -> Optional[ProviderQuality]:
    if not provider_id:
        return None
    return get_quality().providers.get(provider_id.strip())


def public_fields(provider_id: Optional[str]) -> Dict[str, Optional[str]]:
    row = quality_for(provider_id)
    if row is None:
        return {"success_tier": None, "latency_tier": None, "caveat_key": None}
    return row.as_public()


def display_catalog_group(group: str, *, sponsor: bool, success_tier_value: Optional[str]) -> str:
    """Where a catalog card is shown.

    Stored ``group`` stays in the catalog JSON. A low tier never enters
    recommended (it falls into 热门 / popular, unless it is local or more).
    Sponsors that are not low stay in recommended. Popular high/mid rows are
    promoted after the sponsors. Local mid rows stay local.
    """
    if success_tier_value == "low":
        if group == "local":
            return "local"
        if group == "more":
            return "more"
        return "popular"
    if sponsor or group == "recommended":
        return "recommended"
    if success_tier_value in ("high", "mid") and group == "popular":
        return "recommended"
    return group


def recommended_provider_ids() -> list[str]:
    """Sponsors pinned in catalog order, then non-sponsors by success tier and rate."""
    from backend.core.provider_presets import get_catalog

    ranked: list[tuple[tuple, str]] = []
    for index, preset in enumerate(get_catalog().providers.values()):
        row = quality_for(preset.id)
        tier = row.success_tier if row else None
        shown = display_catalog_group(preset.group, sponsor=bool(preset.sponsor), success_tier_value=tier)
        if shown != "recommended":
            continue
        if preset.sponsor:
            key = (0, index, 0, 0.0)
        else:
            rank = _TIER_RANK.get(tier or "", 9)
            rate = -(row.success_rate if row else 0.0)
            key = (1, rank, rate, index)
        ranked.append((key, preset.id))
    ranked.sort(key=lambda item: item[0])
    return [provider_id for _, provider_id in ranked]


def public_payload() -> dict:
    table = get_quality()
    return {
        "providers": {provider_id: row.as_public() for provider_id, row in table.providers.items()},
        "recommended": recommended_provider_ids(),
    }
