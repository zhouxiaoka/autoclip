"""Black-box installed backend acceptance with a loopback OpenAI protocol fixture.

This tests provider persistence and the Studio import/render path, not LLM
editorial quality. It makes no external model requests and requires no API key.
"""
import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def run(base, root, resources, source_video, source_srt):
    import requests
    from backend.utils.text_processor import TextProcessor
    from backend.pipeline.quality import to_seconds, to_srt_time
    import backend
    assert Path(backend.__file__).resolve().is_relative_to(resources / 'backend'), 'development backend imported'
    calls = []

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_json(self, data):
            raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.send_json({'object':'list','data':[{'id':'installed-smoke-model','object':'model'}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            text = body['messages'][-1]['content']
            data = None
            if '\n\n输入内容：\n' in text:
                data = json.loads(text.rsplit('\n\n输入内容：\n', 1)[1])
            if isinstance(data, dict) and 'srt_text' in data:
                stage = 'timeline'
                content = [{'outline':row['title'],'start_time':'00:00:00,000',
                            'end_time':'00:00:40,000','content':'Public interview excerpt'} for row in data['outline']]
            elif isinstance(data, dict) and 'text' in data:
                stage = 'outline'
                content = '1. **Public interview**\n   - Public speech excerpt'
            elif isinstance(data, list) and data and 'outline' in data[0]:
                stage = 'score'
                content = [{'id':row.get('id'),'outline':row['outline'],'final_score':0.9,
                            'recommend_reason':'Deterministic protocol fixture, not a quality judgement'} for row in data]
            elif isinstance(data, list) and data and 'title' in data[0]:
                stage = 'title'
                content = {str(row['id']):'Installed Windows sample' for row in data}
            elif '视频切片列表' in text:
                stage, content = 'collections', []
            else:
                stage, content = 'connection', 'OK'
            calls.append(stage)
            self.send_json({'id':'installed-smoke','object':'chat.completion','model':'installed-smoke-model',
                            'choices':[{'index':0,'message':{'role':'assistant','content':content if isinstance(content,str) else json.dumps(content)},'finish_reason':'stop'}],
                            'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}})

    server = ThreadingHTTPServer(('127.0.0.1',0),Fixture)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        connection = {'id':'installed-smoke','name':'Loopback acceptance fixture','provider':'compatible',
                      'base_url':f'http://127.0.0.1:{server.server_port}/v1','api_key':''}
        config = {'version':1,'connections':[connection],
                  'analysis':{'connection_id':connection['id'],'model':'installed-smoke-model','capability':'text'},
                  'analysis_mode':'subtitle','cover_enabled':False,'allow_send_frame':False}
        headers = {'Origin':'http://tauri.localhost'}
        saved = requests.put(base+'/api/v1/settings/ai-models',json=config,headers=headers,timeout=20)
        if saved.status_code == 404:
            # Existing release/build artifacts predate named model connections.
            # Exercise their real settings API rather than patching installed code.
            settings = requests.get(base+'/api/v1/settings/',timeout=20)
            settings.raise_for_status()
            legacy = settings.json()
            legacy['api'].update(api_provider='openai',api_base_url=connection['base_url'],api_model='installed-smoke-model')
            legacy['api']['api_keys']['openai']=''
            saved = requests.put(base+'/api/v1/settings/',json=legacy,headers=headers,timeout=20)
            saved.raise_for_status()
            persisted = requests.get(base+'/api/v1/settings/',timeout=20).json()
            assert persisted['api']['api_provider']=='openai', persisted
            assert persisted['api']['api_model']=='installed-smoke-model', persisted
            assert persisted['api']['api_base_url']==connection['base_url'], persisted
            test = requests.post(base+'/api/v1/settings/test-api',json={'provider':'openai','base_url':connection['base_url'],
                                 'api_key':'','model':'installed-smoke-model'},headers=headers,timeout=30)
            settings_api, success_field = 'legacy settings', 'success'
        else:
            saved.raise_for_status()
            persisted = requests.get(base+'/api/v1/settings/ai-models',timeout=20).json()
            assert persisted['analysis']['model']=='installed-smoke-model', persisted
            assert persisted['connections'][0]['base_url']==connection['base_url'], persisted
            test = requests.post(base+'/api/v1/settings/ai-models/test',json={'connection':connection,'model':'installed-smoke-model'},headers=headers,timeout=30)
            settings_api, success_field = 'named connections', 'success'
        test.raise_for_status()
        assert test.json()[success_field], test.text

        video = root/'公开访谈 45秒.mp4'
        ffmpeg = resources/'ffmpeg'/'ffmpeg.exe'
        subprocess.run([str(ffmpeg),'-v','error','-i',str(source_video),'-t','45','-c','copy',str(video)],check=True,timeout=60)
        entries = [e for e in TextProcessor.parse_srt(source_srt) if to_seconds(e['start_time'])<45]
        assert entries
        subtitle = root/'公开访谈 45秒.srt'
        subtitle.write_text('\n'.join(f"{i}\n{e['start_time']} --> {to_srt_time(min(45,to_seconds(e['end_time'])))}\n{e['text']}\n"
                                      for i,e in enumerate(entries,1)),encoding='utf-8')
        with video.open('rb') as v, subtitle.open('rb') as s:
            uploaded = requests.post(base+'/api/v1/studio/import',
                                     data={'name':'Installed Windows real video','auto_start':'true','platforms':'douyin'},
                                     files={'video':(video.name,v,'video/mp4'),'subtitle':(subtitle.name,s,'application/x-subrip')},
                                     headers=headers,timeout=120)
        uploaded.raise_for_status()
        pid = uploaded.json()['project_id']
        deadline = time.monotonic()+180
        workspace = None
        body = ''
        while time.monotonic()<deadline:
            response=requests.get(base+f'/api/v1/studio/{pid}',timeout=20)
            body=response.text
            response.raise_for_status()
            workspace=response.json()
            status=(workspace.get('generation') or {}).get('status')
            if status in ('completed','partial','failed'):
                break
            time.sleep(1)
        assert workspace and (workspace.get('generation') or {}).get('status') in ('completed','partial'), body
        from backend.services.studio import store
        project_dir = store.directory(pid)
        files=[]
        for job in workspace.get('jobs') or []:
            if job.get('status')!='completed' or not job.get('job_id'):
                continue
            files.append(project_dir/'output'/'studio'/f"{job['job_id']}.mp4")
        assert files and all(p.is_file() and p.stat().st_size>0 for p in files), body
        probes=[]
        for path in files:
            info=json.loads(subprocess.check_output([str(resources/'ffmpeg'/'ffprobe.exe'),'-v','error','-show_streams','-show_format','-of','json',str(path)],encoding='utf-8'))
            streams=info['streams']
            assert next(s for s in streams if s['codec_type']=='video')['codec_name']=='h264', info
            assert next(s for s in streams if s['codec_type']=='audio')['codec_name']=='aac', info
            assert float(info['format']['duration'])>=20, info
            probes.append({'bytes':path.stat().st_size,'duration_sec':float(info['format']['duration']),'video':'h264','audio':'aac'})
        assert {'connection','outline','timeline','score','title'} <= set(calls), calls
        generation_status = (workspace.get('generation') or {}).get('status')
        return {'status':'passed','settings_api':settings_api,'provider_saved':True,'provider_connection':'passed',
                'generation_status':generation_status,'output_count':len(probes),'outputs':probes,'fixture_stages':calls,
                'input':'repository public interview, first 45 seconds, supplied real SRT',
                'model_mode':'loopback OpenAI protocol fixture; no real model-quality claim or paid call'}
    finally:
        server.shutdown()
        server.server_close()
