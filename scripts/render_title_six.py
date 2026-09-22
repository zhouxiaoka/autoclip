"""Render first-release six-preset review using production FFmpeg, without model calls."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw

STYLES=[('comic','漫画冲击'),('neon','荧光挑战'),('arena','竞技斜切'),('pixel','像素街机'),('editorial','极简大字'),('frosted','磨砂字幕卡')]
CROPS=[(36,89,362,691),(382,89,705,691),(724,89,1050,691),(36,754,362,1357),(382,754,705,1357),(724,754,1050,1357)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','reference','baseline','comic-baseline','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--styles',nargs='+',choices=[s[0] for s in STYLES],default=[s[0] for s in STYLES])
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    ref=Image.open(args.reference)
    shutil.copy2(args.reference,out/'design-reference.png')
    with tempfile.TemporaryDirectory(prefix='autoclip-six-review-') as data:
        os.environ['AUTOCLIP_DATA_DIR']=data
        from backend.services.studio.models import Draft,Scene
        from backend.services.studio.render import render_draft
        from backend.services.studio.store import directory
        from backend.services.studio.title_art import font_for
        from backend.utils.ffmpeg_utils import get_ffmpeg_path
        directory('review').mkdir(parents=True)
        prior=json.loads((out/'evidence.json').read_text()) if (out/'evidence.json').exists() else []
        evidence=[e for e in prior if e['draft']['title_style'] not in args.styles]
        board=Image.new('RGB',(1200,1170),'#111821');d=ImageDraw.Draw(board)
        for i,(style,label) in enumerate(STYLES):
            for lang,hook in [('en','CAN YOU\nESCAPE?'),('zh','你能逃出\n这里吗？')]:
                key=f'{style}-{lang}'
                if style not in args.styles:continue
                draft=Draft(id=key,title=label,hook=hook,title_style=style,title_template_version=6,aspect='portrait',layout='crop',subtitles=False,scenes=[Scene(id='a',start=8,end=14),Scene(id='b',start=16,end=20)])
                result=render_draft('review',args.source,draft,key,lambda _:None)
                video=out/f'{key}.mp4';shutil.copy2(directory('review')/'output/studio'/video.name,video)
                subprocess.run([get_ffmpeg_path(),'-v','error','-ss','1','-i',str(video),'-frames:v','1','-y',str(out/f'{key}.jpg')],check=True)
                evidence.append({'file':video.name,'draft':draft.model_dump(),'result':result})
                print(key,result,flush=True)
            previous=args.comic_baseline/'comic-v5' if style=='comic' else args.baseline/f'{style}-v3'
            for suffix in ['.mp4','.jpg']:shutil.copy2(str(previous)+suffix,out/f'{style}-old{suffix}')
            panel=ref.crop(CROPS[i]);panel.save(out/f'{style}-reference.jpg',quality=95)
            comparison=Image.new('RGB',(1500,520),'#111821');cd=ImageDraw.Draw(comparison)
            for col,name in enumerate(['设计参考','已确认漫画' if style=='comic' else '上一轮','本轮优化']):
                cd.text((col*500+16,12),name,font=font_for(name,28),fill='white')
            comparison.paste(panel.crop((0,0,panel.width,round(panel.width*.86))).resize((480,413)),(10,65))
            for col,key in [(1,'old'),(2,'en')]:
                image=Image.open(out/f'{style}-{key}.jpg')
                comparison.paste(image.crop((0,0,1080,929)).resize((480,413)),(col*500+10,65))
            comparison.save(out/f'{style}-comparison.jpg',quality=95)
            x=(i%3)*400;y=(i//3)*585
            d.text((x+15,y+10),f'{i+1:02} {label}',font=font_for(label,27),fill='white')
            frame=Image.open(out/f'{style}-en.jpg').crop((0,0,1080,1450)).resize((390,524))
            board.paste(frame,(x+5,y+51))
        board.save(out/'contact.jpg',quality=95)
        (out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    shutil.copy2(Path(__file__).with_name('title_six_review.html'),out/'index.html')
    print(out/'index.html',flush=True)

if __name__=='__main__':main()
