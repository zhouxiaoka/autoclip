"""Regression cases for #197 / #198 / #195 / #217; no network or model calls."""
import json
from types import SimpleNamespace
import pytest
from backend.pipeline.quality import profile_for, refine_timeline, to_srt_time
from backend.pipeline.step2_timeline import TimelineExtractor
from backend.utils.text_processor import TextProcessor


def cue(s, e):
    return {"start_time": to_srt_time(s), "end_time": to_srt_time(e), "text": "speech"}


def test_adjacent_short_topics_can_merge_before_being_dropped():
    cues = [cue(i, i + 5) for i in range(0, 30, 5)]
    items = [dict(outline=str(i), start_time=to_srt_time(i), end_time=to_srt_time(i + 10)) for i in (0, 10, 20)]
    out, report = refine_timeline(items, cues, profile_for(30))
    assert len(out) == 1
    assert out[0]["duration_sec"] == 30
    assert not report["dropped"]


def test_isolated_short_topics_are_not_merged_across_long_silence():
    cues = [cue(0, 5), cue(30, 35)]
    items = [dict(outline=str(i), start_time=to_srt_time(i), end_time=to_srt_time(i + 5)) for i in (0, 30)]
    out, _ = refine_timeline(items, cues, profile_for(300))
    assert out == []


def extractor(tmp_path):
    obj = TimelineExtractor.__new__(TimelineExtractor)
    obj.metadata_dir = tmp_path
    obj.text_processor = TextProcessor()
    obj.llm_client = SimpleNamespace(parse_json_response=json.loads, _validate_json_structure=lambda x: True)
    return obj


@pytest.mark.parametrize("start,end", [("00:00:01.500", "00:00:25.5"), ("00:01,5", "00:25,500"), ("00:00:01", "00:00:25")])
def test_standard_timestamp_variants_are_normalized(tmp_path, start, end):
    out = extractor(tmp_path)._parse_and_validate_response(json.dumps([dict(outline="topic", start_time=start, end_time=end)]), "00:00:00,000", "00:00:30,000", 0)
    assert len(out) == 1
    assert out[0]["start_time"] == ("00:00:01,000" if start == "00:00:01" else "00:00:01,500")
    assert out[0]["end_time"] == ("00:00:25,000" if end == "00:00:25" else "00:00:25,500")


@pytest.mark.parametrize("start,end", [("00:00:40,000", "00:00:50,000"), ("00:00:20,000", "00:00:10,000"), ("00:60:01,000", "00:61:01,000"), ("NaN", "00:00:25,000")])
def test_invalid_or_outside_chunk_ranges_are_rejected(tmp_path, start, end):
    assert extractor(tmp_path)._parse_and_validate_response(json.dumps([dict(outline="topic", start_time=start, end_time=end)]), "00:00:00,000", "00:00:30,000", 0) == []


