"""Tests for the Creator Pack compiler (Theme x Layout x Effect, event arbitration, FFmpeg graph)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.services.studio import creator_pack as cp
from backend.services.studio import overlay_fill, packaging_html
from backend.services.studio.templates import registry as template_registry


CATALOG_ROOT = Path(__file__).resolve().parents[2] / 'templates-catalog'


def test_arbitrate_events_confidence_and_asr_policy():
    raw = [
        {'id': 'a1', 'type': 'exploration', 'frame': 10, 'source': 'vision', 'confidence': 0.55},
        {'id': 'a2', 'type': 'exploration', 'frame': 40, 'source': 'vision', 'confidence': 0.72},
        {'id': 'a3', 'type': 'crash', 'frame': 80, 'source': 'asr', 'confidence': 0.95},
        {'id': 'a4', 'type': 'crash', 'frame': 120, 'source': 'vision', 'confidence': 0.85},
    ]
    accepted, pending = cp.arbitrate_events(raw, duration_frames=360)
    assert [e.id for e in accepted] == ['a4']
    pending_by_id = {p['id']: p['reason'] for p in pending}
    assert pending_by_id == {'a2': 'low_confidence', 'a3': 'asr_only'}


def test_arbitrate_events_dedup_mutex_and_cooldown():
    raw = [
        # Same-type within 12 frames: higher confidence (c2) wins dedup over c1.
        {'id': 'c1', 'type': 'crash', 'frame': 95, 'source': 'vision', 'confidence': 0.82},
        {'id': 'c2', 'type': 'crash', 'frame': 100, 'source': 'vision', 'confidence': 0.95},
        # Active-interval overlap with c2 (100..130): lower priority glitch at 106 is suppressed.
        {'id': 'g1', 'type': 'glitch', 'frame': 106, 'source': 'vision', 'confidence': 0.99},
        # Per-effect cooldown (90 frames for impact-hold): lower-confidence crash at 150 is suppressed.
        {'id': 'c3', 'type': 'crash', 'frame': 150, 'source': 'vision', 'confidence': 0.90},
        # After cooldown (>= 190): crash at 195 is accepted.
        {'id': 'c4', 'type': 'crash', 'frame': 195, 'source': 'vision', 'confidence': 0.88},
    ]
    accepted, _ = cp.arbitrate_events(raw, duration_frames=360)
    assert [e.id for e in accepted] == ['c2', 'c4']


def test_arbitrate_events_manual_beats_higher_priority_ai():
    raw = [
        {'id': 'ai_crash', 'type': 'crash', 'frame': 100, 'source': 'vision', 'confidence': 0.99},
        {'id': 'man_exp', 'type': 'exploration', 'frame': 104, 'source': 'manual'},
    ]
    accepted, _ = cp.arbitrate_events(raw, duration_frames=360)
    assert [e.id for e in accepted] == ['man_exp']


@pytest.mark.parametrize('theme_id', ['vice-city-sunset', 'wasted', 'leonida-news'])
@pytest.mark.parametrize('layout_id', ['coast', 'split', 'desk', 'full'])
def test_resolve_render_plan_all_theme_layout_combinations(theme_id: str, layout_id: str):
    plan = cp.resolve_render_plan(
        theme_id=theme_id,
        layout_id=layout_id,
        camera_mode='embedded',
        camera_roi=[0.7, 0.7, 0.25, 0.25],
    )
    assert plan.theme_id == theme_id
    assert plan.layout_id == layout_id
    if layout_id == 'full':
        assert plan.camera_active is False
        assert plan.slots['camera'] is None
    else:
        assert plan.camera_active is True
        assert plan.slots['camera'] is not None


def test_resolve_render_plan_no_camera_widens_coast_and_split_caption():
    for layout_id in ('coast', 'split'):
        plan = cp.resolve_render_plan(theme_id='vice-city-sunset', layout_id=layout_id, camera_mode='none')
        assert plan.camera_active is False
        assert plan.slots['camera'] is None
        cap = plan.slots['caption']
        assert cap is not None
        assert cap[0] == 72 and cap[2] == 828


def test_resolve_render_plan_auto_theme_and_reduced_motion():
    plan = cp.resolve_render_plan(
        theme_id='auto',
        layout_id='auto',
        events=[{'id': 'e1', 'type': 'npc_oddity', 'frame': 20, 'source': 'vision', 'confidence': 0.9}],
        reduced_motion=True,
        strength=0.8,
    )
    assert plan.theme_id == 'leonida-news'
    assert plan.layout_id == 'desk'
    assert plan.reduced_motion is True
    assert plan.strength == 0.0


def test_event_phase_exact_boundaries():
    ev = {'frame': 100, 'enter': 3, 'hold': 15, 'exit': 12}
    assert cp.event_phase(99, ev) == 0.0
    assert cp.event_phase(100, ev) == pytest.approx(1 / 3)
    assert cp.event_phase(102, ev) == 1.0
    assert cp.event_phase(112, ev) == 1.0
    assert cp.event_phase(129, ev) == pytest.approx(1 / 12)
    assert cp.event_phase(130, ev) == 0.0


def test_build_base_video_graph_modes_and_impact_desat():
    # 1. Embedded camera ROI + impact-hold desaturation on game plane only, non-zero scene_start
    plan = cp.resolve_render_plan(
        theme_id='wasted',
        layout_id='split',
        camera_mode='embedded',
        camera_roi=[0.72, 0.70, 0.24, 0.24],
        events=[{'id': 'c1', 'type': 'crash', 'frame': 30, 'source': 'manual'}],
    )
    graph, label = cp.build_base_video_graph(plan, 1920, 1080, scene_start=12.5, scene_end=16.5, scene_offset=0.0)
    assert label == 'base'
    assert 'trim=start=' not in graph  # input 0 is already seeked by render.py
    assert 'split=2[src_g][src_c]' in graph
    assert "hue=s='if(between(t,1.000,1.600),0,1)'" in graph
    # Desaturation must appear on [src_g]...[game], NOT on [src_c]...[cam]
    game_part = [p for p in graph.split(';') if p.startswith('[src_g]')][0]
    cam_part = [p for p in graph.split(';') if p.startswith('[src_c]')][0]
    assert 'hue=s=' in game_part
    assert 'hue=s=' not in cam_part

    # 2. Separate camera input stream
    sep_plan = cp.resolve_render_plan(theme_id='leonida-news', layout_id='desk', camera_mode='separate')
    sep_graph, _ = cp.build_base_video_graph(sep_plan, 1920, 1080, scene_start=0.0, scene_end=3.2, camera_input_index=2)
    assert '[2:v]setpts=PTS-STARTPTS' in sep_graph
    assert '[with_game][cam]overlay=682:456:shortest=1[base]' in sep_graph

    # 3. Reduced motion disables desaturation
    rm_plan = cp.resolve_render_plan(
        theme_id='wasted',
        layout_id='split',
        reduced_motion=True,
        events=[{'id': 'c1', 'type': 'crash', 'frame': 30, 'source': 'manual'}],
    )
    rm_graph, _ = cp.build_base_video_graph(rm_plan, 1920, 1080, scene_start=0.0, scene_end=3.2)
    assert 'hue=s=' not in rm_graph


def test_viral_layouts_double_host_exclusion_and_fallback():
    # Left-edge embedded webcam (e.g. IShowSpeed x=0..22.5%) is excluded from the game crop
    plan = cp.resolve_render_plan(
        theme_id='wasted',
        layout_id='viral_split',
        camera_mode='embedded',
        camera_roi=[0.0, 0.358, 0.225, 0.273],
        events=[{'id': 'c1', 'type': 'crash', 'frame': 30, 'source': 'manual'}],
    )
    graph, _ = cp.build_base_video_graph(plan, 1920, 1080, scene_start=0.0, scene_end=4.0)
    game_part = [p for p in graph.split(';') if p.startswith('[src_g]')][0]
    assert 'crop=w=' in game_part and "x='trunc(iw*0.2300/2)*2'" in game_part
    assert 'scale=1080:1190:force_original_aspect_ratio=increase' in game_part

    # viral_pip applies rounded-corner alpha mask to the 360x360 camera stream
    pip_plan = cp.resolve_render_plan(
        theme_id='vice-city-sunset', layout_id='viral_pip', camera_mode='separate',
    )
    pip_graph, _ = cp.build_base_video_graph(pip_plan, 1920, 1080, scene_start=0.0, scene_end=3.2, camera_input_index=2)
    assert 'geq=lum=' in pip_graph and '[with_game][cam]overlay=676:128:shortest=1[base]' in pip_graph

    # viral_split with no camera falls back to full-bleed 1080x1920 game (never an empty top half)
    no_cam = cp.resolve_render_plan(theme_id='vice-city-sunset', layout_id='viral_split', camera_mode='none')
    assert no_cam.camera_active is False
    assert no_cam.slots['game'] == [0, 0, 1080, 1920]


def test_gta_templates_load_and_build_fill(tmp_path: Path, monkeypatch):
    import shutil
    data_dir = tmp_path / 'data'
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(data_dir))
    for tid, expected_theme, expected_layout in (
        ('streamer_split', 'vice-city-sunset', 'viral_split'),
        ('gta_wasted', 'wasted', 'viral_split'),
        ('streamer_pip', 'vice-city-sunset', 'viral_pip'),
    ):
        shutil.copytree(CATALOG_ROOT / tid, data_dir / 'templates' / tid)
        spec = template_registry.load_folder(CATALOG_ROOT / tid)
        assert spec.base.creator_pack is not None
        assert spec.base.creator_pack.theme == expected_theme
        assert spec.base.creator_pack.default_layout == expected_layout
        fill = overlay_fill.build_fill(
            {'title_lines': ['WAIT FOR IT'], 'audience_language': 'en', 'cues': [{'start': 0.0, 'end': 3.0, 'text': 'NO WAY!'}]},
            3.0,
            template=tid,
            creator_pack_overrides={'host': 'KAI LIVE', 'camera_mode': 'none'},
        )
        assert fill['creator_pack']['theme_id'] == expected_theme
        assert fill['creator_pack']['layout_id'] == expected_layout
        assert fill['creator_pack']['host'] == 'KAI LIVE'


def test_cached_overlay_fits_tolerates_ffconcat_tail_padding(tmp_path: Path):
    dummy = tmp_path / 'overlay.mkv'
    dummy.write_bytes(b'x' * 1024)
    with patch.object(packaging_html, '_cache_usable', return_value=True):
        # +0.08s ffconcat tail padding on 96-frame (3.200s) clip is safe
        with patch.object(packaging_html, '_overlay_duration', return_value=3.28):
            assert packaging_html._cached_overlay_fits(dummy, 96, 30) is True
        # Shorter by 0.10s is still rejected
        with patch.object(packaging_html, '_overlay_duration', return_value=3.10):
            assert packaging_html._cached_overlay_fits(dummy, 96, 30) is False
        # Way too long (+0.50s) is rejected
        with patch.object(packaging_html, '_overlay_duration', return_value=3.70):
            assert packaging_html._cached_overlay_fits(dummy, 96, 30) is False
