"""Packaging version 2 reads the HTML templates. Version 1 classic payloads stay valid."""
import pytest
from pydantic import ValidationError

from backend.services.studio.models import Packaging


def test_version_1_classic_payload_still_loads_and_dumps_without_extended_fields():
    raw = {
        'version': 1,
        'template': 'interview_zh',
        'audience_language': 'zh',
        'title_lines': ['好的投资人', '像飞行教练'],
        'cues': [{'start': 1.0, 'end': 2.0, 'text': '原话', 'original': 'source'}],
    }
    model = Packaging.model_validate(raw)
    assert model.version == 1 and model.template == 'interview_zh' and model.kicker == ''
    assert model.emphasis == [] and model.numbers == [] and model.gloss == []
    podcast = Packaging(template='podcast_en', audience_language='en', style='pop')
    assert podcast.version == 1 and podcast.style == 'pop'


def test_version_1_rejects_html_ids_and_extended_fields():
    with pytest.raises(ValidationError):
        Packaging.model_validate({'version': 1, 'template': 'editorial', 'audience_language': 'zh'})
    with pytest.raises(ValidationError):
        Packaging.model_validate({
            'version': 1, 'template': 'interview_zh', 'audience_language': 'zh', 'kicker': '访谈',
        })
    with pytest.raises(ValidationError):
        Packaging.model_validate({'version': 2, 'template': 'podcast', 'audience_language': 'zh'})


def test_version_2_editorial_and_street_round_trip():
    editorial = Packaging.model_validate({
        'version': 2,
        'template': 'editorial',
        'audience_language': 'zh',
        'title_lines': ['一句钩子'],
        'kicker': '访谈',
        'emphasis': [{'at': 1.2, 'text': '飞行教练'}],
        'numbers': [{'at': 3.0, 'value': 70, 'unit': '秒', 'text': '七十秒'}],
        'gloss': [{'at': 4.0, 'title': '术语', 'body': '解释'}],
        'cues': [{'start': 1.0, 'end': 4.0, 'text': '七十秒', 'original': ''}],
    })
    assert editorial.template == 'editorial' and editorial.numbers[0].value == 70
    street = Packaging(version=2, template='street', audience_language='zh', title_lines=['街头', '一问'])
    assert street.gloss == [] and street.style is None
    with pytest.raises(ValidationError):
        Packaging(version=2, template='editorial', audience_language='zh', style='pop')


def test_classic_style_constraint_still_holds():
    with pytest.raises(ValidationError):
        Packaging(template='interview_zh', audience_language='zh', style='pop')
    with pytest.raises(ValidationError):
        Packaging(template='podcast_en', audience_language='en', style='spotlight')
