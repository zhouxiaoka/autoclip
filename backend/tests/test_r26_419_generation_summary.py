"""R26 #367: the generation summary rules live only in backend attempts.generation_summary (frozen into the
receipt). These are the cases frontend/tests used to assert on the deleted workflow.generationSummary copy."""
from backend.services.studio.attempts import generation_summary

SNAPSHOT = {
    'generation': {'auto_start': True, 'status': 'partial', 'requested_platforms': ['douyin', 'tiktok'], 'skipped': [{'strategy_id': 'youtube_long', 'reason': 'x'}],
                   'source_has_burned_subtitles': False, 'created_at': '2026-09-30T10:00:00Z', 'finished_at': '2026-09-30T10:04:00Z'},
    'output_variants': [
        {'draft_id': 'a', 'strategy_id': 'douyin', 'status': 'completed', 'framing': 'speaker'},
        {'draft_id': 'b', 'strategy_id': 'tiktok', 'status': 'failed', 'framing': 'full_frame', 'trimmed_to_sec': 180},
        {'draft_id': 'c', 'strategy_id': 'douyin', 'status': 'on_demand'},
    ],
    'drafts': [{'id': 'a', 'title': 'Private title', 'packaging': {'template': 'interview_zh', 'fallback': False}},
               {'id': 'b', 'packaging': {'template': 'podcast_en', 'fallback': True}}],
}


def test_counts_templates_framing_and_fallbacks_without_content():
    assert generation_summary(SNAPSHOT) == {
        'variant_count': 3, 'completed_variant_count': 1, 'failed_variant_count': 1, 'on_demand_variant_count': 1, 'skipped_variant_count': 1,
        'platform_count': 2, 'interview_count': 1, 'podcast_count': 1, 'landscape_count': 0, 'editorial_count': 0, 'street_count': 0,
        'classic_count': 2, 'html_downgrade_count': 0, 'speaker_framed_count': 1, 'full_frame_count': 1, 'framing_pending_count': 0,
        'framing_captions_count': 0, 'outro_applied_count': 0, 'outro_fallback_count': 0, 'outro_unknown_count': 1,
        'packaging_fallback_count': 1, 'trimmed_count': 1, 'burned_captions': False, 'duration_ms': 240000}
    assert 'Private' not in str(generation_summary(SNAPSHOT))


def test_outro_metrics_separate_result_disabled_fallback_and_missing_evidence():
    state = {'generation': {'portrait_style': 'podcast', 'branding': {'outro_enabled': True}}, 'output_variants': [
        *({'id': i, 'draft_id': i, 'render_job_id': i, 'strategy_id': 'douyin', 'status': 'completed', 'branding': {'outro_enabled': True}} for i in ('applied', 'fallback', 'disabled', 'unknown')),
        {'id': 'failed', 'draft_id': 'failed', 'render_job_id': 'failed', 'strategy_id': 'douyin', 'status': 'failed'}],
        'jobs': [{'job_id': 'applied', 'status': 'completed', 'brand_outro': True, 'result': {'outro_applied': True}},
                 {'job_id': 'fallback', 'status': 'completed', 'brand_outro': True, 'result': {'outro_applied': False, 'warnings': ['private error']}},
                 {'job_id': 'disabled', 'status': 'completed', 'brand_outro': False, 'result': {'outro_applied': False}},
                 {'job_id': 'failed', 'status': 'failed', 'brand_outro': True, 'result': {'outro_applied': False}}]}
    s = generation_summary(state)
    assert (s['portrait_style'], s['outro_applied_count'], s['outro_fallback_count'], s['outro_unknown_count']) == ('podcast', 1, 1, 1)
    assert 'private' not in str(s)


def test_a_rank_skip_is_classic_and_not_a_downgrade():
    s = generation_summary({'output_variants': [
        {'draft_id': 'a', 'render_job_id': 'j1', 'strategy_id': 'douyin', 'status': 'completed'},
        {'draft_id': 'b', 'render_job_id': 'j2', 'strategy_id': 'douyin', 'status': 'completed'}], 'jobs': [
        {'job_id': 'j1', 'status': 'completed', 'result': {'template_render': {'template': 'classic', 'requested_template': 'editorial', 'downgraded': False, 'downgrade_reason': 'rank', 'outcome': 'skipped'}}},
        {'job_id': 'j2', 'status': 'completed', 'result': {'template_render': {'template': 'classic', 'requested_template': 'editorial', 'downgraded': True, 'downgrade_reason': 'over_budget', 'outcome': 'downgraded'}}}],
        'drafts': []})
    assert (s['html_downgrade_count'], s['classic_count'], s['editorial_count']) == (1, 2, 0)


def test_recommendation_fields_are_kept():
    s = generation_summary({'generation': {'recommended_template': 'editorial', 'accepted_recommendation': False}, 'output_variants': [], 'jobs': [], 'drafts': []})
    assert s['recommended_template'] == 'editorial' and s['accepted_recommendation'] is False
