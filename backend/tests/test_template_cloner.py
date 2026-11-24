"""End-to-end tests for scripts/template_cloner.py and the template-cloner skill."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.services.studio.models import ImportOptions
from backend.services.studio.templates import registry
from scripts import template_cloner, template_factory

ROOT = Path(__file__).resolve().parents[2]


def test_template_cloner_skill_files_exist():
    skill = ROOT / 'skills' / 'template-cloner' / 'SKILL.md'
    cheat = ROOT / 'skills' / 'template-cloner' / 'references' / 'spec-v2-cheatsheet.md'
    assert skill.is_file() and cheat.is_file()
    text = skill.read_text(encoding='utf-8')
    assert 'name: template-cloner' in text
    assert 'scripts/template_cloner.py extract-ref' in text
    assert 'scripts/template_cloner.py install-local' in text


def test_extract_ref_from_images_and_install_local(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    shot = tmp_path / 'shot.png'
    shot.write_bytes(b'\x89PNG\r\n\x1a\nfake')

    work = tmp_path / 'ref_work'
    assert template_cloner.main(['extract-ref', str(shot), '--out', str(work)]) == 0
    brief = json.loads((work / 'reference_brief.json').read_text(encoding='utf-8'))
    assert brief['kind'] == 'images'
    assert brief['count'] == 1
    assert Path(brief['frames'][0]).is_file()

    tpl_root = tmp_path / 'cloned'
    assert template_factory.main([
        'scaffold', 'xhs_tech_card',
        '--name-zh', '小红书技术卡',
        '--name-en', 'XHS Tech Card',
        '--out', str(tpl_root),
    ]) == 0

    assert template_cloner.main(['install-local', str(tpl_root / 'xhs_tech_card')]) == 0
    assert registry.is_html_template('xhs_tech_card')
    assert ImportOptions(html_template='xhs_tech_card').html_template == 'xhs_tech_card'


def test_extract_ref_from_video_produces_keyframes_and_contact_sheet(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg/ffprobe unavailable')
    video = tmp_path / 'viral_ref.mp4'
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc2=s=270x480:r=24:d=2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video),
        ],
        check=True,
    )
    work = tmp_path / 'video_ref'
    assert template_cloner.main(['extract-ref', str(video), '--out', str(work), '--frames', '4']) == 0
    brief = json.loads((work / 'reference_brief.json').read_text(encoding='utf-8'))
    assert brief['kind'] == 'video'
    assert brief['aspect'] == 'portrait'
    assert brief['width'] == 270 and brief['height'] == 480
    assert len(brief['frames']) == 4
    assert all(Path(p).is_file() for p in brief['frames'])
    assert brief['contact_sheet'] and Path(brief['contact_sheet']).is_file()
