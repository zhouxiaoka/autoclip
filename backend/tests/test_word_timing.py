"""No model download/provider calls: exercise ASR output capture and stale timing safety."""
import json
import sys
from types import SimpleNamespace
import pytest
from backend.utils.word_timing import write_word_timing, load_word_timing, sidecar_path
from backend.utils.subtitle_processor import SubtitleProcessor


@pytest.fixture
def sample(tmp_path):
    srt = tmp_path/'input.srt'
    srt.write_text('1\n00:00:00,000 --> 00:00:02,000\nCan you escape?\n')
    segments=[{'text':'Can you escape?', 'start':0, 'end':2, 'words':[
        {'text':'Can', 'start':.1,'end':.3},
        {'text':' you', 'start':.6,'end':.8},
        {'text':' escape?', 'start':1.2,'end':1.9}]}]
    return srt,segments


def test_preserves_real_pauses_and_punctuation(sample):
    srt,segments=sample
    write_word_timing(srt,segments,'en')
    assert load_word_timing(srt)==segments
    parsed=SubtitleProcessor().parse_srt_to_word_level(srt)[0]
    assert parsed['timingSource']=='asr'
    assert [w['startTime'] for w in parsed['words']]==[.1,.6,1.2]
    assert ''.join(w['text'] for w in parsed['words'])==parsed['text']


def test_edited_or_translated_srt_rejects_old_alignment(sample):
    srt,segments=sample
    write_word_timing(srt,segments,'en')
    srt.write_text(srt.read_text().replace('Can you escape?', '你能逃出去吗？'))
    assert load_word_timing(srt) is None
    parsed=SubtitleProcessor().parse_srt_to_word_level(srt)[0]
    assert parsed['timingSource']=='estimated'


@pytest.mark.parametrize('mutation', ['nan','reverse','overlap','outside','partial','missing'])
def test_invalid_alignment_never_becomes_precise(sample,mutation):
    srt,segments=sample
    words=segments[0]['words']
    if mutation=='nan':words[0]['start']=float('nan')
    if mutation=='reverse':words[0]['end']=0
    if mutation=='overlap':words[1]['start']=.2
    if mutation=='outside':words[-1]['end']=2.1
    if mutation=='partial':words.pop()
    if mutation=='missing':words[0].pop('start')
    with pytest.raises(ValueError):write_word_timing(srt,segments)
    assert load_word_timing(srt) is None


def test_corrupt_and_future_sidecars_fall_back(sample):
    srt,segments=sample
    sidecar_path(srt).write_text('{broken')
    assert load_word_timing(srt) is None
    write_word_timing(srt,segments)
    data=json.loads(sidecar_path(srt).read_text());data['schema_version']=9
    sidecar_path(srt).write_text(json.dumps(data))
    assert load_word_timing(srt) is None


def test_whisper_requests_and_saves_word_timing(tmp_path,monkeypatch):
    from backend.services import whisper_runtime
    from backend.utils.speech_recognizer import SpeechRecognizer, SpeechRecognitionConfig, LanguageCode
    monkeypatch.setattr(whisper_runtime,'is_installed',lambda:True)
    monkeypatch.setattr(whisper_runtime,'ensure_on_path',lambda:None)
    monkeypatch.setattr(whisper_runtime,'get_models_dir',lambda:tmp_path)
    captured=[]
    class Model:
        def __init__(self,*args,**kwargs):pass
        def transcribe(self,path,**kwargs):
            captured.append(kwargs)
            return iter([SimpleNamespace(start=0,end=2,text=' Hello world.',words=[
                SimpleNamespace(word=' Hello',start=.1,end=.4),
                SimpleNamespace(word=' world.',start=1.2,end=1.9)])]),SimpleNamespace(language='en')
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=Model))
    source=tmp_path/'audio.wav';source.write_bytes(b'mock audio')
    output=tmp_path/'input.srt'
    recognizer=SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer._generate_subtitle_whisper_local(source,output,SpeechRecognitionConfig(language=LanguageCode.ENGLISH_US))
    assert captured==[{'language':'en','vad_filter':True,'word_timestamps':True}]
    assert load_word_timing(output)[0]['words'][1]['start']==1.2
    assert SubtitleProcessor().parse_srt_to_word_level(output)[0]['timingSource']=='asr'
    # Existing captions must never trigger a surprise retranscription/download.
    recognizer._generate_subtitle_whisper_local(source,output,SpeechRecognitionConfig())
    assert len(captured)==1
