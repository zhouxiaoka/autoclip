"""Regression tests for Phase-2 local ONNX 3-layer subject segmentation depth engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.studio import packaging_html, subject_matte
from backend.services.studio.templates.spec import TemplateSpec


def _minimal_spec(*, subject_layer: bool = False, back_entry: str | None = None) -> dict:
    overlay = {
        'entry': 'index.html',
        'slots': {'hook': {'top': 170}, 'subtitle': {'top': 1350, 'max_rows': 2}},
        'safe_area': 'tiktok',
        'limits': {'emphasis_gap_s': 2.0},
    }
    if back_entry is not None:
        overlay['back_entry'] = back_entry
    return {
        'id': 'depth_test',
        'version': 2,
        'name': {'zh': '景深测试', 'en': 'Depth Test'},
        'fit': {'formats': {'vlog': 1.0}, 'needs_face': True},
        'canvas': {'aspects': ['portrait'], 'overlay_px': [1080, 1920], 'fps': 30},
        'base': {
            'framing': 'full_face',
            'face_y': 0.36,
            'head_zone': [240, 1140],
            'zoom': {'mode': 'creep', 'creep': 0.02},
            'transitions': {'broll': 'none', 'max': 0},
            'grade': 'eq=contrast=1.04',
            'picture_layout': 'crop',
            'subject_layer': subject_layer,
        },
        'overlay': overlay,
        'fields': {'required': ['title_lines', 'cues'], 'optional': ['kicker']},
        'audio': {'bgm': 'none'},
        'cover': {'layout': 'street_9x16', 'from_overlay': True},
        'qa': {},
    }


def test_spec_accepts_subject_layer_and_back_entry():
    spec = TemplateSpec.model_validate(_minimal_spec(subject_layer=True, back_entry='back.html'))
    assert spec.base.subject_layer is True
    assert spec.overlay.back_entry == 'back.html'


def test_spec_rejects_invalid_back_entry():
    with pytest.raises(Exception):
        TemplateSpec.model_validate(_minimal_spec(subject_layer=True, back_entry='../evil.html'))


def test_composite_tail_4_layer_depth_sandwich():
    graph, label = packaging_html.composite_tail(
        'base', 1, 1080, 1920, 'eq=contrast=1.05',
        back_overlay_index=2, matte_index=3,
    )
    assert label == 'html'
    assert 'split=2[bg_l][fg_l]' in graph
    assert '[2:v]scale=1080:1920:flags=lanczos,format=yuva420p[ov_b]' in graph
    assert '[3:v]scale=1080:1920:flags=bilinear,format=gray[m_gray]' in graph
    assert '[fg_yuva][m_gray]alphamerge[fg_cut]' in graph
    assert '[with_back][fg_cut]overlay=0:0:format=yuv420:eof_action=repeat[with_fg]' in graph
    assert '[with_fg][ov]overlay=0:0:format=yuv420:eof_action=repeat[html]' in graph


def test_composite_tail_3_layer_behind_subject_only():
    graph, label = packaging_html.composite_tail(
        'base', 1, 1080, 1920, 'eq=contrast=1.05',
        matte_index=2,
    )
    assert label == 'html'
    assert '[bg_l][ov]overlay=0:0:format=yuv420:eof_action=repeat[with_back]' in graph
    assert '[with_back][fg_cut]overlay=0:0:format=yuv420:eof_action=repeat[html]' in graph


def test_composite_tail_standard_2_layer_unchanged():
    graph, label = packaging_html.composite_tail('base', 1, 1080, 1920, 'eq=contrast=1.05')
    assert label == 'html'
    assert 'alphamerge' not in graph
    assert '[graded][ov]overlay=0:0:format=yuv420:eof_action=repeat[html]' in graph


def test_overlay_cache_path_separates_front_and_back(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    p_front = packaging_html.overlay_cache_path('proj1', 'editorial', {'a': 1}, frames=90, entry='index.html')
    p_back = packaging_html.overlay_cache_path('proj1', 'editorial', {'a': 1}, frames=90, entry='back.html')
    assert p_front != p_back


def test_subject_matte_graceful_fallback_on_invalid_duration(tmp_path):
    res = subject_matte.generate_scene_matte(
        Path('/nonexistent.mp4'),
        start=0.0,
        duration=0.0,
        picture_filter='[0:v]null[base]',
        picture_label='base',
        dest=tmp_path / 'm.mp4',
    )
    assert res is None
