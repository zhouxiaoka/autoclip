"""Creator-uploaded subtitles replace speech recognition; automatic captions never do (no network)."""
from backend.services.studio import jobs
from backend.utils import download_recovery

SRT = ''.join(f'{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},900\nLine {i}.\n\n' for i in range(1, 31))


def _fake_download(monkeypatch, calls, text=SRT):
    def fetch(url, options):
        calls.append(options['subtitleslangs'])
        folder = options['outtmpl'].rsplit('/', 1)[0]
        open(f"{folder}/platform.{options['subtitleslangs'][0]}.srt", 'w', encoding='utf-8').write(text)
    monkeypatch.setattr(download_recovery, 'download_with_recovery', fetch)


def test_uploaded_subtitles_in_the_video_language_become_the_transcript(monkeypatch, tmp_path):
    calls = []
    _fake_download(monkeypatch, calls)
    info = {'language': 'en', 'subtitles': {'es': [{}], 'en-US': [{}]}, 'automatic_captions': {'en': [{}]}}
    assert jobs._fetch_platform_subtitles('https://youtu.be/x', {'format': 'best'}, info, tmp_path)
    assert calls == [['en-US']] and (tmp_path / 'input.srt').read_text(encoding='utf-8') == SRT
    assert [p.name for p in tmp_path.iterdir()] == ['input.srt']


def test_automatic_captions_or_other_languages_keep_speech_recognition(monkeypatch, tmp_path):
    calls = []
    _fake_download(monkeypatch, calls)
    assert not jobs._fetch_platform_subtitles('u', {}, {'language': 'en', 'subtitles': {}, 'automatic_captions': {'en': [{}]}}, tmp_path)
    assert not jobs._fetch_platform_subtitles('u', {}, {'language': 'ja', 'subtitles': {'en': [{}]}}, tmp_path)
    assert not jobs._fetch_platform_subtitles('u', {}, {'subtitles': {'en': [{}]}}, tmp_path)  # unknown language
    assert calls == []


def test_a_stub_subtitle_file_is_ignored(monkeypatch, tmp_path):
    _fake_download(monkeypatch, [], text='1\n00:00:01,000 --> 00:00:02,000\nMusic\n\n')
    assert not jobs._fetch_platform_subtitles('u', {}, {'language': 'en', 'subtitles': {'en': [{}]}}, tmp_path)
    assert not (tmp_path / 'input.srt').exists() and not list(tmp_path.iterdir())
