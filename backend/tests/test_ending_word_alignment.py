"""Acoustic word evidence may adjust timing, never choose a different conclusion."""
import math
import pytest

from backend.services.studio import boundaries


def test_same_selected_sentence_aligns_after_its_last_word_not_early_asr_row():
    from backend.services.studio.ending_alignment import align_ending
    rows = [(0, 2, 'We need a longer timeframe.'), (2, 5, 'What comes next?')]
    bound = boundaries.ClipBounds(0, 2, end_anchor=(0, len(rows[0][2])))
    words = [{'text': text, 'start': start, 'end': end} for text, start, end in
             [('We',0,.2),('need',.2,.5),('a',.5,.7),('longer',.7,1.4),('timeframe.',1.4,2.32),('What',2.65,2.9)]]
    result = align_ending(rows, bound, words, lambda *_: [(2.4, 2.65)])
    assert 2.4 <= result[1] < 2.65 and result.word_aligned
    assert not result.needs_review and result.end_anchor == bound.end_anchor


@pytest.mark.parametrize('problem', ['partial', 'wrong', 'ambiguous', 'nan', 'next_word', 'far'])
def test_uncertain_or_unsafe_word_evidence_keeps_cut_and_review_flag(problem):
    from backend.services.studio.ending_alignment import align_ending
    rows = [(0, 2, 'We have enough time.'), (2.4, 5, 'Next topic.')]
    bound = boundaries.ClipBounds(0, 2, end_anchor=(0, len(rows[0][2])))
    words = [{'text': text, 'start': start, 'end': start + .3} for text, start in
             [('We',0), ('have',.4), ('enough',.8), ('time',1.7)]]
    if problem == 'partial': words.pop(-1)
    if problem == 'wrong': words[-1]['text'] = 'money'
    if problem == 'ambiguous': words += [{**w, 'start':w['start']+2.1, 'end':w['end']+2.1} for w in words]
    if problem == 'nan': words[-1]['end'] = math.nan
    if problem == 'next_word': words.append({'text':'Next','start':1.95,'end':2.3})
    if problem == 'far': words = [{**w, 'start':w['start']+8, 'end':w['end']+8} for w in words]
    result = align_ending(rows, bound, words, lambda *_: [])
    assert result == bound and result.needs_review and not result.word_aligned


def test_verified_audio_does_not_clear_semantic_review_or_cross_neighbor():
    from backend.services.studio.ending_alignment import align_ending
    rows = [(0, 2, 'We have enough time.')]
    bound = boundaries.ClipBounds(0, 2, needs_review=True, end_anchor=(0,len(rows[0][2])))
    words = [{'text':t,'start':i*.5,'end':i*.5+.45} for i,t in enumerate(['We','have','enough','time'])]
    result = align_ending(rows,bound,words,lambda *_:[(2,2.4)])
    assert result.word_aligned and result.needs_review
    refused = align_ending(rows,bound,words,lambda *_:[(2,2.4)],limit=1.9)
    assert refused == bound and refused.needs_review


def test_runtime_absent_does_not_start_download_or_network(tmp_path, monkeypatch):
    from backend.services.studio import ending_alignment as alignment
    monkeypatch.setattr('backend.services.whisper_runtime.is_installed',lambda:False)
    monkeypatch.setattr('backend.core.project_cancellation.run',lambda *_a,**_k:pytest.fail('no runtime, no subprocess'))
    assert alignment.local_words(tmp_path/'source.mp4',0,20) is None


def test_project_cancellation_is_not_swallowed_by_alignment(monkeypatch):
    from backend.services.studio import ending_alignment as alignment
    from backend.core.project_cancellation import JobStopped
    monkeypatch.setattr(alignment,'project_words',lambda *_:None)
    monkeypatch.setattr(alignment,'local_words',lambda *_a, **_k:(_ for _ in ()).throw(JobStopped()))
    monkeypatch.setattr('backend.services.studio.jobs.source',lambda *_:'video.mp4')
    with pytest.raises(JobStopped):
        alignment.align_project('p',[(0,2,'We have enough time.')],[boundaries.ClipBounds(0,2,end_anchor=(0,20))])


