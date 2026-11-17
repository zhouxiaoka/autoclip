"""A completed translation can be corrected without replacing other edits or outputs."""
import json
import threading

import pytest

from backend.services.studio import caption_translation as ct
from backend.services.studio import packaging, store
from backend.services.studio.models import Packaging
from backend.tests.test_translation_recovery_api import recovery  # noqa: F401 - isolated API/project fixture

LINES = [{'start': 0, 'end': 2, 'text': 'We need 3 months.'},
         {'start': 2, 'end': 4, 'text': 'It takes 17 seconds.'}]


def test_force_retranslation_invalidates_only_selected_cached_unit(tmp_path):
    kwargs = dict(cache_dir=tmp_path, model_key='model')
    def old(_, data):
        i = data['lines'][0]['id']
        return {'lines': [{'id': i, 'text': ['我们只剩3个月。', '这需要17秒。'][i]}]}
    ct.translate(LINES, 'zh', call=old, **kwargs)
    seen = []
    def fixed(_, data):
        seen.append(data['lines'][0]['id'])
        return {'lines': [{'id': 0, 'text': '我们需要3个月。'}]}
    result = ct.translate(LINES, 'zh', call=fixed, only_ids={0}, force_ids={0}, **kwargs)
    assert result == {0: '我们需要3个月。', 1: '这需要17秒。'} and seen == [0]
    assert ct.translate(LINES, 'zh', allow_model=False, **kwargs) == result


def test_failed_forced_request_does_not_reuse_known_bad_translation(tmp_path):
    kwargs = dict(cache_dir=tmp_path, model_key='model')
    ct.translate(LINES, 'zh', call=lambda _, d: {'lines': [{'id': d['lines'][0]['id'], 'text': '3个月和17秒。'}]}, **kwargs)
    def unavailable(*_): raise OSError('offline')
    result = ct.translate(LINES, 'zh', call=unavailable, only_ids={0}, force_ids={0}, **kwargs)
    assert 0 not in result and 1 in result
    assert 0 not in ct.translate(LINES, 'zh', allow_model=False, **kwargs)


def test_late_cache_writer_cannot_resurrect_invalidated_translation(tmp_path):
    entered, release = threading.Event(), threading.Event()
    kwargs = dict(cache_dir=tmp_path, model_key='model')
    def delayed(_, data):
        entered.set(); assert release.wait(5)
        return {'lines': [{'id': 0, 'text': '我们只剩3个月。'}]}
    thread = threading.Thread(target=lambda: ct.translate(LINES, 'zh', call=delayed, only_ids={0}, **kwargs))
    thread.start(); assert entered.wait(5)
    try:
        ct.translate(LINES, 'zh', call=lambda *_: {'lines': [{'id': 0, 'text': '我们需要3个月。'}]}, only_ids={0}, force_ids={0}, **kwargs)
    finally:
        release.set(); thread.join(5)
    assert ct.translate(LINES, 'zh', allow_model=False, **kwargs)[0] == '我们需要3个月。'


def test_completed_caption_can_be_retranslated_without_touching_other_manual_edits(recovery, monkeypatch):
    monkeypatch.setattr(ct, '_request', lambda _, d: {'lines': [{'id': d['lines'][0]['id'], 'text': f"第{d['lines'][0]['id']}个想法。"}]})
    first = recovery.client.post('/translation/retry-translation', json=recovery.draft.model_dump()).json()
    first['cues'][1].update(text='第二句的人工修正。', manually_edited=True)
    draft = recovery.draft.model_copy(update={'packaging': Packaging.model_validate(first)})
    calls = []
    def regenerate(_, data):
        calls.append(data['lines'][0]['id'])
        return {'lines': [{'id': 0, 'text': '这是重新翻译的第0个想法。'}]}
    monkeypatch.setattr(ct, '_request', regenerate)
    reply = recovery.client.post('/translation/retranslate-caption', json={'draft': draft.model_dump(), 'cue_index': 0})
    assert reply.status_code == 200, reply.text
    after = reply.json()
    assert calls == [0]
    assert after['cues'][0]['text'] == '这是重新翻译的第0个想法。'
    assert after['cues'][1] == first['cues'][1]
    assert after['title_lines'] == first['title_lines']
    assert recovery.output.read_bytes() == b'previous immutable output'
    assert store.read('translation')['drafts'][0]['packaging']['translation_status'] == 'source_fallback'
    # Saving/reloading and global missing-caption recovery must retain the manual sentence.
    draft = draft.model_copy(update={'packaging': Packaging.model_validate(after)})
    saved = store.save_draft('translation', draft)
    replay = recovery.client.post('/translation/retry-translation', json=saved)
    assert replay.status_code == 200
    assert replay.json()['cues'][1]['text'] == '第二句的人工修正。'
    assert replay.json()['cues'][1]['manually_edited'] is True


