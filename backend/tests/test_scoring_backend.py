"""Scoring protocol, real prompt contracts and identity alignment regressions."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.pipeline.scoring_backend import LLMScoringBackend
from backend.pipeline.step3_scoring import ClipScorer, run_step3_scoring
from backend.pipeline.quality import align_scores, save_profile, profile_for


def test_every_category_uses_score_contract_and_preserves_input_ids():
    paths = list(Path('backend/prompt').glob('*/推荐理由.txt'))
    assert paths
    for path in paths:
        calls = []
        client = SimpleNamespace(call_with_retry=lambda prompt, data: calls.append((prompt, data)) or '[{"id":"8","final_score":0.8}]',
                                 parse_json_response=json.loads)
        result = LLMScoringBackend(client, path.read_text()).score([{'id':'8', 'outline':'topic', 'transcript':'spoken words'}])
        assert result[0]['final_score'] == .8
        assert '覆盖上文输入/输出示例' in calls[0][0]
        assert '"final_score":0.8' in calls[0][0]
        assert calls[0][1][0]['id'] == '8'


def test_reordered_scores_do_not_change_clip_identity():
    clips = [{'id':'1','outline':'first'}, {'id':'2','outline':'second'}]
    scores = [{'id':'2','outline':'second','final_score':.9}, {'id':'1','outline':'first','final_score':.2}]
    output, stats = align_scores(clips, scores)
    assert [c['final_score'] for c in output] == [.2,.9]
    assert stats == {'matched':2,'fallback':0}


def test_long_outline_identity_and_unknown_named_result():
    title = 'long topic ' * 20
    clips = [{'outline': title}, {'outline':'unreturned'}]
    output, stats = align_scores(clips, [{'outline':'unrelated','final_score':.99}, {'outline': title,'final_score':.75}])
    assert [c['final_score'] for c in output] == [.75,.5]
    assert stats['fallback'] == 1


@pytest.mark.parametrize('value', [float('nan'),float('inf'),-1,101,True,'NaN'])
def test_non_finite_or_invalid_scores_are_fallback(value):
    output, stats = align_scores([{'id':'1'}],[{'id':'1','final_score':value}])
    assert output[0]['final_score'] == .5
    assert stats['fallback'] == 1


def test_duplicate_result_id_is_ambiguous():
    output, stats = align_scores([{'id':'1'}], [{'id':'1','final_score':.1},{'id':'1','final_score':.9}])
    assert stats['fallback'] == 1


def test_custom_backend_runs_actual_step3_without_creating_llm_client(monkeypatch, tmp_path):
    from backend.pipeline import step3_scoring
    def forbidden(): raise AssertionError('custom backend must not initialize LLM client')
    monkeypatch.setattr(step3_scoring, 'LLMClient', forbidden)
    monkeypatch.setattr(step3_scoring, 'resolve_min_score_threshold',lambda:.7)
    chunk_dir = tmp_path/'step1_srt_chunks';chunk_dir.mkdir()
    (chunk_dir/'chunk_0.json').write_text(json.dumps([{'start_time':'00:00:00,000','end_time':'00:00:30,000','text':'actual excerpt'}]))
    clips = [{'id':'1','chunk_index':0,'outline':'one','start_time':'00:00:00,000','end_time':'00:00:30,000'}]
    timeline = tmp_path/'timeline.json';timeline.write_text(json.dumps(clips))
    save_profile(profile_for(90),tmp_path)
    calls=[]
    class CustomBackend:
        def score(self, inputs):
            calls.extend(inputs)
            return [{'id':'1','final_score':.85,'recommend_reason':'supported by transcript'}]
    output = run_step3_scoring(timeline,metadata_dir=tmp_path,scoring_backend=CustomBackend())
    assert output[0]['final_score'] == .85 and output[0]['selected_by'] == 'threshold'
    assert output[0]['score_source'] == 'backend'
    assert calls[0]['id'] == '1' and calls[0]['transcript'] == 'actual excerpt'
    assert json.loads((tmp_path/'step3_all_scored.json').read_text())[0]['final_score'] == .85


def test_backend_failure_still_keeps_explicit_unscored_fallback(tmp_path):
    class BrokenBackend:
        def score(self, _): raise RuntimeError('backend offline')
    scorer = ClipScorer(metadata_dir=tmp_path,scoring_backend=BrokenBackend())
    output=scorer.score_clips([{'id':'1','chunk_index':0,'outline':'one'}])
    assert output[0]['final_score'] == .5
    assert output[0]['score_source'] == 'fallback'


def test_rechunking_score_excerpt_ignores_old_srt_blocks(tmp_path):
    from backend.pipeline.step1_outline import OutlineExtractor
    from backend.pipeline.quality import load_srt_chunks
    extractor = OutlineExtractor.__new__(OutlineExtractor)
    extractor.srt_chunks_dir = tmp_path / 'step1_srt_chunks'
    extractor.srt_chunks_dir.mkdir()
    old = {'start_time':'00:01:00,000','end_time':'00:01:30,000','text':'obsolete text'}
    (extractor.srt_chunks_dir/'chunk_1.json').write_text(json.dumps([old]))
    current = {'start_time':'00:00:00,000','end_time':'00:00:30,000','text':'current text'}
    extractor._save_srt_chunks([{'chunk_index':0,'srt_entries':[current]}])
    assert load_srt_chunks(tmp_path) == [current]
    assert (extractor.srt_chunks_dir/'chunk_1.json').exists()  # old diagnostic is retained
