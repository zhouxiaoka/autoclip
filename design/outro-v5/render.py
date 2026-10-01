from pathlib import Path
import math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parent
DURATION=1.8
FPS=60
logo=Image.open(ROOT/'logo.png').convert('RGBA').crop((104,104,920,920))
def clamp(x): return max(0,min(1,x))
def smooth(x):
    x=clamp(x)
    return x*x*x*(x*(x*6-15)+10)
def spring(t):
    # Continuous damped response, settling without a hard stop.
    return 1-math.exp(-10*max(0,t))*(math.cos(17*max(0,t))+.45*math.sin(17*max(0,t)))
def opacity(im,a):
    im=im.copy(); im.putalpha(im.getchannel('A').point(lambda p:int(p*clamp(a))))
    return im
def frame(t,W,H):
    u=min(W/1080,H/1080); cx,cy=W/2,H/2-105*u
    im=Image.new('RGBA',(W,H),(8,8,9,255))
    # One neutral pool of light; no colored fringing.
    aura=Image.new('RGBA',(W,H)); ad=ImageDraw.Draw(aura)
    r=200*u
    ad.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(255,255,255,int(13*smooth(t/.6))))
    im=Image.alpha_composite(im,aura.filter(ImageFilter.GaussianBlur(140*u)))
    # V1's full-screen cut motion, rebuilt as one silver light blade.
    if t<.54:
        p=smooth((t-.015)/.45)
        tip=-W*.34+p*W*1.75
        trail=Image.new('RGBA',(W,H)); td=ImageDraw.Draw(trail)
        fade=smooth(t/.06)*(1-smooth((t-.37)/.17))
        for j in range(32):
            x=tip-j*4*u
            alpha=int(200*fade*(1-j/32)**2)
            td.line((x+H*.21,0,x-H*.21,H),fill=(245,245,245,alpha),width=max(1,int(3*u)))
        # Needle-sharp leading edge with a broad, soft monochrome wake.
        im=Image.alpha_composite(im,trail.filter(ImageFilter.GaussianBlur(20*u)))
        im=Image.alpha_composite(im,trail)
    if t>.15:
        a=smooth((t-.15)/.15)
        response=spring(t-.15)
        scale=.66+.34*response
        size=max(1,int(292*u*scale))
        mark=logo.resize((size,size),Image.Resampling.LANCZOS)
        # One continuous split-and-join, without randomized glitch flicker.
        split=22*u*(1-smooth((t-.19)/.23))
        if split>.2:
            joined=Image.new('RGBA',(size+int(split)*2+4,size))
            pad=int(split)+2
            mid=int(size*.55)
            joined.alpha_composite(mark.crop((0,0,size,mid)),(pad+int(split),0))
            joined.alpha_composite(mark.crop((0,mid,size,size)),(pad-int(split),mid))
            mark=joined
        # Small rotation and vertical drift share the same smooth spring curve.
        mark=mark.rotate(-9*(1-response),Image.Resampling.BICUBIC,expand=True)
        mark=opacity(mark,a)
        blur=5*u*(1-smooth((t-.15)/.18))
        if blur>.2: mark=mark.filter(ImageFilter.GaussianBlur(blur))
        y=cy+62*u*(1-response)
        im.alpha_composite(mark,(round(cx-mark.width/2),round(y-mark.height/2)))
        # Restrained surface gleam synchronized to the audible ding.
        if .44<t<.73:
            p=smooth((t-.44)/.29)
            n=int(292*u); shine=Image.new('RGBA',(n,n)); sd=ImageDraw.Draw(shine)
            x=-n*.4+p*n*1.8
            sd.polygon([(x,0),(x+60*u,0),(x-n*.27+60*u,n),(x-n*.27,n)],fill=(255,255,255,48))
            mask=logo.resize((n,n),Image.Resampling.LANCZOS).getchannel('A')
            shine.putalpha(Image.fromarray((np.array(shine.getchannel('A')).astype(float)*np.array(mask)/255).astype('uint8')))
            im.alpha_composite(shine,(round(cx-n/2),round(cy-n/2)))
    # Staggered glyph drift creates a soft cascading reveal with preserved kerning.
    f=ImageFont.truetype(str(ROOT/'InstrumentSerif.ttf'),int(112*u))
    text='AutoClip'; total=f.getlength(text); left=cx-total/2
    letters=Image.new('RGBA',(W,H)); ld=ImageDraw.Draw(letters)
    for i,char in enumerate(text):
        p=smooth((t-(.36+i*.018))/.27)
        x=left+f.getlength(text[:i])
        ld.text((x,cy+173*u+22*u*(1-p)),char,font=f,fill=(250,249,246,int(255*p)))
    im=Image.alpha_composite(im,letters)
    a=smooth((t-.65)/.28)
    if a>0:
        layer=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(layer)
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',int(28*u))
        label='Made with AutoClip'
        tw=d.textlength(label,font=font)
        d.text((cx-tw/2,cy+365*u+6*u*(1-a)),label,font=font,fill=(220,220,222,int(255*a)))
        im=Image.alpha_composite(im,layer)
    return im.convert('RGB')

def sound():
    sr=48000; t=np.arange(round(DURATION*sr))/sr; rng=np.random.default_rng(19)
    noise=rng.normal(0,1,len(t))
    soft=np.convolve(noise,np.ones(12)/12,mode='same')
    # Airy low-level swoosh and a tiny soft tactile landing.
    air=soft*.25*np.exp(-((t-.23)/.08)**2)
    a=np.maximum(0,t-.39)
    tap=(np.sin(2*np.pi*(135*a-35*a*a))*.15*np.exp(-a*28)+soft*.05*np.exp(-a*75))*(t>=.39)
    # Bell: clean fundamental, delicately inharmonic partials, fast rounded attack.
    b=np.maximum(0,t-.86); attack=1-np.exp(-b*1000)
    bell=np.zeros_like(t)
    for hz,amp,decay in [(1568,.27,3.9),(3136,.075,6.5),(4240,.032,9),(6272,.009,13)]:
        bell+=amp*np.sin(2*np.pi*hz*b)*np.exp(-b*decay)
    bell*=attack*(t>=.86)
    # Slight stereo depth without a detached echo; tail gently reaches silence.
    dry=air+tap+bell
    delay=np.zeros_like(dry); offset=round(.012*sr); delay[offset:]=bell[:-offset]*.11
    end=1-smooth_array((t-1.65)/.15)
    stereo=np.column_stack((dry+delay,dry*.98+np.roll(delay,120)))*end[:,None]
    with wave.open(str(ROOT/'sound.wav'),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr)
        w.writeframes((np.clip(stereo,-.95,.95)*32767).astype('<i2').tobytes())
def smooth_array(x):
    x=np.clip(x,0,1);return x*x*x*(x*(x*6-15)+10)
def render(W,H,name):
    cmd=['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i',str(ROOT/'sound.wav'),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(DURATION),'-movflags','+faststart',str(ROOT/name)]
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for n in range(round(FPS*DURATION)):p.stdin.write(frame(n/FPS,W,H).tobytes())
    p.stdin.close()
    if p.wait():raise RuntimeError('Encoding failed')
    print(name,flush=True)
if __name__=='__main__':
    sound()
    render(1080,1920,'AutoClip-Outro-v5-Vertical.mp4')
    render(1920,1080,'AutoClip-Outro-v5-Horizontal.mp4')
    frame(1.3,1080,1920).save(ROOT/'poster.jpg',quality=94)
