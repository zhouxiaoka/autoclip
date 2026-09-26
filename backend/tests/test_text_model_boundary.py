import sys
from types import SimpleNamespace
import pytest
from backend.services.studio import intelligence

@pytest.mark.parametrize('visual_configured',[False,True])
@pytest.mark.parametrize('available',[False,True])
def test_text_operations_never_fall_back_to_visual(monkeypatch,visual_configured,available):
    calls=[]
    fake=SimpleNamespace(llm_manager=SimpleNamespace(get_current_provider_info=lambda:{'available':available}),call=lambda *a:calls.append(a) or '{"title":"text result"}')
    monkeypatch.setitem(sys.modules,'backend.utils.llm_client',SimpleNamespace(LLMClient=lambda:fake))
    monkeypatch.setattr(intelligence,'ready',lambda:visual_configured)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k:pytest.fail('implicit visual fallback'))
    if available:
        assert intelligence.text_json('rewrite',{'title':'source'})=={'title':'text result'}
        assert len(calls)==1
    else:
        with pytest.raises(ValueError,match='文字模型不可用'):
            intelligence.text_json('translate',{'subtitles':['source']})
        assert not calls


def test_text_provider_error_does_not_retry_with_visual(monkeypatch):
    def fail(*a):raise RuntimeError('text provider failed')
    monkeypatch.setitem(sys.modules,'backend.utils.llm_client',SimpleNamespace(LLMClient=lambda:SimpleNamespace(llm_manager=SimpleNamespace(get_current_provider_info=lambda:{'available':True}),call=fail)))
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k:pytest.fail('implicit retry'))
    with pytest.raises(RuntimeError,match='text provider failed'):
        intelligence.text_json('rewrite',{})
