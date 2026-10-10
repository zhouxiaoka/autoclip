"""Template events keep enums and counts, and drop anything that could identify a video."""
from backend.services.studio.template_telemetry import override_event, render_event


def test_render_event_keeps_enums_and_drops_paths_titles_and_free_text():
    props = render_event({
        'template': 'editorial',
        'encoder': 'h264_nvenc',
        'downgraded': True,
        'downgrade_reason': 'over_budget',
        'os': 'win32',
        'cpu_count': 8,
        'duration_ms': 4200,
        'failure_reason': 'none',
        'outcome': 'downgraded',
        'strategy_id': 'xiaohongshu',
        'flow_id': 't-abc123def456',
        'path': '/Users/private/clip.mp4',
        'title': '秘密标题',
        'caption': '原话不该出现',
        'reason': 'ffmpeg said /tmp/secret',
        'cpu_count_raw': 8.5,
    })
    assert props['template'] == 'editorial'
    assert props['encoder'] == 'h264_nvenc'
    assert props['downgraded'] is True
    assert props['downgrade_reason'] == 'over_budget'
    assert props['os'] == 'win32' and props['cpu_count'] == 8
    assert props['duration_ms'] == 4200 and props['outcome'] == 'downgraded'
    blob = str(props)
    assert 'private' not in blob and '秘密' not in blob and '原话' not in blob and '/tmp' not in blob
    assert 'path' not in props and 'title' not in props


def test_unknown_encoder_and_negative_duration_are_dropped():
    props = render_event({'template': 'street', 'encoder': 'hevc_nvenc', 'duration_ms': -1, 'cpu_count': 10_000})
    assert props == {'template': 'street'}


def test_override_event_is_enums_only():
    props = override_event({
        'from_template': 'editorial',
        'to_template': 'street',
        'stage': 'pre_import',
        'flow_id': 't-abc123def456',
        'title': 'do not send',
    })
    assert props == {
        'from_template': 'editorial',
        'to_template': 'street',
        'stage': 'pre_import',
        'flow_id': 't-abc123def456',
    }