def test_full_extraction_normalizes_and_merges_model_topics(tmp_path):
    obj = extractor(tmp_path)
    obj.timeline_prompt = "Extract topics"
    obj.srt_chunks_dir = tmp_path / "step1_srt_chunks"
    obj.timeline_chunks_dir = tmp_path / "step2_timeline_chunks"
    obj.llm_raw_output_dir = tmp_path / "step2_llm_raw_output"
    obj.srt_chunks_dir.mkdir()
    cues = [dict(cue(i, i + 5), index=i // 5 + 1) for i in range(0, 30, 5)]
    (obj.srt_chunks_dir / "chunk_0.json").write_text(json.dumps(cues))
    response = json.dumps([dict(outline=str(i), start_time=to_srt_time(i).replace(",", "."), end_time=to_srt_time(i + 10).replace(",", ".")) for i in (0, 10, 20)])
    obj.llm_client.call_with_retry = lambda *a, **k: response
    out = obj.extract_timeline([dict(title="topic", subtopics=[], chunk_index=0)])
    assert len(out) == 1
    assert out[0]["start_time"] == "00:00:00,000"
    assert out[0]["end_time"] == "00:00:30,000"
    assert out[0]["duration_sec"] == 30
    assert json.loads((tmp_path / "quality_report.json").read_text())["step2"]["output"] == 1


def test_short_source_remains_below_existing_minimum():
    # This fix does not silently lower the product's 20-second minimum.
    out, report = refine_timeline([dict(outline="short", **{k: v for k, v in cue(0, 10).items() if k != "text"})], [cue(0, 10)], profile_for(10))
    assert out == []
    assert len(report["dropped"]) == 1


def test_merge_does_not_exceed_maximum():
    from dataclasses import replace
    profile = replace(profile_for(300), min_clip_sec=20, max_clip_sec=25)
    out, _ = refine_timeline([dict(outline=str(i), start_time=to_srt_time(i), end_time=to_srt_time(i + 15)) for i in (0, 15)], [cue(0, 15), cue(15, 30)], profile)
    assert out == []


def test_partial_overlap_is_clamped_to_chunk(tmp_path):
    out = extractor(tmp_path)._parse_and_validate_response(json.dumps([dict(outline="topic", start_time="00:00:05.5", end_time="00:00:40")]), "00:00:10,000", "00:00:30,000", 1)
    assert out[0]["start_time"] == "00:00:10,000"
    assert out[0]["end_time"] == "00:00:30,000"


def prepared_extractor(tmp_path):
    obj = extractor(tmp_path)
    obj.timeline_prompt = 'extract'
    obj.srt_chunks_dir = tmp_path / 'step1_srt_chunks'
    obj.timeline_chunks_dir = tmp_path / 'step2_timeline_chunks'
    obj.llm_raw_output_dir = tmp_path / 'step2_llm_raw_output'
    for directory in (obj.srt_chunks_dir, obj.timeline_chunks_dir, obj.llm_raw_output_dir):
        directory.mkdir()
    (obj.srt_chunks_dir / 'chunk_0.json').write_text(json.dumps([dict(cue(0, 30), index=1)]))
    obj.llm_client.call_with_retry = lambda *a, **k: ''
    return obj


def topic(title='current', start=0, end=30):
    return dict(outline=title, start_time=to_srt_time(start), end_time=to_srt_time(end))


def test_failed_run_never_returns_previous_timeline(tmp_path):
    obj = prepared_extractor(tmp_path)
    old = json.dumps([topic('stale')])
    (obj.timeline_chunks_dir / 'chunk_0.json').write_text(old)
    assert obj.extract_timeline([dict(title='new', chunk_index=0)]) == []
    assert (obj.timeline_chunks_dir / 'chunk_0.json').read_text() == old


def test_current_run_ignores_obsolete_result_and_subtitle_chunks(tmp_path):
    obj = prepared_extractor(tmp_path)
    (obj.timeline_chunks_dir / 'chunk_9.json').write_text('malformed obsolete result')
    (obj.srt_chunks_dir / 'chunk_9.json').write_text(json.dumps([dict(cue(100, 5000), index=2)]))
    obj.llm_client.call_with_retry = lambda *a, **k: json.dumps([topic()])
    out = obj.extract_timeline([dict(title='current', chunk_index=0)])
    assert [item['outline'] for item in out] == ['current']
    report = json.loads((tmp_path / 'quality_report.json').read_text())['step2']
    assert report['profile']['total_sec'] == 30


@pytest.mark.parametrize('response', [json.dumps([topic()]), 'not json', ''])
def test_cached_response_uses_validation_without_network(tmp_path, response):
    obj = prepared_extractor(tmp_path)
    (obj.llm_raw_output_dir / 'chunk_0.txt').write_text(response)
    obj.llm_client.call_with_retry = lambda *a, **k: pytest.fail('cache must not trigger a paid call')
    out = obj.extract_timeline([dict(title='current', chunk_index=0)])
    assert len(out) == (1 if response.startswith('[') else 0)
    if out:
        assert json.loads((obj.timeline_chunks_dir / 'chunk_0.json').read_text())[0]['outline'] == 'current'


def test_partial_failure_only_returns_successful_current_chunks(tmp_path):
    obj = prepared_extractor(tmp_path)
    (obj.srt_chunks_dir / 'chunk_1.json').write_text(json.dumps([dict(cue(40, 70), index=2)]))
    (obj.timeline_chunks_dir / 'chunk_1.json').write_text(json.dumps([topic('stale', 40, 70)]))
    # Chunks run side by side: answer by chunk content, not call order (chunk 1 starts at 40 s and fails).
    obj.llm_client.call_with_retry = lambda prompt, data, **k: '' if '00:00:40' in data['srt_text'] else json.dumps([topic()])
    out = obj.extract_timeline([dict(title='current', chunk_index=0), dict(title='failed', chunk_index=1)])
    assert [item['outline'] for item in out] == ['current']


def test_short_tail_can_extend_backward_without_crossing_previous_topic():
    cues = [cue(i, i + 5) for i in range(0, 90, 5)]
    out, report = refine_timeline([topic('earlier', 0, 30), topic('tail', 80, 90)], cues, profile_for(90))
    tail = next(c for c in out if c['outline']=='tail')
    assert tail['start_time'] == to_srt_time(70) and tail['duration_sec'] == 20
    assert 'extend_start' in tail['refine']['ops']
    assert not report['dropped']


def test_short_tail_does_not_expand_across_silence():
    out, report = refine_timeline([topic('tail',80,90)], [cue(50,55),cue(80,85),cue(85,90)], profile_for(90))
    assert out == [] and report['dropped']


@pytest.mark.parametrize('start,end', [('1:05.5','1:30'),(65.5,90),('65.5','90')])
def test_timeline_common_model_timestamp_variants(tmp_path,start,end):
    out=extractor(tmp_path)._parse_and_validate_response(json.dumps([dict(title='retained input title',start_time=start,end_time=end)]),to_srt_time(0),to_srt_time(120),0)
    assert len(out)==1 and out[0]['outline']=='retained input title'
    assert out[0]['start_time']==to_srt_time(65.5)


def test_one_malformed_topic_does_not_discard_the_valid_batch(tmp_path):
    obj=extractor(tmp_path)
    from backend.utils.llm_client import LLMClient
    obj.llm_client=LLMClient.__new__(LLMClient)
    out=obj._parse_and_validate_response(json.dumps([{'outline':'bad','start_time':'00:00:00'},topic('valid',0,30),None]),to_srt_time(0),to_srt_time(90),0)
    assert len(out)==1 and out[0]['outline']=='valid'


@pytest.mark.parametrize('value',[True,float('nan'),float('inf'),-1,'1:60','00:60:01','garbage'])
def test_timeline_invalid_numeric_and_colon_times_remain_rejected(tmp_path,value):
    assert not extractor(tmp_path)._validate_time_format(value)


@pytest.mark.parametrize('wrap', [lambda item: item, lambda item: {'timeline': [item]}, lambda item: {'outline': [item]}])
def test_unambiguous_compatible_response_shapes_recover_without_model_call(tmp_path, wrap):
    obj = prepared_extractor(tmp_path)
    from backend.utils.llm_client import LLMClient
    obj.llm_client.parse_json_response = LLMClient.__new__(LLMClient).parse_json_response
    (obj.llm_raw_output_dir / 'chunk_0.txt').write_text(json.dumps(wrap(topic())))
    obj.llm_client.call_with_retry = lambda *a, **k: pytest.fail('recovery must use the recorded response')
    assert len(obj.extract_timeline([dict(title='current', chunk_index=0)])) == 1
    assert obj.extraction_report['chunks'][0]['source'] == 'cache'


def test_ambiguous_response_envelope_is_not_guessed(tmp_path):
    response = json.dumps({'timeline': [topic()], 'outline': [topic('other')]})
    obj = extractor(tmp_path)
    assert obj._parse_and_validate_response(response, to_srt_time(0), to_srt_time(30), 0) == []
    assert obj._last_parse_diagnostics['rejected']['invalid_container'] == 1


def run_prepared_step2(obj, monkeypatch):
    from backend.pipeline import step2_timeline
    monkeypatch.setattr(step2_timeline, 'TimelineExtractor', lambda *a, **k: obj)
    path = obj.metadata_dir / 'step1_outline.json'
    path.write_text(json.dumps([dict(title='current', chunk_index=0)]))
    return step2_timeline.run_step2_timeline(path, metadata_dir=obj.metadata_dir)


@pytest.mark.parametrize('error,code', [
    (TimeoutError('private-url secret-key'), 'timeout'),
    (ConnectionError('private-url secret-key'), 'connection'),
    (RuntimeError('API调用失败 - Status: 429, Message: secret-key'), 'rate_limited'),
    (RuntimeError('API调用失败 - Status: 401, Message: secret-key'), 'authentication'),
    (RuntimeError('API调用失败 - Status: 503, Message: secret-key'), 'provider_error'),
])
def test_step2_call_failure_is_not_reported_as_short_content(tmp_path, monkeypatch, error, code):
    from backend.pipeline.failures import PipelineFailure
    obj = prepared_extractor(tmp_path)
    calls = []
    def fail(*a, **k):
        calls.append(1)
        raise error
    obj.llm_client.call_with_retry = fail
    with pytest.raises(PipelineFailure) as exc:
        run_prepared_step2(obj, monkeypatch)
    assert len(calls) == 1  # The inner client already owns transport retries.
    assert exc.value.code == code
    assert '最短时长' not in exc.value.user_message()
    assert 'secret-key' not in exc.value.user_message()
    report = json.loads((tmp_path / 'quality_report.json').read_text())['step2_extraction']
    assert report['chunks'][0]['error_code'] == code
    assert 'secret-key' not in json.dumps(report)
    assert json.loads((tmp_path / 'step2_timeline.json').read_text()) == []


@pytest.mark.parametrize('response,reason', [
    ('not json', 'malformed_json'),
    ('{}', 'invalid_container'),
    ('[]', 'empty_array'),
    (json.dumps([topic('outside', 40, 60)]), 'outside_chunk_or_reversed'),
    (json.dumps([{'outline':'bad', 'start_time':'NaN', 'end_time':30}]), 'invalid_time'),
])
def test_step2_invalid_reply_has_current_safe_diagnostics(tmp_path, monkeypatch, response, reason):
    from backend.pipeline.failures import PipelineFailure
    obj = prepared_extractor(tmp_path)
    (obj.llm_raw_output_dir / 'chunk_0.txt').write_text(response)
    obj.llm_client.call_with_retry = lambda *a, **k: pytest.fail('invalid cache cannot silently spend money')
    # A failed rerun must replace the previous successful Step 2 report.
    (tmp_path / 'quality_report.json').write_text(json.dumps({'step2': {'input':99, 'output':99}}))
    with pytest.raises(PipelineFailure) as exc:
        run_prepared_step2(obj, monkeypatch)
    assert exc.value.code == 'invalid_response'
    assert '尚未进入评分或最短时长筛选' in exc.value.user_message()
    assert '创建新项目' in exc.value.hint
    saved = json.loads((tmp_path / 'quality_report.json').read_text())
    report = saved['step2_extraction']
    assert report['parsed'] == report['output'] == 0
    assert saved['step2']['output'] == 0
    assert report['chunks'][0]['rejected'][reason] == 1


@pytest.mark.parametrize('total,min_sec,start,end', [(10,20,0,10), (600,45,0,30), (3600,90,0,30)])
def test_step2_duration_failure_reports_actual_profile(tmp_path, monkeypatch, total, min_sec, start, end):
    from backend.pipeline.failures import PipelineFailure
    from backend.pipeline.quality import save_profile
    obj = prepared_extractor(tmp_path)
    (obj.srt_chunks_dir / 'chunk_0.json').write_text(json.dumps([dict(cue(start, end), index=1)]))
    save_profile(profile_for(total), tmp_path)
    obj.llm_client.call_with_retry = lambda *a, **k: json.dumps([topic('short', start, end)])
    with pytest.raises(PipelineFailure) as exc:
        run_prepared_step2(obj, monkeypatch)
    assert exc.value.code == 'timeline_empty'
    assert f'{min_sec} 秒' in exc.value.message
    assert '模型' not in exc.value.hint
    assert obj.extraction_report['parsed'] == 1 and obj.extraction_report['output'] == 0


def test_step2_missing_subtitle_block_points_to_reimport(tmp_path, monkeypatch):
    from backend.pipeline.failures import PipelineFailure
    obj = prepared_extractor(tmp_path)
    (obj.srt_chunks_dir / 'chunk_0.json').unlink()
    with pytest.raises(PipelineFailure) as exc:
        run_prepared_step2(obj, monkeypatch)
    assert exc.value.code == 'missing_resource'
    assert '重新导入' in exc.value.hint


def test_corrupted_chunk_is_not_a_model_or_duration_failure(tmp_path, monkeypatch):
    from backend.pipeline.failures import PipelineFailure
    obj = prepared_extractor(tmp_path)
    (obj.srt_chunks_dir / 'chunk_0.json').write_text('not json')
    with pytest.raises(PipelineFailure) as exc:
        run_prepared_step2(obj, monkeypatch)
    assert exc.value.code == 'unexpected'
    assert '数据目录' in exc.value.hint


def test_live_json_repair_stays_bounded_and_returns_recovered_chunk(tmp_path):
    obj = prepared_extractor(tmp_path)
    calls = []
    def response(prompt, data):
        calls.append(dict(data))
        return 'not json' if len(calls) == 1 else json.dumps({'timeline':[topic()]})
    obj.llm_client.call_with_retry = response
    assert len(obj.extract_timeline([dict(title='current', chunk_index=0)])) == 1
    assert len(calls) == 2
    assert 'additional_instruction' in calls[1]
    assert obj.extraction_report['chunks'][0]['attempts'] == 2


def test_all_live_invalid_replies_stop_after_three_repair_attempts(tmp_path):
    obj = prepared_extractor(tmp_path)
    calls = []
    def response(*a, **k):
        calls.append(1)
        return 'not json'
    obj.llm_client.call_with_retry = response
    assert obj.extract_timeline([dict(title='current', chunk_index=0)]) == []
    assert len(calls) == 3


def test_step2_refinement_error_never_exports_unvalidated_ranges(tmp_path, monkeypatch):
    from backend.pipeline.failures import PipelineFailure
    from backend.pipeline import quality
    obj = prepared_extractor(tmp_path)
    obj.llm_client.call_with_retry = lambda *a, **k: json.dumps([topic()])
    def fail(*a, **k):
        raise RuntimeError('private local path')
    monkeypatch.setattr(quality, 'refine_timeline', fail)
    with pytest.raises(PipelineFailure) as exc:
        obj.extract_timeline([dict(title='current', chunk_index=0)])
    assert exc.value.code == 'unexpected'
    assert 'private' not in exc.value.user_message()
    assert obj.extraction_report['refinement_failed']
