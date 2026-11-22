"""Regression tests for 2d37667d dual-platform remake blocker:
confirming a remake with goals=['content'] must create a new pending Studio draft
and settle generation.status out of 'awaiting_confirmation' while preserving V1 outputs.
"""
import pytest

from backend.services.studio import intelligence, jobs, store
from backend.services.studio.models import ConfirmPlan, Preferences
from backend.tests.test_studio import root, source  # noqa: F401


@pytest.fixture(autouse=True)
def allow_short_fixture(monkeypatch):
    from backend.pipeline import media_precheck
    monkeypatch.setattr(media_precheck, 'too_short', lambda duration: False)


class _Immediate:
    def submit(self, fn, *args, **kwargs):
        kwargs.pop('_io_receipt', None)
        fn(*args, **kwargs)


def _seed_completed_v1_awaiting_remake(project_id: str, plan_id: str = 'plan-remake-1'):
    (store.directory(project_id) / 'metadata').mkdir(parents=True, exist_ok=True)
    store.write(
        project_id,
        {
            'schema_version': 2,
            'drafts': [
                {
                    'id': 'draft-v1',
                    'revision': 1,
                    'title': '旧版成片标题',
                    'origin': 'auto-content',
                    'language': 'zh',
                    'aspect': 'portrait',
                    'layout': 'crop',
                    'subtitles': True,
                    'scenes': [{'id': 's-v1', 'label': '旧版成片标题', 'start': 0.0, 'end': 2.0}],
                }
            ],
            'events': [],
            'jobs': [
                {
                    'job_id': 'job-v1',
                    'draft_id': 'draft-v1',
                    'revision': 1,
                    'status': 'completed',
                    'created_at': '2026-11-22T08:00:00+00:00',
                }
            ],
            'output_variants': [
                {
                    'id': 'var-v1',
                    'strategy_id': 'douyin',
                    'draft_id': 'draft-v1',
                    'draft_revision': 1,
                    'render_job_id': 'job-v1',
                    'status': 'completed',
                    'post': {'title': '旧版完整标题', 'description': '', 'tags': []},
                    'branding': {'outro_enabled': True},
                }
            ],
            'plan': {
                'id': plan_id,
                'mode': 'ai',
                'goal': 'content',
                'suggested_goals': ['content'],
                'recommended_analysis': 'subtitle',
                'aspect': 'original',
                'preferences': Preferences(goal='content', language='zh', aspect='original', duration=20).model_dump(),
                'overrides': {'auto_start': False, 'goal': 'content', 'language': 'zh', 'aspect': 'original'},
            },
            'generation': {
                'auto_start': False,
                'status': 'awaiting_confirmation',
                'requested_platforms': ['douyin'],
                'created_at': '2026-11-22T10:59:58+00:00',
            },
            'analysis': {
                'status': 'awaiting_confirmation',
                'phase': 'screening',
                'run_id': 'run-screen-1',
            },
        },
    )


def test_confirm_remake_content_creates_new_draft_and_settles_generation_status(root, source, monkeypatch):  # noqa: F811
    pid = 'proj-remake-content'
    _seed_completed_v1_awaiting_remake(pid)

    monkeypatch.setattr(jobs, 'executor', _Immediate())
    monkeypatch.setattr(jobs, 'source', lambda _: source)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, '_check_production_route', lambda *a, **k: None)
    monkeypatch.setattr(
        jobs,
        'run_content',
        lambda *a, **k: [
            {
                'start_time': '00:00:00,000',
                'end_time': '00:00:02,000',
                'generated_title': '再做新方案片段',
                'recommend_reason': '完整观点表达',
                'final_score': 0.92,
            }
        ],
    )
    from backend.services.studio import readiness
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)

    jobs.confirm_project(
        pid,
        ConfirmPlan(
            plan_id='plan-remake-1',
            analysis_mode='subtitle',
            goals=['content'],
            language='zh',
            aspect='original',
            duration=20,
        ),
    )

    state = store.read(pid)
    # 1. Existing V1 outputs remain untouched
    assert state['output_variants'][0]['id'] == 'var-v1'
    assert state['jobs'][0]['job_id'] == 'job-v1'
    assert state['drafts'][0]['id'] == 'draft-v1'

    # 2. A brand-new confirmed Studio draft is created for the remake
    assert len(state['drafts']) == 2, f'expected new remake draft, got {state["drafts"]}'
    new_draft = state['drafts'][1]
    assert new_draft['id'] != 'draft-v1'
    assert new_draft['origin'] == 'subtitle-content'
    assert new_draft['title'] == '再做新方案片段'
    assert new_draft['language'] == 'zh'
    assert new_draft['aspect'] == 'original'
    assert new_draft['subtitles'] is True
    assert len(new_draft['scenes']) == 1
    assert new_draft['scenes'][0]['start'] == 0.0
    assert new_draft['scenes'][0]['end'] == 2.0
    assert '_auto_score' not in new_draft

    # 3. Both analysis and generation settle out of awaiting_confirmation
    assert state['analysis']['status'] == 'completed'
    assert state['analysis']['result_count'] == 1
    assert state['generation']['status'] == 'completed'
    assert state['generation'].get('finished_at')

    # 4. New draft is owned by the production attempt
    prod_attempts = [a for a in state.get('attempts') or [] if a.get('kind') == 'production']
    assert prod_attempts and new_draft['id'] in (prod_attempts[-1].get('draft_ids') or [])


def test_confirm_remake_content_portrait_uses_blur_instead_of_untracked_crop(root, source, monkeypatch):  # noqa: F811
    pid = 'proj-remake-portrait'
    _seed_completed_v1_awaiting_remake(pid, plan_id='plan-portrait')

    monkeypatch.setattr(jobs, 'executor', _Immediate())
    monkeypatch.setattr(jobs, 'source', lambda _: source)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, '_check_production_route', lambda *a, **k: None)
    monkeypatch.setattr(
        jobs,
        'run_content',
        lambda *a, **k: [
            {
                'start_time': '00:00:00,000',
                'end_time': '00:00:02,000',
                'generated_title': '竖屏再做片段',
            }
        ],
    )
    from backend.services.studio import readiness
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)

    jobs.confirm_project(
        pid,
        ConfirmPlan(
            plan_id='plan-portrait',
            analysis_mode='subtitle',
            goals=['content'],
            language='zh',
            aspect='portrait',
        ),
    )

    state = store.read(pid)
    assert len(state['drafts']) == 2
    assert state['drafts'][1]['aspect'] == 'portrait'
    assert state['drafts'][1]['layout'] == 'blur'
    assert state['generation']['status'] == 'completed'


def test_confirm_remake_content_failure_settles_generation_to_failed(root, source, monkeypatch):  # noqa: F811
    pid = 'proj-remake-fail'
    _seed_completed_v1_awaiting_remake(pid, plan_id='plan-fail')

    monkeypatch.setattr(jobs, 'executor', _Immediate())
    monkeypatch.setattr(jobs, 'source', lambda _: source)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, '_check_production_route', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'run_content', lambda *a, **k: (_ for _ in ()).throw(ValueError('upstream boom')))
    from backend.services.studio import readiness
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)

    jobs.confirm_project(
        pid,
        ConfirmPlan(plan_id='plan-fail', analysis_mode='subtitle', goals=['content']),
    )

    state = store.read(pid)
    assert len(state['drafts']) == 1  # V1 preserved
    assert state['analysis']['status'] == 'failed'
    assert state['generation']['status'] == 'failed'
