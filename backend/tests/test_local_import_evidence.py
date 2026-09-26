from pathlib import Path
import pytest
from backend.services.studio import local_evidence, planning, intelligence, analysis_preferences
from backend.services.studio.models import ImportOptions

@pytest.fixture
def video(tmp_path,monkeypatch):
    monkeypatch.setattr(analysis_preferences,'load',lambda:analysis_preferences.AnalysisPreferences())
    monkeypatch.setattr(intelligence,'_probe',lambda _:{'duration':20,'width':1920,'height':1080})
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k:pytest.fail('no visual call'))
    monkeypatch.setattr(intelligence,'text_json',lambda *a,**k:pytest.fail('no text call'))
    return tmp_path/'video.mp4'


def test_subtitle_evidence_recommends_without_claiming_content_type(video):
    video.with_name('input.srt').write_text('1\n00:00:00,000 --> 00:00:04,000\nFirst\n\n2\n00:00:03,000 --> 00:00:07,000\nSecond\n\n3\n00:00:08,000 --> 00:00:10,000\nThird\n')
    result=planning.recommend(video,ImportOptions())
    assert result['suggested_goals']==['content','highlight']
    assert result['local_evidence']['covered_seconds']==9
    assert result['content_type']=='other' and result['confidence']==0
    assert 'First' not in str(result['local_evidence'])

@pytest.mark.parametrize('raw,status',[(None,'missing'),(b'bad','invalid'),(b'\xff','invalid'),(b'x'*(local_evidence.MAX_SUBTITLE_BYTES+1),'too_large'),(b'1\n00:00:19,000 --> 00:00:21,000\nOutside\n','invalid')])
def test_unverified_subtitles_do_not_preselect_or_start_transcription(video,raw,status):
    if raw is not None:video.with_name('input.srt').write_bytes(raw)
    result=planning.recommend(video,ImportOptions())
    assert result['suggested_goals']==[]
    assert result['local_evidence']['subtitle_status']==status
    assert result['recommended_analysis']=='subtitle'


def test_explicit_goal_is_preserved_even_without_subtitles(video):
    result=planning.recommend(video,ImportOptions(goal='promo'))
    assert result['suggested_goals']==['promo'] and result['mode']=='manual'


def test_duplicate_cues_do_not_inflate_local_highlight_suggestion(video):
    video.with_name('input.srt').write_text('1\n00:00:00,000 --> 00:00:07,000\nSame\n\n2\n00:00:00,000 --> 00:00:07,000\nSame\n\n3\n00:00:00,000 --> 00:00:07,000\nSame\n')
    result=planning.recommend(video,ImportOptions())
    assert result['suggested_goals']==['content']
    assert result['local_evidence']['valid_cues']==1
