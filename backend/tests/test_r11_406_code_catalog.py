"""R11 #406 follow-up: new codes are classified consistently in the catalog, success-rate SQL
and analytics docs. frame_extract_failed is a counted (product) failure; the subtitle-route /
fallback codes are degrade reasons on successful runs, never failures."""
import re
from pathlib import Path

from backend.core import event_catalog, sentry_setup
from backend.services.studio import planning

ROOT = Path(__file__).resolve().parents[2]
DEGRADES = {
    planning.VISION_FALLBACK_CODE, planning.VISION_INVALID_FALLBACK_CODE,
    planning.FRAME_EXTRACT_FALLBACK_CODE, planning.SOURCE_TOO_LONG_CODE,
}


def _excluded_codes(sql):
    return [set(re.findall(r"'(\w+)'", block)) for block in
            re.findall(r"coalesce\(properties\.error_code, ''\) NOT IN\s*\(([^)]*)\)", sql)]


def test_catalog_classifies_new_codes():
    for path in ('docs/analytics/event_catalog.json', 'backend/core/event_catalog.json'):
        import json
        catalog = json.loads((ROOT / path).read_text(encoding='utf-8'))
        attr = catalog['attribution']
        assert 'frame_extract_failed' in attr['product_error_codes'], path
        assert 'frame_extract_failed' not in attr['user_caused_error_codes'] + attr['environment_error_codes']
        assert set(catalog['enums']['degrade_reason']) == DEGRADES, path
        assert not DEGRADES & set(attr['user_caused_error_codes'] + attr['environment_error_codes'] + attr['product_error_codes'])
    assert set(event_catalog.load_catalog()['attribution']['product_error_codes']) <= sentry_setup.STUDIO_ERROR_CODES


def test_success_rate_sql_counts_frame_extract_failed_and_reports_degrades():
    sql = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
    blocks = _excluded_codes(sql)
    assert len(blocks) >= 2
    for codes in blocks:
        assert 'frame_extract_failed' not in codes  # a failure that counts against success
        assert not DEGRADES & codes  # degrades are not failure codes
    assert 'frame_extract_failed' in sql  # documented explicitly as counted
    degrade_query = sql[sql.index('degrade_reason'):]
    for code in DEGRADES:
        assert f"'{code}'" in degrade_query, code


def test_docs_list_new_codes():
    for doc in ('TRACKING_PLAN.md', 'STUDIO_MONITORING.md', 'LLM_TELEMETRY.md'):
        text = (ROOT / 'docs/analytics' / doc).read_text(encoding='utf-8')
        for code in ('frame_extract_failed', planning.FRAME_EXTRACT_FALLBACK_CODE, planning.SOURCE_TOO_LONG_CODE):
            assert code in text, (doc, code)
