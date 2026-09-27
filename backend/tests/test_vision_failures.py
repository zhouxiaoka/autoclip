"""Safe, durable vision diagnostics; all HTTP responses are local test doubles."""
import io
import json
import urllib.error
from http.client import IncompleteRead
from pathlib import Path

import pytest
from backend.services.studio import intelligence as vision
from backend.services.studio import planning
from backend.services.studio.models import ImportOptions

CONFIG = {'base_url':'https://example.test/private-url', 'model':'vision', 'api_key':'private-key', 'timeout':10}


def invoke(monkeypatch, response=None, error=None):
    calls=[]
    def send(*args, **kwargs):
        calls.append(1)
        if error is not None: raise error
        return io.BytesIO(response if isinstance(response,bytes) else json.dumps(response).encode())
    monkeypatch.setattr(vision.urllib.request,'urlopen',send)
    ticks=iter([100,102.5])
    monkeypatch.setattr(vision.time,'monotonic',lambda:next(ticks))
    with pytest.raises(vision.VisionRequestError) as caught:
        vision.vision_call([{'type':'text','text':'private-prompt'}],config=CONFIG)
    assert calls==[1]
    diagnostic=caught.value.diagnostics()
    assert diagnostic['elapsed_seconds']==2.5
    exposed=str(caught.value)+json.dumps(diagnostic)
    assert 'private-' not in exposed and 'example.test' not in exposed
    return caught.value


@pytest.mark.parametrize('error,code',[
    (TimeoutError('private-timeout'),'timeout'),
    (urllib.error.URLError(TimeoutError('private-nested-timeout')),'timeout'),
    (urllib.error.URLError('private-network'),'connection'),
    (ConnectionResetError('private-reset'),'connection'),
    (IncompleteRead(b'private-response',100),'connection'),
])
def test_network_failures_have_stable_safe_codes(monkeypatch,error,code):
    assert invoke(monkeypatch,error=error).code==code


@pytest.mark.parametrize('status,code',[(401,'authentication'),(403,'authentication'),(429,'rate_limited'),(500,'provider_error')])
def test_http_body_and_request_details_are_never_exposed(monkeypatch,status,code):
    body=io.BytesIO(b'private-key and private-provider-body')
    error=urllib.error.HTTPError(CONFIG['base_url'],status,'private-message',{},body)
    failure=invoke(monkeypatch,error=error)
    assert failure.code==code and failure.diagnostics()['http_status']==status
    assert body.closed


@pytest.mark.parametrize('response',[
    b'private-non-json', {}, {'choices':[]},
    {'choices':[{'message':{'content':'private-json'}}]},
    {'choices':[{'message':{'content':None}}]},
    {'choices':[{'message':{'content':'[]'}}]},
    {'choices':[{'message':{'content':{'private-key':'value'}}}]},
])
def test_invalid_provider_envelopes_are_actionable_and_do_not_leak(monkeypatch,response):
    assert invoke(monkeypatch,response=response).code=='invalid_response'


@pytest.mark.parametrize('reason,code',[('length','output_truncated'),('content_filter','refused')])
def test_incomplete_results_are_not_accepted_even_when_json_parses(monkeypatch,reason,code):
    response={'choices':[{'finish_reason':reason,'message':{'content':'{}'}}]}
    assert invoke(monkeypatch,response=response).code==code


def test_refusal_and_valid_fenced_json(monkeypatch):
    assert invoke(monkeypatch,response={'choices':[{'message':{'refusal':'private-content','content':None}}]}).code=='refused'
    monkeypatch.setattr(vision.time,'monotonic',lambda:1)
    monkeypatch.setattr(vision.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(json.dumps({'choices':[{'message':{'content':'```json\n{"events": []}\n```'}}]}).encode()))
    assert vision.vision_call([],config=CONFIG)=={'events':[]}


def test_stage_annotation_and_quick_fallback_preserve_diagnostics(monkeypatch):
    def fail(*a,**k):raise vision.VisionRequestError('timeout','模型超时',elapsed_seconds=30)
    monkeypatch.setattr(vision,'vision_call',fail)
    with pytest.raises(vision.VisionRequestError) as caught:vision.vision_call_at('refine',[])
    assert caught.value.diagnostics()['phase']=='refine'
    monkeypatch.setattr(vision,'ready',lambda:True)
    monkeypatch.setattr(vision,'_probe',lambda _: {'duration':20})
    monkeypatch.setattr(vision,'sample',lambda *a,**k:[])
    plan=planning.recommend(Path('unused'),ImportOptions())
    assert plan['mode']=='fallback' and plan['suggested_goals']==[]
    assert plan['diagnostics']=={'code':'timeout','phase':'screening','elapsed_seconds':30}
