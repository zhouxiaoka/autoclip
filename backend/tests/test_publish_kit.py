"""Publish kit: per-platform post copy within platform rules, designed covers, the bundle (no model calls)."""
import io
import zipfile
import pytest

from PIL import Image

from backend.services.studio import cover_design, post_copy, publish_kit

LINES = ['Nvidia sends a GDS2 file to TSMC.', 'The moat is the supply chain and the trust of partners.']


def test_one_call_writes_copy_for_every_platform_within_its_rules():
    sent = []
    long_title = '英伟达真正的护城河不是芯片而是整条供应链的信任与规模引力'

    def call(prompt, data):
        sent.append(data)
        return {'posts': {
            'xiaohongshu': {'title': long_title, 'description': '要点一。要点二。', 'tags': ['#英伟达', '黄仁勋', '英伟达', 'AI 芯片', '供应链', '台积电', 'GPU', '护城河', '多余']},
            'tiktok': {'title': 'Nvidia&#39;s real moat', 'description': '**Supply chain** trust.', 'tags': ['Nvidia', 'AI']},
        }}

    posts = post_copy.build_posts('Nvidia 的护城河', LINES, ['xiaohongshu', 'tiktok', 'douyin'], source='Dwarkesh Patel', call=call)
    assert len(sent) == 1 and sent[0]['rules']['xiaohongshu']['title_max'] == 20
    xhs = posts['xiaohongshu']
    assert len(xhs['title']) <= 20 and xhs['tags'][:2] == ['英伟达', '黄仁勋'] and len(xhs['tags']) == 8  # deduped, capped, no '#'
    assert posts['tiktok'] == {'title': "Nvidia's real moat", 'description': 'Supply chain trust.', 'tags': ['Nvidia', 'AI']}
    assert posts['douyin'] == {'title': 'Nvidia 的护城河', 'description': '', 'tags': []}  # missing: falls back to the clip title


def test_copy_falls_back_to_the_clip_title_when_the_model_fails():
    def broken(*_):
        raise RuntimeError('provider down')
    assert post_copy.build_posts('一个标题', LINES, ['bilibili'], call=broken) == {'bilibili': {'title': '一个标题', 'description': '', 'tags': []}}


def _frame(width=1920, height=1080):
    out = io.BytesIO()
    Image.new('RGB', (width, height), (120, 90, 60)).save(out, format='JPEG')
    return out.getvalue()


def test_covers_match_each_platform_slot_and_keep_the_title_band_clear():
    for strategy, size in (('douyin', (1080, 1920)), ('xiaohongshu', (1080, 1440)), ('bilibili', (1146, 717))):
        data = cover_design.design(_frame(), width=size[0], height=size[1], title_lines=['电子变 Token', '无法被完全商品化'],
                                   palette='coral', speaker=('Jensen Huang', '英伟达 CEO'), crop_centre=.4)
        image = Image.open(io.BytesIO(data))
        assert image.size == size == cover_design.size_for(strategy)
    portrait = Image.open(io.BytesIO(cover_design.design(_frame(), width=1080, height=1920, title_lines=['A', 'B'], palette='mint')))
    assert portrait.getpixel((10, 10)) == portrait.getpixel((1070, 10))  # flat palette band above the photo


def test_the_cover_names_the_guest_and_follows_the_track_to_the_speaker():
    packaging = {'speakers': [{'name': 'Dwarkesh Patel', 'role': '访谈主持人'}, {'name': 'Jensen Huang', 'role': '英伟达CEO'}]}
    assert cover_design.cover_speaker(packaging) == ('Jensen Huang', '英伟达CEO')
    assert cover_design.cover_speaker({'speakers': [{'name': 'Host', 'role': 'podcast host'}]}) is None
    # A 4:3 window at the left edge (position 0) of a 1920×1080 frame is centred at 720 px.
    assert abs(cover_design.speaker_centre(0.0, 'window', 1920, 1080) - 720 / 1920) < 1e-6
    assert cover_design.speaker_centre(None, 'crop', 1920, 1080) is None


def test_the_kit_bundles_video_cover_and_copy(tmp_path):
    video, cover = tmp_path / 'v.mp4', tmp_path / 'c.jpg'
    video.write_bytes(b'mp4')
    cover.write_bytes(_frame(10, 10))
    data, name = publish_kit.kit_zip(video, cover, {'title': 'AI/还不能当实习生', 'description': '一句话', 'tags': ['AI', 'Karpathy']}, '抖音 9:16')
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert name == 'AI 还不能当实习生.zip' and names == ['AI 还不能当实习生.mp4', 'AI 还不能当实习生 封面.jpg', 'AI 还不能当实习生 发布文案.txt']
    text = zipfile.ZipFile(io.BytesIO(data)).read(names[2]).decode()
    assert '#AI #Karpathy' in text and '抖音' in text


