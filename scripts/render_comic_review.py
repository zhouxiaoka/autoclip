"""Reproducible comparison of the design reference, previous version and comic calibration."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--version',type=int,choices=[4,5],default=4)
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    version=args.version;previous=version-1
    with tempfile.TemporaryDirectory(prefix='comic-v4-') as data:
        os.environ['AUTOCLIP_DATA_DIR']=data
        from backend.services.studio.models import Draft,Scene
        from backend.services.studio.render import render_draft
        from backend.services.studio.store import directory
        from backend.services.studio.title_art import font_for
        from backend.utils.ffmpeg_utils import get_ffmpeg_path
        directory('review').mkdir(parents=True)
        evidence=[]
        for key,hook in [(f'comic-v{version}','CAN YOU\nESCAPE?'),('comic-zh','你能逃出\n这里吗？')]:
            draft=Draft(id=key,title=key,hook=hook,title_style='comic',title_template_version=version,
                        aspect='portrait',layout='crop',subtitles=False,
                        scenes=[Scene(id='a',start=8,end=14),Scene(id='b',start=16,end=20)])
            result=render_draft('review',args.source,draft,key,lambda _:None)
            shutil.copy2(directory('review')/'output/studio'/f'{key}.mp4',out/f'{key}.mp4')
            subprocess.run([get_ffmpeg_path(),'-v','error','-ss','1','-i',str(out/f'{key}.mp4'),'-frames:v','1','-y',str(out/f'{key}.jpg')],check=True)
            evidence.append({'file':f'{key}.mp4','draft':draft.model_dump(),'result':result})
            print(key,result,flush=True)
        for suffix in ['.mp4','.jpg']:shutil.copy2(args.baseline/f'comic-v{previous}{suffix}',out/f'comic-v{previous}{suffix}')
        ref=Image.open(args.reference)
        ref.crop((36,89,362,691)).save(out/'reference.jpg')
        board=Image.new('RGB',(1500,510),'#1a1d23');d=ImageDraw.Draw(board)
        for i,label in enumerate(['设计参考',f'上一轮 v{previous}',f'本轮 v{version}']):
            d.text((i*500+20,15),label,font=font_for(label,28),fill='white')
        board.paste(ref.crop((36,89,362,356)).resize((480,393)),(10,60))
        for i,v in enumerate([previous,version],1):
            im=Image.open(out/f'comic-v{v}.jpg')
            board.paste(im.crop((0,0,1080,885)).resize((480,393)),(i*500+10,60))
        board.save(out/'comparison.jpg',quality=95)
        (out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    page = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>漫画冲击 · 设计校准</title><style>body{margin:0;background:#10141b;color:#f5f5f5;font:16px system-ui;padding:28px;max-width:1400px;margin:auto}h1{font-size:28px;margin:0 0 12px}p{color:#aeb9c9;line-height:1.65}.board{width:100%;border-radius:16px}section{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:25px}article{background:#1c2330;padding:15px;border-radius:16px}video,.ref{width:100%;max-height:620px;object-fit:contain;background:#10141b}button,a{background:#2e3b51;color:white;border:0;padding:10px 16px;border-radius:9px;cursor:pointer;text-decoration:none}button[aria-pressed=true]{background:#ffdf39;color:#161a20}nav{display:flex;gap:10px;margin:15px 0}small{display:block;line-height:1.6;color:#aeb9c9}@media(max-width:800px){section{grid-template-columns:1fr}}</style><h1>漫画冲击 · 设计校准 v4</h1><p>先对齐一款：更换字形、压紧高宽比例、调整倾斜与硬描边，去掉金属反光条。下面为产品渲染器实际输出，设计图仍作为参考，等待逐项确认。</p><img class="board" src="comparison.jpg" alt="设计图、上一轮和本轮放大对比"><nav><button id="en" aria-pressed="true">英文</button><button id="zh" aria-pressed="false">中文</button><button id="sync">重播两版</button><a id="download" href="comic-v4.mp4" download>下载本轮样片</a></nav><section><article><h2>设计参考</h2><img class="ref" src="reference.jpg"><small>原始 AI 设计图；不是可直接替换文案的字体模板。</small></article><article><h2>上一轮 v3</h2><video id="old" controls playsinline loop preload="metadata" poster="comic-v3.jpg" src="comic-v3.mp4"></video></article><article><h2>本轮 v4</h2><video id="now" controls playsinline loop preload="metadata" poster="comic-v4.jpg" src="comic-v4.mp4"></video><small>10 秒 · 1080 × 1920 · 保留游戏原声。中文使用内置中文字体回退。</small></article></section><p>字幕动效进度：已接本地 Whisper 词级时间及失效校验；本页演示标题样式，不是卡拉 OK 成片。后续接镜头重排后的时间映射、逐词高亮及逐字扫色。</p><script>const old=document.querySelector('#old'),now=document.querySelector('#now');for(const lang of ['en','zh'])document.querySelector('#'+lang).onclick=()=>{now.pause();now.src=lang==='en'?'comic-v4.mp4':'comic-zh.mp4';now.poster=lang==='en'?'comic-v4.jpg':'comic-zh.jpg';document.querySelector('#download').href=now.getAttribute('src');for(const l of ['en','zh'])document.querySelector('#'+l).setAttribute('aria-pressed',String(l===lang))};document.querySelector('#sync').onclick=()=>{for(const v of [old,now]){v.currentTime=0;v.muted=true;v.play().catch(()=>{})}};</script></html>'''
    if version == 5:
        page=page.replace('v4','NEW_VERSION').replace('v3','v4').replace('NEW_VERSION','v5')
        page=page.replace('更换字形、压紧高宽比例、调整倾斜与硬描边，去掉金属反光条。','保留校准字形，突出第二行、压紧行距、增强整体倾斜和两侧爆点。')
    (out/'index.html').write_text(page)
    print(out/'index.html')

if __name__=='__main__':main()
