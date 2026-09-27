"""Render the six v3 title presets with the product renderer; no model calls.

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
from PIL import Image, ImageDraw, ImageFilter

STYLES = [('comic', '漫画冲击'), ('neon', '荧光挑战'), ('arena', '竞技斜切'), ('pixel', '像素街机'), ('editorial', '极简大字'), ('frosted', '磨砂字幕卡')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-dir', type=Path, help='Reuse existing v2 comparison videos')
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
            for version in ([2, 3] if style not in ('pixel','frosted') else [3]):
                key = f'{style}-v{version}'
                if version==2 and args.baseline_dir:
                    for suffix in ('.mp4','.jpg'):
                        shutil.copy2(args.baseline_dir/f'{key}{suffix}',args.output/f'{key}{suffix}')
                    continue
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
        board = Image.new('RGB', (1080, 1408), '#111821')
        draw = ImageDraw.Draw(board)
        for i, (style, label) in enumerate(STYLES):
            zh = background.copy()
            if style=='frosted':
                from backend.services.studio.title_materials import frosted_layers,blur_sigma
                mask=frosted_layers('你能逃出\n这里吗？',1080,1920)[1]
                zh=Image.composite(background.filter(ImageFilter.GaussianBlur(blur_sigma(1080))),background,mask)
            zh.alpha_composite(title_art.artwork('你能逃出\n这里吗？', style, 1080, 1920, version=3))
            zh.convert('RGB').save(args.output/f'{style}-zh.jpg', quality=95)
            col,row=i%3,i//3
            board.paste(Image.open(args.output/f'{style}-v3.jpg').resize((360,640)),(col*360,row*704+52))
            draw.text((col*360+16,row*704+9),f'{i+1:02} {label}',font=title_art.font_for(label,26),fill='white')
            if style in ('pixel','frosted'):
                key=f'{style}-zh'
                draft=Draft(id=key,title=label,hook='你能逃出\n这里吗？',title_style=style,title_template_version=3,aspect='portrait',layout='crop',subtitles=False,scenes=[Scene(id='a',start=8,end=14),Scene(id='b',start=16,end=20)])
                result=render_draft('review',args.source,draft,key,lambda _:None)
                shutil.copy2(directory('review')/'output/studio'/f'{key}.mp4',args.output/f'{key}.mp4')
                evidence.append({'file':f'{key}.mp4','draft':draft.model_dump(),'result':result})
                print(key,result,flush=True)
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