def test_ai_cover_fit_fills_the_gap_from_the_image_edge_without_cropping():
    generated = Image.new('RGB', (1024, 1536), (20, 20, 20))
    generated.paste((240, 200, 40), (0, 300, 1024, 400))  # a headline band well inside the image
    fitted = publish_kit._fit(generated, (1080, 1920))
    assert fitted.size == (1080, 1920)
    top = fitted.getpixel((540, 20))
    assert max(top) < 40, 'the gap continues the dark edge instead of echoing the headline'
    band_y = (1920 - 1620) // 2 + round(350 * 1620 / 1536)
    assert fitted.getpixel((540, band_y))[0] > 200, 'the image itself is kept sharp, not blurred'


def test_no_ai_cover_without_permission_to_send_the_frame(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from backend.services import cover
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=False))
    frame, meta = tmp_path / 'f.jpg', tmp_path / 'm.json'
    frame.write_bytes(b'f')
    meta.write_text('{}')
    monkeypatch.setattr(publish_kit, 'frame_path', lambda *_: frame)
    monkeypatch.setattr(publish_kit, 'cd_meta_path', lambda *_: meta)
    assert publish_kit.ai_cover('p', 'j', 'tiktok') is False, 'a made-up face must never carry the guest nameplate'


def test_disk_kit_contains_the_whole_video_without_an_in_memory_archive(tmp_path, monkeypatch):
    video = tmp_path / 'long.mp4'
    video.write_bytes(b'video-data' * 100_000)
    with monkeypatch.context() as patch:
        patch.setattr(publish_kit.io, 'BytesIO', lambda: pytest.fail('HTTP kit must be built on disk'))
        path, name = publish_kit.kit_file(video, None, {'title': 'Long interview'}, 'YouTube', english=True)
    try:
        with zipfile.ZipFile(path) as archive:
            assert archive.read('Long interview.mp4') == video.read_bytes()
        assert name == 'Long interview.zip'
    finally:
        path.unlink()


def test_failed_disk_kit_removes_its_temporary_file(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_kit.tempfile, 'tempdir', str(tmp_path))
    with pytest.raises(FileNotFoundError):
        publish_kit.kit_file(tmp_path / 'missing.mp4', None, {}, 'YouTube')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('description', [
    '坦诚分享，出自【】。你怎么看？',
    '浏览器与 Sora 分散了聚焦——出自《Hard Fork》播客。',
    '团队新领导正在加入。出自节目：《》',
    'A frank discussion from the Hard Fork podcast.',
])
def test_unknown_source_cannot_ship_invented_or_empty_attribution(description):
    calls=[]
    def call(prompt, data):
        calls.append(data)
        return {'posts': {'douyin': {'title':'重新聚焦核心能力','description':description,'tags':['AI战略']}}}
    result=post_copy.build_posts('重新聚焦', ['We over-diversified on the product side.'], ['douyin'], source=' ', call=call)
    assert result['douyin']['description']=='', 'missing provenance must not become an invented programme or placeholder'
    assert result['douyin']['title']=='重新聚焦核心能力'
    assert calls[0]['source']==''


def test_unknown_source_keeps_description_without_attribution():
    def call(*_):
        return {'posts': {'douyin': {'title':'重新聚焦核心能力','description':'重新聚焦核心能力，避免目标过多。','tags':['AI战略']}}}
    assert post_copy.build_posts('重新聚焦', LINES, ['douyin'], call=call)['douyin']['description']=='重新聚焦核心能力，避免目标过多。'


@pytest.mark.parametrize(('lines', 'tags', 'expected'), [
    (['We built a browser and Sora.'], ['Meta', '扎克伯格', 'Sora'], ['Sora']),
    (['Metaphors matter. Greg and Fiji helped.'], ['Meta', 'Greg', 'Fiji'], ['Greg', 'Fiji']),
    (['Sora helps. 公司管理需要聚焦。'], ['a', 'b', 'c', 'd', 'e', 'Sora', '公司管理'], ['Sora', '公司管理']),
])
def test_unknown_source_tags_use_literal_subtitle_evidence(lines, tags, expected):
    def call(*_):
        return {'posts': {'douyin': {'title': '聚焦核心能力', 'description': '', 'tags': tags}}}
    result = post_copy.build_posts('参考标题里的 Meta 不是事实依据', lines, ['douyin'], call=call)
    assert result['douyin']['tags'] == expected
