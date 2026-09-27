import base64, json, urllib.request, urllib.error
from pathlib import Path

here = Path(__file__).parent
config = {}
for line in Path('/Users/zhoukk/autoclip/.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k, v = line.split('=', 1)
        config[k.strip()] = v.strip().strip('\"\'')
content = [{'type':'text','text': '你是游戏买量视频创意审片员。以下是同一段22秒连续跑酷视频按顺序每2秒采样的11张画面（采样约1、3、5…21秒）。只根据画面，输出中文JSON：observed_gameplay，events（approx_seconds、evidence），crop_review（原视频1920x1080，计划居中裁切到926x1080：玩家、三条跑道、前方障碍是否完整，有风险需说明），hook_review（评估“连续避障”“下一步往哪躲？”“你能坚持到最后吗？”是否忠于内容），limitations。不要编造输赢、CTR、投放效果，不可依据抽帧判断帧间动作细节。'}]
for p in sorted((here/'seed-frames').glob('*.jpg')):
    content.append({'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode()}})
payload={'model':'doubao-seed-2-1-pro-260915','messages':[{'role':'user','content':content}],'max_tokens':2000,'thinking':{'type':'disabled'}}
req=urllib.request.Request(config['SEEDANCE_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+config['SEEDANCE_API_KEY'],'Content-Type':'application/json'})
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        data=json.load(r)
    out={'model':data.get('model'),'usage':data.get('usage'),'review':data['choices'][0]['message']['content'],'sampling':'11 ordered stills, every 2 seconds; not full-motion video analysis'}
    (here/'seed-review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps(out,ensure_ascii=False,indent=2))
except urllib.error.HTTPError as e:
    message=e.read().decode()[:2000].replace(config['SEEDANCE_API_KEY'],'[REDACTED]')
    print('API error', e.code, message)
    raise SystemExit(1)
