"""A long ASR cue and a completed export with no publisher or platform variant."""
from backend.services import cover
from backend.services.studio import jobs, store
from backend.tests.test_studio import client, draft, root, source  # noqa: F401


def test_preview_pages_an_old_paragraph_on_the_source_clock(client, root):
    words = ' '.join(['Here are the first words.', 'We clearly had some missteps as a company.'] * 5)
    (root / 'metadata').mkdir(exist_ok=True)
    (root / 'metadata/input.srt').write_text(f'1\n00:00:01,000 --> 00:00:20,000\n{words}\n')
    response = client.get('/studio/p1/subtitles?width=1080&height=1920&style=accent')
    pages = response.json()['cues']
    assert len(pages) > 1
    assert pages[0]['start'] == 1 and abs(pages[-1]['end'] - 20) < .001
    assert ' '.join(' '.join(p['text'].split()) for p in pages) == words
    assert all(len(p['text'].splitlines()) <= 2 for p in pages)
    assert sum(p['start'] <= 12 < p['end'] for p in pages) == 1


def test_old_packaged_draft_previews_saved_translation(client, root):
    from backend.services.studio.models import Packaging
    d = draft()
    d.packaging = Packaging(template='interview_zh', audience_language='zh', source_language='en',
                            cues=[{'start': 10, 'end': 15, 'text': '公司确实出现了一些失误。', 'original': 'We made mistakes.'}])
    store.save_draft('p1', d, create=True)
    pages = client.get('/studio/p1/subtitles?draft_id=d1').json()['cues']
    assert any('失误' in p['text'] and p['start'] <= 12 < p['end'] for p in pages)


def test_standalone_render_creates_one_cover_for_the_finished_video(root, source, monkeypatch):
    from PIL import Image
    from shutil import copyfile
    d = draft()
    jid = 'c' * 32
    movie = root / 'output/studio' / f'{jid}.mp4'
    movie.parent.mkdir(parents=True, exist_ok=True)
    copyfile(source, movie)
    store.write('p1', {'drafts': [], 'jobs': [{'job_id': jid, 'draft_id': d.id, 'revision': 1,
                'title': d.title, 'status': 'completed', 'result': {'width': 320, 'height': 180}}]})
    monkeypatch.setattr(cover, 'load_config', lambda: cover.CoverConfig(enabled=False))
    jobs._design_covers('p1', d, jid)
    path = cover.cover_path('p1', 'studio-' + jid, 'bilibili')
    assert path.is_file()
    with Image.open(path) as img:
        assert img.format == 'JPEG' and img.width > img.height
    monkeypatch.setattr(cover, 'generate_cover', lambda **_: (_ for _ in ()).throw(AssertionError('regenerated')))
    before = path.stat().st_mtime_ns
    jobs._design_covers('p1', d, jid)
    assert path.stat().st_mtime_ns == before


def test_local_only_selection_survives_saves_and_old_disabled_assignments(root):
    import json
    from backend.services import ai_model_settings as ai
    profile = ai.ModelSettings(
        connections=[ai.Connection(id='a', name='Local', provider='ollama')],
        analysis=ai.Assignment(connection_id='a', model='chat'), prefer_local_cover=True)
    ai.save(profile)
    assert ai.public(ai.load())['prefer_local_cover'] is True
    old = json.loads(ai.path().read_text())
    old.pop('prefer_local_cover')
    old['cover'] = {'connection_id': 'a', 'model': 'stored-image'}
    ai.path().write_text(json.dumps(old))
    assert ai.load().prefer_local_cover and not cover.load_config().enabled
