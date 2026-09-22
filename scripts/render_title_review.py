"""Render the four v2 title presets with the product renderer; no model calls.

Usage: python scripts/render_title_review.py --source gameplay.mp4 --output /tmp/title-review
The sample must contain the 8–14s and 16–20s ranges used for this visual comparison.
"""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw

STYLES = [('comic', '漫画冲击'), ('neon', '荧光挑战'), ('arena', '竞技斜切'), ('editorial', '极简大字')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path, help='Optional original design board')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='autoclip-title-review-') as data:
        os.environ['AUTOCLIP_DATA_DIR'] = data
        from backend.services.studio.models import Draft, Scene
        from backend.services.studio.render import render_draft
        from backend.services.studio.store import directory
        from backend.services.studio import title_art
        from backend.utils.ffmpeg_utils import get_ffmpeg_path
        directory('review').mkdir(parents=True)
        evidence = []
        for style, label in STYLES:
            for version in ([1, 2] if style != 'editorial' else [2]):
                key = f'{style}-v{version}'
                draft = Draft(id=key, title=label, hook='CAN YOU\nESCAPE?', title_style=style,
                    title_template_version=version, aspect='portrait', layout='crop', subtitles=False,
                    scenes=[Scene(id='a', start=8, end=14), Scene(id='b', start=16, end=20)])
                result = render_draft('review', args.source, draft, key, lambda _: None)
                video = args.output / f'{key}.mp4'
                shutil.copy2(directory('review') / 'output/studio' / video.name, video)
                subprocess.run([get_ffmpeg_path(), '-v', 'error', '-ss', '1', '-i', str(video), '-frames:v', '1', '-y', str(args.output/f'{key}.jpg')], check=True)
                evidence.append({'file': video.name, 'draft': draft.model_dump(), 'result': result})
                print(key, result, flush=True)
        # Chinese is a static layout preview, explicitly labeled in the review UI.
        frame = subprocess.check_output([get_ffmpeg_path(), '-v', 'error', '-ss', '9', '-i', str(args.source), '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920', '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'])
        background = Image.open(io.BytesIO(frame)).convert('RGBA')
        board = Image.new('RGB', (1440, 1424), '#111821')
        draw = ImageDraw.Draw(board)
        for i, (style, label) in enumerate(STYLES):
            zh = background.copy()
            zh.alpha_composite(title_art.artwork('你能逃出\n这里吗？', style, 1080, 1920, version=2))
            zh.convert('RGB').save(args.output/f'{style}-zh.jpg', quality=95)
            for row, path in enumerate([args.output/f'{style}-v2.jpg', args.output/f'{style}-zh.jpg']):
                board.paste(Image.open(path).resize((360, 640)), (i*360, row*712+52))
                draw.text((i*360+16,row*712+9), f'{i+1:02} {label}', font=title_art.font_for(label,26), fill='white')
        board.save(args.output/'contact.jpg', quality=94)
        (args.output/'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    page = Path(__file__).with_name('title_review.html').read_text()
    if args.reference:
        shutil.copy2(args.reference, args.output/'design-reference.png')
    else:
        start = page.index('<details>')
        end = page.index('</details>', start)+len('</details>')
        page = page[:start]+page[end:]
    (args.output/'index.html').write_text(page)
    print(args.output/'index.html')


if __name__ == '__main__':
    main()
