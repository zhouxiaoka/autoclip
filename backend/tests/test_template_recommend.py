"""Style recommendation stays inside a short budget and returns enums only."""
from pathlib import Path
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.studio import jobs, store
from backend.services.studio.models import ImportOptions
from backend.services.studio.template_recommend import decide, recommend_template, signals_from_media


def test_picture_shape_and_length_choose_a_style():
    street = signals_from_media(1080, 1920, 40)
    assert street['people'] == 'unknown'
    assert street['duration_bucket'] == 'short'
    assert decide(street) == ('street', 'street_quick')
    seated = signals_from_media(1920, 1080, 700)
    assert decide(seated) == ('editorial', 'seated_interview')
    talk = signals_from_media(1920, 1080, 240)
    assert decide(talk) == ('editorial', 'speech')
    missing = signals_from_media(None, None, None)
    assert decide(missing) == ('editorial', 'default')
    assert decide({'scene': 'speech', 'pace': 'fast'}) == ('street', 'street_quick')


def test_a_slow_probe_falls_back_without_leaving_the_budget():
    def slow(_header, _budget):
        raise TimeoutError('probe timed out')

    result = recommend_template(url='https://www.youtube.com/watch?v=abc', header=b'not-a-movie', probe=slow)
    assert result['template'] == 'editorial'
    assert result['reason_code'] == 'timeout'
    assert result['signals']['people'] == 'unknown'
    assert 'youtube' not in str(result)
    empty = recommend_template(url='https://www.youtube.com/watch?v=abc')
    assert empty['reason_code'] == 'default'
    assert empty['template'] == 'editorial'


def test_recommend_route_rejects_an_empty_body_and_does_not_echo_the_url():
    from backend.api.v1.studio import router

    app = FastAPI()
    app.include_router(router, prefix='/studio')
    client = TestClient(app)
    missing = client.post('/studio/template-recommend')
    assert missing.status_code == 422
    refused = client.post('/studio/template-recommend', data={'url': 'http://example.com/watch'})
    assert refused.status_code == 422
    ok = client.post('/studio/template-recommend', data={'url': 'https://youtu.be/abcdefghijk'})
    assert ok.status_code == 200
    body = ok.json()
    assert body['template'] == 'editorial'
    assert body['reason_code'] == 'default'
    assert 'youtu' not in str(body)


def test_recommend_route_probes_local_video_after_closing_temp_writer(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    from backend.api.v1.studio import router
    from backend.services.studio import template_recommend
    from backend.utils.ffmpeg_utils import get_ffmpeg_path

    sample = tmp_path / 'vertical.mp4'
    subprocess.run([get_ffmpeg_path(), '-v', 'error', '-f', 'lavfi', '-i',
                    'color=s=180x320:d=1', '-movflags', '+faststart', str(sample)], check=True)

    open_temp = template_recommend.tempfile.NamedTemporaryFile
    run = subprocess.run
    writers = {}
    probed = []

    def track_temp_writer(*args, **kwargs):
        writer = open_temp(*args, **kwargs)
        writers[writer.name] = writer
        return writer

    def probe_with_windows_sharing(command, **kwargs):
        filename = command[-1]
        probed.append(Path(filename))
        writer = writers.get(filename)
        if writer is not None and not writer.closed:
            return subprocess.CompletedProcess(command, 1, b'', b'Permission denied')
        return run(command, **kwargs)

    monkeypatch.setattr(template_recommend.tempfile, 'NamedTemporaryFile', track_temp_writer)
    monkeypatch.setattr(template_recommend.subprocess, 'run', probe_with_windows_sharing)
    app = FastAPI()
    app.include_router(router, prefix='/studio')
    response = TestClient(app).post('/studio/template-recommend', files={
        'header': ('vertical.mp4', sample.read_bytes(), 'video/mp4'),
    })
    assert response.status_code == 200, response.text
    assert response.json()['reason_code'] == 'street_quick'
    assert len(probed) == 1 and not probed[0].exists()


@pytest.mark.parametrize('selected,accepted', [('street', False), ('editorial', True)])
def test_import_keeps_the_recommendation_next_to_the_choice(tmp_path, monkeypatch, selected, accepted):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('p1').mkdir()
    monkeypatch.setattr(jobs.executor, 'submit', lambda *_args, **_kwargs: None)
    jobs.inspect_project('p1', ImportOptions(
        auto_start=False, platforms=['douyin'], html_template=selected, recommended_template='editorial',
    ))
    generation = store.read('p1')['generation']
    assert generation['html_template'] == selected
    assert generation['recommended_template'] == 'editorial'
    assert generation['accepted_recommendation'] is accepted