@pytest.mark.parametrize('change,expected', [('stale',409), ('unknown',422)])
def test_retranslation_rejects_stale_or_unmapped_caption_before_cache_mutation(recovery, monkeypatch, change, expected):
    value = recovery.draft.model_dump()
    value['packaging']['cues'] = [{'start':0, 'end':.4, 'text':'译文', 'original':'invented source'}]
    if change == 'stale': value['revision'] += 1
    monkeypatch.setattr(ct, 'translate', lambda *_args, **_kwargs: pytest.fail('must not translate or invalidate cache'))
    reply = recovery.client.post('/translation/retranslate-caption', json={'draft':value, 'cue_index':0})
    assert reply.status_code == expected, reply.text


def test_regeneration_retains_manual_caption_and_metadata_without_requesting_it(recovery, monkeypatch):
    from backend.services.platform_strategy import platform_strategy
    from backend.services.publish_export import _load_srt_entries
    from backend.services.studio.caption_units import translation_units
    entries = _load_srt_entries('translation')
    lines = packaging.draft_lines(entries,[s.model_dump() for s in recovery.draft.scenes])
    units = translation_units(lines)
    value = recovery.draft.model_dump()
    value['packaging']['cues'] = [{'start':0,'end':1,'text':'人工核对的第0句。',
        'source_id':packaging.source_unit_id(units[0]),'source_text':units[0]['text'],
        'manually_edited':True,'speaker':'Speaker','emphasis':'核对'}]
    seen=[]
    def translate(_,data):
        if data.get('task') != 'translate_captions': raise OSError('decoration unavailable')
        i=data['lines'][0]['id'];seen.append(i)
        return {'lines':[{'id':i,'text':f'这是第{i}句。'}]}
    result=packaging.build_packaging(value,lines,platform_strategy('douyin'),call=translate)
    assert 0 not in seen and len(seen)==9
    assert result['cues'][0]['text']=='人工核对的第0句。'
    assert result['cues'][0]['manually_edited'] and result['cues'][0]['speaker']=='Speaker'
    assert result['translation_status']=='complete'


def test_cache_invalidation_write_failure_prevents_model_call(tmp_path,monkeypatch):
    monkeypatch.setattr(ct,'_write_cache',lambda *_:(_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):
        ct.translate(LINES,'zh',cache_dir=tmp_path,model_key='model',only_ids={0},force_ids={0},
                     call=lambda *_:pytest.fail('must persist invalidation first'))


def test_malformed_cache_epoch_is_recovered_without_losing_sibling(tmp_path):
    path=tmp_path/(ct._cache_key(LINES,'zh',(),'model')+'.json')
    path.write_text(json.dumps({'0':'我们需要3个月。','1':'这需要17秒。','_epochs':42}))
    result=ct.translate(LINES,'zh',cache_dir=tmp_path,model_key='model',only_ids={0},force_ids={0},
                        call=lambda *_:{'lines':[{'id':0,'text':'我们需要3个月时间。'}]})
    assert result=={0:'我们需要3个月时间。',1:'这需要17秒。'}


def test_missing_translation_remains_editable_without_rendering_source_placeholder(recovery,monkeypatch):
    from backend.services.publish_export import _load_srt_entries
    from backend.services.studio.caption_units import translation_units
    lines=translation_units(packaging.draft_lines(_load_srt_entries('translation'),[s.model_dump() for s in recovery.draft.scenes]))
    facts,cues=packaging._translation_content(lines,{},'zh',True)
    assert not cues and len(facts['untranslated_cues'])==10
    value=recovery.draft.model_dump()
    value['packaging'].update(**facts,cues=cues,burned_captions=True)
    # Editor sends one placeholder only for this suggestion; it is never saved/rendered first.
    value['packaging']['cues']=[facts['untranslated_cues'][0]]
    monkeypatch.setattr(ct,'_request',lambda _,d:{'lines':[{'id':0,'text':'这是第0个想法。'}]})
    reply=recovery.client.post('/translation/retranslate-caption',json={'draft':value,'cue_index':0})
    assert reply.status_code==200,reply.text
    result=reply.json()
    assert result['cues'][0]['text']=='这是第0个想法。'
    assert len(result['untranslated_cues'])==9 and result['translated_rows']==1
    assert result['translation_status']=='partial'
    assert not store.read('translation')['drafts'][0]['packaging']['cues']
