"""English platforms are English only: no Chinese or Japanese text in titles, captions, nameplates,
post copy, kit files or the share credit, whatever the model returns (no model calls)."""
import io
import json
import zipfile

from backend.services.platform_strategy import platform_strategy
from backend.services.studio import jobs, packaging, post_copy, publish_kit, render, store

ZH_LINES = [
    {'start': 0.0, 'end': 3.0, 'text': '我觉得好的投资人就像飞行教练'},
    {'start': 3.0, 'end': 6.0, 'text': '他会让你自己去飞，但不会让你坠机'},
]
ZH_DRAFT = {'title': '好的投资人像飞行教练', 'hook': ''}


def _response(**overrides):
    body = {'title_lines': ['Good investors', 'are flight instructors'], 'accent_line': 1,
            'segments': [{'from': 0, 'to': 1, 'text': 'Good investors are like flight instructors: they let you fly, never crash.'}],
            'speakers': [{'line': 0, 'name': 'Sam Altman', 'role': 'OpenAI CEO'}], 'tags': [], 'highlights': []}
    return {**body, **overrides}


def _has_foreign(value):
    return packaging.foreign_for('en', json.dumps(value, ensure_ascii=False))


def test_chinese_model_output_never_reaches_an_english_package():
    calls = []

    def chinese_titles_then_good(_prompt, payload):
        calls.append(payload)
        if len(calls) == 1:  # captions still in Chinese: rejected and retried
            return _response(segments=[{'from': 0, 'to': 1, 'text': '好的投资人像飞行教练'}])
        return _response(title_lines=['好的投资人', '像飞行教练'], speakers=[{'line': 0, 'name': 'Sam Altman', 'role': 'OpenAI 首席执行官'}])
    result = packaging.build_packaging(ZH_DRAFT, ZH_LINES, platform_strategy('tiktok'), known_names='Sam Altman', call=chinese_titles_then_good)
    assert len(calls) == 2 and 'previous_error' in calls[1]
    assert not _has_foreign({k: result[k] for k in ('title_lines', 'cues', 'speakers')}), result
    assert result['speakers'] == [{'at': 0.0, 'name': 'Sam Altman', 'role': ''}]


def test_malformed_lists_do_not_break_packaging():
    result = packaging.build_packaging({'title': 'x', 'hook': ''}, [{'start': 0, 'end': 2, 'text': 'flight instructors teach you to fly'} for _ in range(3)],
                                       platform_strategy('tiktok'), call=lambda *_: _response(title_lines='Fly alone', speakers=['Sam'], highlights={'a': 1}))
    assert result['title_lines'] == ['Fly alone'] and result['speakers'] == []


def test_post_copy_retries_a_chinese_title_for_an_english_platform_and_never_posts_one():
    answers = iter([
        {'posts': {'tiktok': {'title': '好的投资人', 'description': 'x', 'tags': []}, 'douyin': {'title': '好的投资人', 'description': '简介', 'tags': ['投资']}}},
        {'posts': {'tiktok': {'title': 'Good investors teach you to fly', 'description': '中文简介', 'tags': ['investing', '投资']},
                   'douyin': {'title': '好的投资人', 'description': '简介', 'tags': ['投资']}}},
    ])
    posts = post_copy.build_posts('好的投资人', ['line'], ['tiktok', 'douyin'], call=lambda *_: next(answers))
    assert posts['tiktok'] == {'title': 'Good investors teach you to fly', 'description': '', 'tags': ['investing']}
    assert posts['douyin']['title'] == '好的投资人'
    stubborn = post_copy.build_posts('好的投资人', ['line'], ['tiktok'], call=lambda *_: {'posts': {'tiktok': {'title': '中文', 'description': '', 'tags': []}}})
    assert stubborn['tiktok']['title'] == ''


def test_an_english_version_without_an_english_title_uses_an_english_caption():
    value = {'title': '中文标题', 'packaging': {'title_lines': [], 'cues': [{'text': '我', 'start': 0, 'end': 1}, {'text': 'Fly alone first', 'start': 1, 'end': 2}]}}
    assert jobs._audience_title(value, 'tiktok', {'title': '中文'})['title'] == 'Fly alone first'
    assert jobs._audience_title({'title': '中文标题', 'packaging': None}, 'youtube_long', None)['title'] == 'Untitled clip'


def test_landscape_versions_caption_in_their_audiences_language():
    draft = {'id': 'd', 'title': 't', 'scenes': [{'id': 's', 'label': 'x', 'start': 0.0, 'end': 90.0}], 'language': 'source'}
    assert jobs._apply_strategy(draft, 'youtube_long').language == 'en'
    assert jobs._apply_strategy(draft, 'bilibili').language == 'zh'
    assert jobs._apply_strategy(draft, 'original').language == 'source'
    english = [{'text': 'a good investor is like a flight instructor who lets you fly'}]
    assert not render._needs_translation('en', 'Fly alone', english)
    assert render._needs_translation('en', '好的投资人', english), 'a Chinese hook on English YouTube is translated'
    assert render._needs_translation('zh', '', english)
    assert not render._needs_translation('zh', '好的投资人', [{'text': '我觉得好的投资人就像飞行教练，他会让你自己去飞'}])


def test_an_english_kit_is_english_down_to_the_file_names(tmp_path):
    video, cover = tmp_path / 'v.mp4', tmp_path / 'c.jpg'
    video.write_bytes(b'v')
    cover.write_bytes(b'c')
    data, name = publish_kit.kit_zip(video, cover, {'title': 'Fly alone', 'description': '', 'tags': []}, 'TikTok', english=True)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert not any(packaging.foreign_for('en', n) for n in names + [name]), names
    text = zipfile.ZipFile(io.BytesIO(data)).read('Fly alone post.txt').decode()
    assert not packaging.foreign_for('en', text)


def test_a_version_interrupted_mid_render_becomes_retryable_after_a_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'get_projects_directory', lambda: tmp_path)
    meta = tmp_path / 'p1' / 'metadata'
    meta.mkdir(parents=True)
    (meta / 'studio.json').write_text(json.dumps({
        'generation': {'status': 'rendering'}, 'analysis': {'status': 'running', 'instance': 'old'},
        'jobs': [{'job_id': 'j1', 'status': 'running', 'instance': 'old'}],
        'output_variants': [{'id': 'v1', 'status': 'queued', 'render_job_id': 'j1'}, {'id': 'v2', 'status': 'on_demand'}]}))
    data = store.read('p1')
    assert data['output_variants'][0]['status'] == 'failed'
    assert data['generation']['status'] == 'failed', 'the results page does not say it is still rendering'
