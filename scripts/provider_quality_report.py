#!/usr/bin/env python3
"""Refresh notes for backend/presets/provider_quality.json.

The desktop app does not call PostHog. This script documents the last-14-day
device-level success rate and the p50 duration of successful runs, and prints
the HogQL to paste into PostHog project 450605.

Without POSTHOG_PERSONAL_API_KEY (or POSTHOG_API_KEY) it prints that HogQL and
exits 0. It never invents rates. ``--write`` updates the JSON only after a
live query returns rows; caveat_key values already in the file are kept.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.provider_quality import REFRESH_HOGQL, quality_path


def _credentials() -> tuple[str, str, str]:
    key = (os.environ.get("POSTHOG_PERSONAL_API_KEY") or os.environ.get("POSTHOG_API_KEY") or "").strip()
    project = (os.environ.get("POSTHOG_PROJECT_ID") or "450605").strip()
    host = (os.environ.get("POSTHOG_HOST") or "https://us.posthog.com").rstrip("/")
    return key, project, host


def _query(hogql: str, key: str, project: str, host: str) -> object:
    url = f"{host}/api/projects/{project}/query/"
    body = json.dumps({"query": {"kind": "HogQLQuery", "query": hogql}}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _rows(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    columns = payload.get("columns")
    results = payload.get("results")
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return [row for row in results if isinstance(row, dict)]
    if isinstance(columns, list) and isinstance(results, list):
        names = [str(column) for column in columns]
        parsed = []
        for row in results:
            if isinstance(row, list) and len(row) == len(names):
                parsed.append(dict(zip(names, row)))
        return parsed
    return []


def _apply(path: Path, rate_rows: list[dict], latency_rows: list[dict]) -> int:
    rates = {str(row.get("provider")): row.get("success_rate") for row in rate_rows if row.get("provider")}
    minutes = {
        str(row.get("provider")): row.get("success_p50_minutes")
        for row in latency_rows if row.get("provider")
    }
    if not rates and not minutes:
        print("PostHog returned no provider rows; left the JSON unchanged.", file=sys.stderr)
        return 1
    document = json.loads(path.read_text(encoding="utf-8"))
    providers = document.setdefault("providers", {})
    updated = 0
    for provider_id, raw in list(providers.items()):
        if not isinstance(raw, dict):
            continue
        if provider_id in rates and isinstance(rates[provider_id], (int, float)):
            raw["success_rate"] = round(float(rates[provider_id]), 4)
            updated += 1
        if provider_id in minutes and isinstance(minutes[provider_id], (int, float)):
            raw["success_p50_minutes"] = round(float(minutes[provider_id]), 2)
            updated += 1
    if not updated:
        print("No overlap between the query and the seeded providers; left the JSON unchanged.", file=sys.stderr)
        return 1
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {updated} fields in {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or refresh provider quality tiers from PostHog.")
    parser.add_argument("--write", action="store_true", help="Replace measured rates in the JSON after a live query.")
    args = parser.parse_args(argv)
    path = quality_path()
    print(f"Quality file: {path}")
    print("Thresholds: high ≥ 80%, mid 60–80%, low < 60%. Latency: < 5 min / 5–20 min / > 20 min.")
    print("Grain: one device (person_id) per provider over the last 14 days. The app does not run this query.")
    key, project, host = _credentials()
    if not key:
        print("\nNo POSTHOG_PERSONAL_API_KEY / POSTHOG_API_KEY. Expected HogQL:\n")
        print(REFRESH_HOGQL)
        print("Re-run with the key set to query project", project, "on", host + ".")
        print("Review the numbers before writing them into the JSON. Do not invent a rate for a provider the query omits.")
        return 0
    chunks = REFRESH_HOGQL.split("\n\n-- ")
    hogql_statements = []
    for index, chunk in enumerate(chunks):
        text = chunk if index == 0 else "-- " + chunk
        select_at = text.upper().find("SELECT")
        if select_at >= 0:
            hogql_statements.append(text[select_at:].strip())
    if len(hogql_statements) != 2:
        print("Expected two HogQL statements.", file=sys.stderr)
        return 1
    try:
        rate_payload = _query(hogql_statements[0], key, project, host)
        latency_payload = _query(hogql_statements[1], key, project, host)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"PostHog query failed: {exc}", file=sys.stderr)
        print(REFRESH_HOGQL)
        return 1
    rate_rows = _rows(rate_payload)
    latency_rows = _rows(latency_payload)
    print(json.dumps({"success_rate": rate_rows, "success_p50_minutes": latency_rows}, ensure_ascii=False, indent=2))
    if not args.write:
        print("\nDry run. Pass --write to merge these rates into the existing provider rows.")
        return 0
    if path is None or not path.is_file():
        print("Quality JSON is missing; refusing to create rates from scratch.", file=sys.stderr)
        return 1
    return _apply(path, rate_rows, latency_rows)


if __name__ == "__main__":
    raise SystemExit(main())