def test_acoustic_extension_keeps_selected_text_and_excludes_unspoken_next_row():
    from backend.services.studio.ending_alignment import align_ending
    from backend.services.studio.packaging import draft_lines
    from backend.services.studio.models import Scene
    rows = [(0, 2, 'We need a longer timeframe.'), (2, 5, 'What comes next?')]
    bound = boundaries.ClipBounds(0, 2, end_anchor=(0, len(rows[0][2])))
    words = [{'text':t,'start':a,'end':b} for t,a,b in
             [('We',0,.2),('need',.2,.5),('a',.5,.7),('longer',.7,1.4),('timeframe',1.4,2.32),('What',2.65,2.9)]]
    result = align_ending(rows,bound,words,lambda *_:[(2.4,2.65)])
    scene = Scene(id='s',start=0,end=result[1],caption_end=result.caption_end)
    entries = [{'start_time':f'00:00:{a:06.3f}','end_time':f'00:00:{b:06.3f}','text':t} for a,b,t in rows]
    lines = draft_lines(entries,[Scene.model_validate_json(scene.model_dump_json()).model_dump()])
    assert ' '.join(l['text'] for l in lines) == rows[0][2]
    assert lines[-1]['end'] == result[1]
    edited = scene.model_dump(); edited['end'] = 5
    assert any('What comes next' in l['text'] for l in draft_lines(entries,[edited]))
    entries[0]['text'] = 'Changed source.'
    assert any('What comes next' in l['text'] for l in draft_lines(entries,[scene.model_dump()]))


def test_local_alignment_failure_does_not_discard_clip_or_hide_review(monkeypatch):
    from backend.services.studio import ending_alignment as alignment
    import subprocess
    monkeypatch.setattr(alignment,'project_words',lambda *_:None)
    monkeypatch.setattr(alignment,'local_words',lambda *_a,**_k:(_ for _ in ()).throw(subprocess.TimeoutExpired('worker',1)))
    monkeypatch.setattr('backend.services.studio.jobs.source',lambda *_:'video.mp4')
    bound = boundaries.ClipBounds(0,2,end_anchor=(0,20))
    result = alignment.align_project('p',[(0,2,'We have enough time.')],[bound])[0]
    assert result == bound and result.needs_review


def test_worker_uses_local_model_and_own_source_directory(tmp_path,monkeypatch):
    from backend.services.studio import ending_alignment as alignment
    from types import SimpleNamespace
    monkeypatch.setattr('backend.services.whisper_runtime.is_installed',lambda:True)
    monkeypatch.setattr('backend.services.whisper_runtime.get_install_dir',lambda:tmp_path/'runtime')
    monkeypatch.setattr('backend.services.whisper_model_manager.get_model_manager',lambda:SimpleNamespace(get_local_model_path=lambda _:tmp_path/'model'))
    monkeypatch.setattr('backend.utils.speech_recognizer.configured_whisper_model',lambda:'base')
    monkeypatch.setattr('backend.services.studio.qa.schedule._interpreter',lambda:'/portable/python')
    monkeypatch.setattr('backend.utils.ffmpeg_utils.get_ffmpeg_path',lambda:'/portable/ffmpeg')
    seen={}
    def run(command,**kw):
        seen.update(command=command,**kw)
        return SimpleNamespace(stdout=b'{"words":[]}')
    monkeypatch.setattr(alignment.project_cancellation,'run',run)
    assert alignment.local_words('video.mp4',0,22)==[]
    assert seen['cwd']==alignment.Path(alignment.__file__).resolve().parents[3]
    assert seen['env']['HF_HUB_OFFLINE']=='1'
    assert seen['command'][0]=='/portable/python' and str(tmp_path/'model') in seen['command']
    assert seen['timeout']<=45


def test_zero_duration_next_word_bounds_cut_but_cannot_verify_terminal_word():
    from backend.services.studio.ending_alignment import align_ending
    rows=[(0,2,'We have enough time.')]
    bound=boundaries.ClipBounds(0,2,end_anchor=(0,len(rows[0][2])))
    words=[{'text':t,'start':i*.5,'end':i*.5+.45} for i,t in enumerate(['We','have','enough','time'])]
    words.append({'text':'Next','start':2.1,'end':2.1})
    result=align_ending(rows,bound,words,lambda *_:[])
    assert result.word_aligned and 1.95 < result[1] < 2.1
    words[3]['end']=words[3]['start']
    assert not align_ending(rows,bound,words,lambda *_:[]).word_aligned
    words[3].update(end=1.95,probability=.1)
    assert not align_ending(rows,bound,words,lambda *_:[]).word_aligned
