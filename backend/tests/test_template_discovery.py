"""Unit tests for the internal viral template discovery pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from scripts.template_discovery import analyzer, report, sources


def test_parse_duration_and_engagement_score():
    assert sources._parse_duration('1:32') == 92.0
    assert sources._parse_duration('01:02:03') == 3723.0
    assert sources._parse_duration(45) == 45.0
    assert sources._parse_duration('') == 0.0

    c_high = sources.CandidateVideo(id='a', platform='youtube', track='gaming', title='High', url='https://yt', views=500_000, likes=50_000)
    c_low = sources.CandidateVideo(id='b', platform='youtube', track='gaming', title='Low', url='https://yt', views=5_000, likes=100)
    assert c_high.engagement_score > c_low.engagement_score


def test_fetch_youtube_apify_graceful_without_token_and_parses_mocked(monkeypatch):
    monkeypatch.delenv('APIFY_TOKEN', raising=False)
    assert sources.fetch_youtube_apify(['gta clip'], track='gaming') == []

    fake_items = [{
        'id': 'abc123',
        'title': 'Insane GTA Clip',
        'url': 'https://www.youtube.com/shorts/abc123',
        'channelName': 'SpeedLive',
        'viewCount': 1_200_000,
        'likes': 95_000,
        'duration': '0:28',
        'thumbnailUrl': 'https://i.ytimg.com/vi/abc123/hqdefault.jpg',
        'searchQuery': 'gta clip',
    }]
    with patch.object(sources, '_http_json', return_value=fake_items):
        res = sources.fetch_youtube_apify(['gta clip'], track='gaming', token='test-token')
    assert len(res) == 1
    assert res[0].id == 'abc123'
    assert res[0].views == 1_200_000
    assert res[0].duration_sec == 28.0


def test_fetch_bilibili_search_parses_and_filters():
    fake_resp = {
        'data': {
            'result': [
                {
                    'bvid': 'BV1test1234',
                    'title': '<em class="keyword">GTA</em> 爆笑切片',
                    'author': '主播切片君',
                    'play': 320_000,
                    'like': 18_000,
                    'duration': '0:42',
                    'pic': '//i0.hdslb.com/bfs/archive/test.jpg',
                },
                {
                    'bvid': 'BV1toolong',
                    'title': '超长完整录播',
                    'author': '录播组',
                    'play': 500_000,
                    'duration': '55:00',
                    'pic': '//i0.hdslb.com/bfs/archive/long.jpg',
                },
            ],
        },
    }
    with patch.object(sources, '_http_json', return_value=fake_resp):
        res = sources.fetch_bilibili_search(['GTA 切片'], track='gaming', max_duration_sec=120)
    assert len(res) == 1
    assert res[0].id == 'BV1test1234'
    assert res[0].title == 'GTA 爆笑切片'
    assert res[0].thumbnail_url == 'https://i0.hdslb.com/bfs/archive/test.jpg'


def test_layout_signals_detects_split_seam_and_sandwich_bars():
    # 1. Synthetic split-screen portrait: bright coral top 38%, dark navy bottom 62%
    split_im = Image.new('RGB', (360, 640), (15, 20, 30))
    draw = ImageDraw.Draw(split_im)
    draw.rectangle([0, 0, 360, 243], fill=(240, 180, 160))
    sig_split = analyzer._image_layout_signals(split_im)
    assert sig_split['aspect'] == 'portrait'
    assert sig_split['has_split_seam'] is True
    assert 0.34 <= (sig_split['seam_y_ratio'] or 0) <= 0.42
    arch, _ = analyzer.classify_archetype(sig_split, track='gaming')
    assert arch == 'streamer_split'

    # 2. Synthetic sandwich card: solid dark top/bottom bands + textured middle
    card_im = Image.new('RGB', (360, 640), (18, 22, 36))
    cdraw = ImageDraw.Draw(card_im)
    for y in range(180, 460, 8):
        for x in range(0, 360, 12):
            cdraw.rectangle([x, y, x + 6, y + 6], fill=(230, 120, 40) if (x + y) % 16 == 0 else (30, 190, 210))
    sig_card = analyzer._image_layout_signals(card_im)
    assert sig_card['has_top_bottom_bars'] is True
    arch_game, _ = analyzer.classify_archetype(sig_card, track='gaming')
    assert arch_game == 'headline_sandwich'
    arch_int, _ = analyzer.classify_archetype(sig_card, track='interview')
    assert arch_int == 'interview_card'


def test_write_report_generates_markdown_json_and_contact_sheet(tmp_path: Path):
    kf = tmp_path / 'sample.jpg'
    Image.new('RGB', (360, 640), (40, 120, 210)).save(kf)
    cand = sources.CandidateVideo(
        id='vid1', platform='youtube', track='gaming', title='Viral Sandwich Clip',
        url='https://www.youtube.com/shorts/vid1', views=800_000, likes=60_000,
    )
    ana = analyzer.StyleAnalysis(
        archetype='headline_sandwich', aspect='portrait', width=360, height=640,
        has_top_bottom_bars=True, palette=['#2878D2', '#111111'],
        keyframe_paths=[str(kf)], existing_match=[], is_new_opportunity=True,
        notes='上下标题/字幕留白三明治结构',
    )
    out = report.write_report([(cand, ana)], tmp_path / 'out')
    assert out['json'].is_file()
    assert out['markdown'].is_file()
    assert out['contact_sheet'].is_file()
    data = json.loads(out['json'].read_text(encoding='utf-8'))
    assert data['count'] == 1
    assert data['items'][0]['analysis']['is_new_opportunity'] is True
    md = out['markdown'].read_text(encoding='utf-8')
    assert 'headline_sandwich' in md and 'NEW' in md
