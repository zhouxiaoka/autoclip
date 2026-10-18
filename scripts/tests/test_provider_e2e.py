import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from backend.core.upstream_errors import UpstreamErrorType, is_retryable
from provider_e2e import SUCCESS_RATE_THRESHOLD, judge, mask, matrix, mock_openai
from provider_e2e.presets import find_e2e_presets_path, load_catalog_providers
from provider_e2e.report import merge_reports
from provider_e2e.settings import live_ready
import release_acceptance as gate


def _catalog_payload(providers: dict) -> dict:
    return {'schema_version': 1, 'version': 1, 'providers': providers}


def _preset_row(*, display_name: str, short_name: str, group: str = 'popular',
                base_url: str = '', default_model: str = '', analysis=None) -> dict:
    return {
        'kind': 'preset',
        'display_name': display_name,
        'short_name': short_name,
        'group': group,
        'protocol': 'openai-completions',
        'base_url': base_url,
        'default_model': default_model,
        'candidates': {'analysis': list(analysis or []), 'vision': [], 'asr': [], 'image': []},
    }


def _full_live_catalog(**overrides: dict) -> dict:
    rows = {
        'api88': _preset_row(display_name='88API', short_name='88API', group='recommended',
                             base_url='https://api.88api.ai/v1', default_model='deepseek-v4-flash'),
        'deepseek': _preset_row(display_name='DeepSeek', short_name='DeepSeek',
                                base_url='https://api.deepseek.com', default_model='deepseek-flash'),
        'gemini': _preset_row(display_name='Google Gemini', short_name='Gemini',
                              base_url='https://generativelanguage.googleapis.com/v1beta/openai',
                              default_model='gemini-3.5-flash-lite'),
        'dashscope': _preset_row(display_name='阿里云百炼', short_name='DashScope',
                                 base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
                                 default_model='qwen-plus'),
        'infistar': _preset_row(display_name='Infistar', short_name='Infistar', group='recommended',
                                base_url='https://infistar.ai/v1', default_model='gpt-4o-mini'),
    }
    rows.update(overrides)
    return _catalog_payload(rows)


class ProviderE2EContractTests(unittest.TestCase):
    def test_product_models_do_not_override_live_defaults(self):
        raw = _full_live_catalog()
        for provider in raw['providers'].values():
            provider['default_model'] = 'product-only-model'
            provider['candidates']['analysis'] = ['product-only-candidate']
        raw['providers']['gemini']['default_model'] = 'gemini-3.8-flash'
        raw['providers']['gemini']['base_url'] = 'https://generativelanguage.googleapis.com/v1beta'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'provider_presets.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            before = path.read_bytes()
            with patch.dict(os.environ, {'AUTOCLIP_PROVIDER_PRESETS': str(path)}):
                matrix.reset_live_catalog()
                try:
                    providers = {item['id']: item for item in matrix.live_providers()}
                    for expected in matrix.LIVE_PROVIDERS:
                        with self.subTest(provider=expected['id']):
                            provider = providers[expected['id']]
                            self.assertEqual(provider['default_model'], expected['default_model'])
                            ready = live_ready(provider, {provider['secret']: 'sk-test-key'})
                            self.assertEqual(ready['model'], expected['default_model'])
                            override = live_ready(provider, {
                                provider['secret']: 'sk-test-key',
                                provider['model_env']: 'explicit-live-model',
                            })
                            self.assertEqual(override['model'], 'explicit-live-model')
                    self.assertEqual(providers['gemini']['default_model'], 'gemini-3.5-flash-lite')
                    self.assertEqual(providers['gemini']['base_url'],
                                     'https://generativelanguage.googleapis.com/v1beta/openai')
                    self.assertEqual(path.read_bytes(), before)
                finally:
                    matrix.reset_live_catalog()

    def test_matrix_has_eight_success_and_two_blocks(self):
        succeed = matrix.assets(expect='succeed')
        blocked = matrix.assets(expect='block')
        self.assertEqual(len(succeed), 8)
        self.assertEqual(len(blocked), 2)
        self.assertEqual({item['id'] for item in blocked}, {'too_short', 'no_audio'})
        self.assertLess(matrix.TOO_SHORT_DURATION_SEC, 20)
        self.assertGreaterEqual(matrix.SUCCESS_DURATION_SEC, 60)
        self.assertLessEqual(matrix.SUCCESS_DURATION_SEC, 120)
        self.assertTrue(all(item['duration_sec'] >= 20 for item in succeed))
        labels = {item['label'] for item in succeed}
        for name in ('中文口播', '中文访谈', '英文播客', '带字幕', '竖屏', '游戏', '体育', '纯音乐'):
            self.assertIn(name, labels)
        self.assertEqual({item['id']: item['block_code'] for item in blocked}, {
            'too_short': 'source_too_short',
            'no_audio': 'source_no_audio',
        })

    def test_live_providers_and_faults(self):
        providers = {item['id']: item for item in matrix.live_providers()}
        self.assertEqual(set(providers), {'api88', 'deepseek', 'gemini', 'dashscope', 'infistar'})
        self.assertEqual(providers['api88']['base_url'], 'https://api.88api.ai/v1')
        self.assertEqual(providers['gemini']['base_url'], 'https://generativelanguage.googleapis.com/v1beta/openai')
        self.assertTrue(providers['gemini']['base_url'].endswith('/openai'))
        self.assertEqual(providers['dashscope']['base_url'], 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.assertEqual(providers['infistar']['base_url'], 'https://infistar.ai/v1')
        self.assertEqual(providers['dashscope']['secret'], 'DASHSCOPE_API_KEY')
        self.assertEqual(providers['infistar']['secret'], 'INFISTAR_API_KEY')
        self.assertEqual(providers['dashscope']['default_model'], 'qwen-plus')
        self.assertEqual(providers['gemini']['default_model'], 'gemini-3.5-flash-lite')
        self.assertEqual(providers['deepseek']['default_model'], 'deepseek-flash')
        self.assertEqual(providers['api88']['default_model'], 'deepseek-v4-flash')
        self.assertEqual(providers['infistar']['default_model'], 'gpt-4o-mini')
        self.assertTrue(all(item['default_model'] for item in providers.values()))
        faults = {item['id']: item for item in matrix.faults()}
        self.assertEqual(set(faults), {'rate_limited_429', 'unavailable_503', 'disconnect', 'kill_backend'})
        self.assertEqual(faults['rate_limited_429']['upstream_error_type'], UpstreamErrorType.RATE_LIMITED.value)
        self.assertEqual(faults['unavailable_503']['upstream_error_type'], UpstreamErrorType.UPSTREAM_UNAVAILABLE.value)
        self.assertEqual(faults['disconnect']['upstream_error_type'], UpstreamErrorType.CONNECTION.value)
        self.assertIsNone(faults['kill_backend']['upstream_error_type'])
        for item in faults.values():
            if item['upstream_error_type'] is None:
                continue
            self.assertTrue(is_retryable(item['upstream_error_type']))
            classified = mock_openai.classify_injected_fault(item['fault'])
            self.assertIsNotNone(classified)
            self.assertEqual(classified.error_type.value, item['upstream_error_type'])
            self.assertTrue(classified.retryable)

    def test_release_acceptance_requires_provider_e2e_job(self):
        self.assertIn('provider-e2e', gate.BUILD_JOBS)
        workflow = (ROOT / '.github/workflows/provider-e2e-gate.yml').read_text(encoding='utf-8')
        desktop = (ROOT / '.github/workflows/desktop-build.yml').read_text(encoding='utf-8')
        self.assertIn('environment: provider-e2e', workflow)
        self.assertIn('DASHSCOPE_API_KEY', workflow)
        self.assertIn('INFISTAR_API_KEY', workflow)
        self.assertIn('workflow_call', workflow)
        self.assertIn('head.repo.full_name == github.repository', workflow)
        self.assertIn('scripts/provider_e2e/**', workflow)
        self.assertIn('fork-skip', workflow)
        self.assertIn('uses: ./.github/workflows/provider-e2e-gate.yml', desktop)
        self.assertIn('needs: [candidate-gate]', desktop)
        self.assertIn('needs.provider-e2e.result == \'success\'', desktop)
        self.assertIn('github.event_name == \'schedule\'', workflow)
        self.assertNotIn('e2e-live-once', workflow)
        self.assertIn('provider-e2e-cases', workflow)
        self.assertIn('live_mode', workflow)
        self.assertIn('--expect-live', workflow)
        self.assertIn('fail-closed: live job ran but report.json is missing or empty', workflow)

    def test_mask_redacts_keys(self):
        text = mask.redact_text('Authorization: Bearer sk-abc123456789 and api_key=supersecretvalue')
        self.assertNotIn('sk-abc123456789', text)
        self.assertNotIn('supersecretvalue', text)
        self.assertIn('***', text)
        hidden = mask.redact({'api_key': 'sk-live-should-hide', 'ok': 'plain'}, ['sk-live-should-hide'])
        self.assertEqual(hidden['api_key'], '***')
        self.assertEqual(hidden['ok'], 'plain')

    def test_live_ready_skips_without_secrets(self):
        for provider in matrix.live_providers():
            self.assertFalse(live_ready(provider, {})['ready'])
            ready = live_ready(provider, {provider['secret']: 'sk-test-key'})
            self.assertTrue(ready['ready'], provider['id'])
            self.assertEqual(ready['model'], provider['default_model'])
            self.assertEqual(ready['model_source'], 'default')
            self.assertEqual(ready['base_url'], provider['base_url'])
            override = live_ready(provider, {
                provider['secret']: 'sk-test-key',
                provider['model_env']: 'custom-model',
            })
            self.assertEqual(override['model'], 'custom-model')
            self.assertEqual(override['model_source'], 'secret')

    def test_live_providers_follow_catalog_labels_but_keep_live_defaults(self):
        raw = _full_live_catalog(deepseek=_preset_row(
            display_name='DeepSeek',
            short_name='FixtureSeek',
            base_url='https://example.test/deepseek',
            default_model='fixture-flash',
        ))
        raw['providers']['deepseek']['api_key'] = 'sk-should-never-appear'
        raw['providers']['api88']['default_model'] = ''
        raw['providers']['api88']['candidates']['analysis'] = []
        old = os.environ.get('AUTOCLIP_PROVIDER_PRESETS')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'provider_presets.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            os.environ['AUTOCLIP_PROVIDER_PRESETS'] = str(path)
            matrix.reset_live_catalog()
            try:
                providers = {item['id']: item for item in matrix.live_providers()}
            finally:
                if old is None:
                    os.environ.pop('AUTOCLIP_PROVIDER_PRESETS', None)
                else:
                    os.environ['AUTOCLIP_PROVIDER_PRESETS'] = old
                matrix.reset_live_catalog()
        self.assertEqual(providers['deepseek']['base_url'], 'https://api.deepseek.com')
        self.assertEqual(providers['deepseek']['default_model'], 'deepseek-flash')
        self.assertEqual(providers['deepseek']['label'], 'FixtureSeek')
        self.assertEqual(providers['api88']['default_model'], 'deepseek-v4-flash')
        dumped = json.dumps(providers, ensure_ascii=False)
        self.assertNotIn('sk-should-never-appear', dumped)
        self.assertTrue(all('api_key' not in item for item in providers.values()))

    def test_catalog_analysis_candidate_does_not_override_live_default(self):
        raw = _full_live_catalog(gemini=_preset_row(
            display_name='Google Gemini',
            short_name='Gemini',
            base_url='https://generativelanguage.googleapis.com/v1beta/openai',
            default_model='',
            analysis=['gemini-from-candidates'],
        ))
        old = os.environ.get('AUTOCLIP_PROVIDER_PRESETS')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'provider_presets.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            os.environ['AUTOCLIP_PROVIDER_PRESETS'] = str(path)
            matrix.reset_live_catalog()
            try:
                providers = {item['id']: item for item in matrix.live_providers()}
            finally:
                if old is None:
                    os.environ.pop('AUTOCLIP_PROVIDER_PRESETS', None)
                else:
                    os.environ['AUTOCLIP_PROVIDER_PRESETS'] = old
                matrix.reset_live_catalog()
        self.assertEqual(providers['gemini']['default_model'], 'gemini-3.5-flash-lite')

    def test_unknown_schema_is_rejected(self):
        raw = _full_live_catalog()
        raw['schema_version'] = 99
        old = os.environ.get('AUTOCLIP_PROVIDER_PRESETS')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            os.environ['AUTOCLIP_PROVIDER_PRESETS'] = str(path)
            matrix.reset_live_catalog()
            try:
                with self.assertRaises(ValueError):
                    matrix.live_providers()
            finally:
                if old is None:
                    os.environ.pop('AUTOCLIP_PROVIDER_PRESETS', None)
                else:
                    os.environ['AUTOCLIP_PROVIDER_PRESETS'] = old
                matrix.reset_live_catalog()

    def test_missing_live_entry_is_fail_closed(self):
        raw = _full_live_catalog()
        del raw['providers']['dashscope']
        old = os.environ.get('AUTOCLIP_PROVIDER_PRESETS')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'partial.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            os.environ['AUTOCLIP_PROVIDER_PRESETS'] = str(path)
            matrix.reset_live_catalog()
            try:
                with self.assertRaises(KeyError):
                    matrix.live_providers()
            finally:
                if old is None:
                    os.environ.pop('AUTOCLIP_PROVIDER_PRESETS', None)
                else:
                    os.environ['AUTOCLIP_PROVIDER_PRESETS'] = old
                matrix.reset_live_catalog()

    def test_missing_presets_env_is_fail_closed(self):
        old = os.environ.get('AUTOCLIP_PROVIDER_PRESETS')
        os.environ['AUTOCLIP_PROVIDER_PRESETS'] = '/tmp/autoclip-missing-provider-presets.json'
        matrix.reset_live_catalog()
        try:
            with self.assertRaises(FileNotFoundError):
                matrix.live_providers()
        finally:
            if old is None:
                os.environ.pop('AUTOCLIP_PROVIDER_PRESETS', None)
            else:
                os.environ['AUTOCLIP_PROVIDER_PRESETS'] = old
            matrix.reset_live_catalog()

    def test_product_gemini_38_flash_gets_openai_compat_url(self):
        raw = _full_live_catalog(gemini=_preset_row(
            display_name='Google Gemini',
            short_name='Gemini',
            base_url='https://generativelanguage.googleapis.com/v1beta',
            default_model='gemini-3.8-flash',
        ))
        old = os.environ.get('AUTOCLIP_PROVIDER_PRESETS')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'provider_presets.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            os.environ['AUTOCLIP_PROVIDER_PRESETS'] = str(path)
            matrix.reset_live_catalog()
            try:
                providers = {item['id']: item for item in matrix.live_providers()}
            finally:
                if old is None:
                    os.environ.pop('AUTOCLIP_PROVIDER_PRESETS', None)
                else:
                    os.environ['AUTOCLIP_PROVIDER_PRESETS'] = old
                matrix.reset_live_catalog()
        self.assertEqual(providers['gemini']['default_model'], 'gemini-3.5-flash-lite')
        self.assertEqual(
            providers['gemini']['base_url'],
            'https://generativelanguage.googleapis.com/v1beta/openai',
        )
        self.assertTrue(providers['gemini']['base_url'].endswith('/openai'))

    def test_dashscope_live_default_is_qwen_plus(self):
        providers = {item['id']: item for item in matrix.live_providers()}
        self.assertEqual(providers['dashscope']['default_model'], 'qwen-plus')
        overlay = next(item for item in matrix.LIVE_PROVIDERS if item['id'] == 'dashscope')
        self.assertEqual(overlay['default_model'], 'qwen-plus')

    def test_live_defaults_do_not_write_product_json(self):
        shipped = ROOT / 'backend' / 'presets' / 'provider_presets.json'
        existed = shipped.is_file()
        before = shipped.read_bytes() if existed else None
        matrix.reset_live_catalog()
        matrix.live_providers()
        if existed:
            self.assertEqual(shipped.read_bytes(), before)
            default = json.loads(shipped.read_text(encoding='utf-8'))['providers']['dashscope']['default_model']
            self.assertEqual(default, 'qwen-plus')
        else:
            self.assertFalse(shipped.exists())

    def test_catalog_path_prefers_shipped_json_then_live_defaults(self):
        old = os.environ.get('AUTOCLIP_PROVIDER_PRESETS')
        if old is not None:
            os.environ.pop('AUTOCLIP_PROVIDER_PRESETS', None)
        matrix.reset_live_catalog()
        try:
            shipped = ROOT / 'backend' / 'presets' / 'provider_presets.json'
            path = find_e2e_presets_path()
            providers = {item['id']: item for item in matrix.live_providers()}
            if shipped.is_file():
                self.assertEqual(path, shipped.resolve())
                raw = json.loads(shipped.read_text(encoding='utf-8'))['providers']
                self.assertEqual(providers['deepseek']['label'], 'DeepSeek')
                self.assertTrue(raw['deepseek']['base_url'].strip())
                self.assertNotIn('api_key', providers['deepseek'])
            else:
                self.assertIsNone(path)
                self.assertEqual(providers['dashscope']['default_model'], 'qwen-plus')
                self.assertEqual(set(load_catalog_providers()), set())
        finally:
            if old is not None:
                os.environ['AUTOCLIP_PROVIDER_PRESETS'] = old
            matrix.reset_live_catalog()

    def test_judge_thresholds(self):
        succeed = [{'expect': 'succeed', 'passed': True} for _ in range(8)]
        blocked = [
            {'expect': 'block', 'passed': True, 'billable_calls_before_failure': 0},
            {'expect': 'block', 'passed': True, 'billable_calls_before_failure': 0},
        ]
        report = {'cases': succeed + blocked, 'status': 'completed'}
        self.assertTrue(judge.judge_suite(report)['passed'])
        self.assertGreaterEqual(judge.success_rate(succeed), SUCCESS_RATE_THRESHOLD)

        failed = dict(report)
        failed['cases'] = succeed[:-1] + [{'expect': 'succeed', 'passed': False}] + blocked
        # 7/8 = 87.5% < 95%
        self.assertFalse(judge.judge_suite(failed)['passed'])

        billed = dict(report)
        billed['cases'] = succeed + [
            {'expect': 'block', 'passed': True, 'billable_calls_before_failure': 1},
            {'expect': 'block', 'passed': True, 'billable_calls_before_failure': 0},
        ]
        self.assertFalse(judge.judge_suite(billed)['passed'])
        self.assertIn('billable_calls_before_failure', ' '.join(judge.judge_suite(billed)['reasons']))

        injected = dict(report)
        injected['cases'] = succeed + blocked + [{
            'expect': 'succeed',
            'passed': True,
            'expected_upstream_error_type': UpstreamErrorType.RATE_LIMITED.value,
            'upstream_error_type': UpstreamErrorType.RATE_LIMITED.value,
        }]
        verdict = judge.judge_suite(injected)
        self.assertTrue(verdict['passed'])
        self.assertEqual(verdict['should_succeed_n'], 8)
        self.assertEqual(verdict['fault_n'], 1)

        bad_type = dict(report)
        bad_type['cases'] = succeed + blocked + [{
            'expect': 'succeed',
            'passed': True,
            'expected_upstream_error_type': 'not_a_contract_type',
        }]
        self.assertFalse(judge.judge_suite(bad_type)['passed'])

        skipped = {'status': 'skipped', 'reason': 'secrets unset', 'cases': []}
        self.assertTrue(judge.judge_suite(skipped)['skipped'])
        self.assertTrue(judge.judge_reports([report, skipped])['passed'])

    def test_import_refusal_code_only_takes_coded_source_422(self):
        # #418: the preflight refuses a bad source at import (coded 422, no project) -> a valid block.
        import json as _json
        from provider_e2e.harness import import_refusal_code
        from provider_e2e.http_util import HttpError
        body = _json.dumps({'error': {'code': 'HTTP_422'}, 'detail': {'code': 'source_no_audio', 'message': 'x'}})
        self.assertEqual(import_refusal_code(HttpError(422, body)), 'source_no_audio')
        self.assertIsNone(import_refusal_code(HttpError(500, body)))
        self.assertIsNone(import_refusal_code(HttpError(422, _json.dumps({'detail': {'code': 'whisper_not_installed'}}))))
        self.assertIsNone(import_refusal_code(HttpError(422, 'not json')))
        self.assertIsNone(import_refusal_code(HttpError(422, _json.dumps({'detail': '视频文件为空'}))))

    def test_refusal_counts_only_for_should_block_cases(self):
        import json as _json
        from provider_e2e.harness import refusal_workspace
        from provider_e2e.http_util import HttpError
        exc = HttpError(422, _json.dumps({'detail': {'code': 'source_too_short', 'message': 'x'}}))
        self.assertEqual(refusal_workspace('block', exc)['generation']['error_code'], 'source_too_short')
        for expect in ('succeed', 'service_restarted'):
            self.assertIsNone(refusal_workspace(expect, exc), expect)

    def test_unknown_paid_call_count_never_passes_a_block(self):
        # #353: "no project" is not "zero calls"; a call seen by the observer before the 422 fails the case.
        from provider_e2e.harness import evaluate_case, observed_chat_calls
        refused = {'generation': {'status': 'failed', 'error_code': 'source_no_audio', 'failure_stage': 'INGEST'}, 'analysis': {}}
        self.assertFalse(evaluate_case('block', refused, None, 'source_no_audio')['passed'])
        self.assertTrue(evaluate_case('block', refused, 0, 'source_no_audio')['passed'])

        class Observer:
            class state:
                @staticmethod
                def snapshot():
                    return {'events': [{'path': '/v1/models'}, {'path': '/v1/chat/completions'}]}
        self.assertEqual(observed_chat_calls(Observer, 0), 1)
        self.assertEqual(observed_chat_calls(Observer, 2), 0)
        self.assertIsNone(observed_chat_calls(None, 0))
        from provider_e2e.harness import paid_calls
        self.assertIsNone(paid_calls(None, None), 'no project and no observer: unknown, not 0')
        self.assertEqual(paid_calls(1, None), 1)
        self.assertEqual(paid_calls(None, 2), 2)
        self.assertEqual(paid_calls(1, 0), 1, 'a call the observer saw counts even if the ledger missed it')
        from provider_e2e import judge
        row = {'id': 'mock:no_audio', 'expect': 'block', 'passed': True, 'billable_calls_before_failure': None, 'billable_calls': None}
        self.assertFalse(judge.judge_suite({'status': 'ok', 'cases': [row]})['passed'])

    def test_evaluate_block_requires_zero_billable(self):
        from provider_e2e.harness import evaluate_case
        workspace = {
            'generation': {'status': 'failed', 'error_code': 'source_too_short', 'failure_stage': 'screening'},
            'analysis': {'status': 'failed', 'phase': 'screening', 'error_code': 'source_too_short'},
        }
        self.assertTrue(evaluate_case('block', workspace, 0, 'source_too_short')['passed'])
        self.assertFalse(evaluate_case('block', workspace, 1, 'source_too_short')['passed'])
        self.assertTrue(evaluate_case('service_restarted', {
            'generation': {'status': 'failed', 'error_code': 'service_restarted'},
            'analysis': {},
        }, 0)['passed'])
        self.assertTrue(evaluate_case('succeed', {
            'generation': {'status': 'completed'},
            'output_variants': [{'status': 'completed'}],
        }, 3)['passed'])
        recovered = evaluate_case(
            'succeed',
            {'generation': {'status': 'completed'}, 'output_variants': [{'status': 'completed'}]},
            8,
            expected_upstream_error_type=UpstreamErrorType.RATE_LIMITED.value,
            observed_upstream_error_type=UpstreamErrorType.RATE_LIMITED.value,
        )
        self.assertTrue(recovered['passed'])
        mismatch = evaluate_case(
            'succeed',
            {'generation': {'status': 'completed'}, 'output_variants': [{'status': 'completed'}]},
            8,
            expected_upstream_error_type=UpstreamErrorType.RATE_LIMITED.value,
            observed_upstream_error_type=UpstreamErrorType.INVALID_KEY.value,
        )
        self.assertFalse(mismatch['passed'])

    def test_mock_server_models_and_faults(self):
        server, root = mock_openai.start()
        try:
            models = json.loads(urlopen(root + '/v1/models', timeout=5).read().decode())
            self.assertEqual(models['data'][0]['id'], 'mock-gpt')

            def chat(url):
                body = json.dumps({
                    'model': 'mock-gpt',
                    'messages': [{'role': 'user', 'content': 'final_score 请评分'}],
                }).encode()
                request = Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
                return urlopen(request, timeout=5)

            with self.assertRaises(HTTPError) as first:
                chat(root + '/fault/429/v1/chat/completions')
            self.assertEqual(first.exception.code, 429)
            self.assertEqual(first.exception.headers.get('Retry-After'), '1')
            classified_429 = mock_openai.classify_injected_fault('429')
            self.assertEqual(classified_429.error_type, UpstreamErrorType.RATE_LIMITED)
            self.assertTrue(classified_429.retryable)
            second = json.loads(chat(root + '/fault/429/v1/chat/completions').read().decode())
            self.assertIn('final_score', second['choices'][0]['message']['content'])

            with self.assertRaises(HTTPError) as unavailable:
                chat(root + '/fault/503/v1/chat/completions')
            self.assertEqual(unavailable.exception.code, 503)
            self.assertEqual(
                mock_openai.classify_injected_fault('503').error_type,
                UpstreamErrorType.UPSTREAM_UNAVAILABLE,
            )
            recovered = chat(root + '/fault/503/v1/chat/completions')
            self.assertEqual(recovered.status, 200)

            outline = json.loads(urlopen(Request(
                root + '/v1/chat/completions',
                data=json.dumps({'messages': [{'role': 'user', 'content': '提取大纲'}]}).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST',
            ), timeout=5).read().decode())
            topics = json.loads(outline['choices'][0]['message']['content'])
            self.assertIsInstance(topics, list)
            self.assertIn('title', topics[0])
        finally:
            mock_openai.stop(server)

    def test_srt_and_merge_report(self):
        from provider_e2e.fixtures import srt_text
        text = srt_text(('第一句', '第二句'), 25)
        self.assertIn('00:00:00,000', text)
        self.assertIn('00:00:25,000', text)
        merged = merge_reports([
            {'suite': 'mock', 'status': 'completed', 'commit': 'a' * 40, 'cases': [{'id': 'm'}]},
            {'suite': 'live', 'status': 'skipped', 'reason': 'secrets unset', 'cases': []},
        ])
        self.assertEqual(merged['suite'], 'combined')
        self.assertEqual(len(merged['cases']), 1)
        self.assertTrue(merged['skipped_providers'])

    def test_announced_port_ignores_partial_lines(self):
        from provider_e2e.backend import announced_port
        self.assertIsNone(announced_port('starting\nPORT=\n'))
        self.assertEqual(announced_port('PORT=\nPORT=8123\nBACKEND_URL=http://127.0.0.1:8123'), '8123')

    def test_docs_exist(self):
        doc = (ROOT / 'docs/PROVIDER_E2E_GATE.md').read_text(encoding='utf-8')
        self.assertIn('provider-e2e', doc)
        self.assertIn('backend/presets/provider_presets.json', doc)
        self.assertIn('API88_API_KEY', doc)
        self.assertIn('DASHSCOPE_API_KEY', doc)
        self.assertIn('INFISTAR_API_KEY', doc)
        self.assertIn('api.88api.ai/v1', doc)
        self.assertIn('deepseek-v4-flash', doc)
        self.assertIn('dashscope.aliyuncs.com/compatible-mode/v1', doc)
        self.assertIn('infistar.ai/v1', doc)
        self.assertIn('¥300', doc)
        self.assertIn('provider-e2e-cases', doc)
        self.assertIn('ISO', doc)
        self.assertIn('gemini-3.5-flash-lite', doc)
        self.assertIn('qwen-plus', doc)
        self.assertIn('/openai', doc)
        self.assertIn('fail-closed', doc)
        self.assertIn('不要只靠这一条探针放行', doc)
        self.assertIn('UpstreamErrorType', doc)
        self.assertIn('billable_calls_before_failure', doc)
        self.assertIn('SUCCESS_RATE_CONTRACT.md', doc)
        self.assertIn('PROVIDER_E2E_GATE.md', (ROOT / 'docs/README.md').read_text(encoding='utf-8'))
        contract = (ROOT / 'docs/SUCCESS_RATE_CONTRACT.md').read_text(encoding='utf-8')
        self.assertIn('UpstreamErrorType', contract)
        self.assertIn('billable_calls_before_failure', contract)


class ProviderE2ECostControlTests(unittest.TestCase):
    def test_nightly_plan_only_uses_free_tier_providers(self):
        week0 = matrix.assignments('nightly', week=1)
        self.assertEqual(len(week0), 3)
        self.assertEqual({item['clip_id'] for item in week0}, set(matrix.NIGHTLY_CLIP_IDS))
        self.assertTrue(all(item['provider_id'] in matrix.NIGHTLY_PROVIDER_IDS for item in week0))
        week1 = matrix.assignments('nightly', week=2)
        self.assertNotEqual(
            [(item['provider_id'], item['clip_id']) for item in week0],
            [(item['provider_id'], item['clip_id']) for item in week1],
        )

    def test_prerelease_splits_ten_clips_across_five_providers(self):
        plan = matrix.assignments('prerelease', week=12)
        self.assertEqual(len(plan), 10)
        counts = {}
        for item in plan:
            counts[item['provider_id']] = counts.get(item['provider_id'], 0) + 1
        self.assertEqual(set(counts), {'api88', 'deepseek', 'gemini', 'dashscope', 'infistar'})
        self.assertTrue(all(value == 2 for value in counts.values()))
        rotated = matrix.assignments('prerelease', week=13)
        self.assertNotEqual(
            [(item['provider_id'], item['clip_id']) for item in plan],
            [(item['provider_id'], item['clip_id']) for item in rotated],
        )

    def test_verify_adds_one_probe_per_paid_provider(self):
        plan = matrix.assignments('verify', week=3)
        probes = [item for item in plan if item['role'] == 'probe']
        self.assertEqual({item['provider_id'] for item in probes}, set(matrix.VERIFY_PAID_PROVIDER_IDS))
        self.assertTrue(all(item['clip_id'] == matrix.VERIFY_PROBE_CLIP_ID for item in probes))
        self.assertGreaterEqual(len(plan), 6)

    def test_resolve_mode_from_event(self):
        self.assertEqual(matrix.resolve_mode({'GITHUB_EVENT_NAME': 'schedule'}), 'nightly')
        self.assertEqual(matrix.resolve_mode({'GITHUB_REF': 'refs/tags/v1.5.7'}), 'prerelease')
        self.assertEqual(matrix.resolve_mode({'INPUT_FULL': 'true'}), 'prerelease')
        self.assertEqual(matrix.resolve_mode({'PROVIDER_E2E_MODE': 'verify'}), 'verify')
        self.assertEqual(matrix.resolve_mode({'PROVIDER_E2E_MODE': 'api88'}), 'api88')
        self.assertEqual(matrix.resolve_mode({}), 'nightly')
        plan = matrix.assignments('api88', week=1)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]['provider_id'], 'api88')
        self.assertEqual(plan[0]['clip_id'], 'talk_zh')
        self.assertEqual(plan[0]['model'], 'deepseek-v4-flash')

    def test_budget_blocks_when_month_is_full(self):
        from provider_e2e.library import budget_check
        from provider_e2e.cost import MONTHLY_BUDGET_CNY
        plan = matrix.assignments('prerelease', week=1)
        for item in plan:
            item['model'] = item['provider']['default_model']
        rows = [{
            'recorded_at': '2099-01-15T00:00:00Z',
            'estimated_cost_cny': MONTHLY_BUDGET_CNY,
            'run_id': 'old',
            'provider': 'deepseek',
            'clip_id': 'talk_zh',
            'expect': 'succeed',
            'passed': True,
        }]
        from datetime import datetime, timezone
        check = budget_check(rows, plan, now=datetime(2099, 1, 20, tzinfo=timezone.utc))
        self.assertTrue(check['blocked'])
        self.assertGreater(check['projected_cny'], MONTHLY_BUDGET_CNY)

    def test_rolling_window_needs_minimum_sample(self):
        from provider_e2e.library import rolling_window
        small = [{
            'run_id': 'r1',
            'expect': 'succeed',
            'passed': False,
            'provider': 'deepseek',
            'clip_id': 'talk_zh',
        } for _ in range(8)]
        under = rolling_window(small, min_sample=20)
        self.assertFalse(under['enforced'])
        self.assertTrue(under['passed'])
        full = []
        for run in range(5):
            for index in range(10):
                full.append({
                    'run_id': f'r{run}',
                    'expect': 'succeed',
                    'passed': index > 0,
                    'provider': 'deepseek',
                    'clip_id': f'clip{index}',
                })
        window = rolling_window(full, min_sample=20)
        self.assertTrue(window['enforced'])
        self.assertEqual(window['should_succeed_n'], 50)
        self.assertLess(window['success_rate'], 0.95)
        self.assertFalse(window['passed'])

    def test_case_record_strips_secrets_and_urls(self):
        from provider_e2e.library import case_from_result, sanitize_case
        record = case_from_result(
            {
                'passed': True,
                'expect': 'succeed',
                'model': 'deepseek-flash',
                'error_class': 'rate_limited',
                'error_code': None,
                'duration_ms': 1200,
                'estimated_cost_cny': 0.12,
                'prompt_tokens': 100,
                'completion_tokens': 20,
                'billable_calls': 3,
                'reason': 'should never be stored',
                'api_key': 'sk-should-not-leak',
            },
            run_id='385',
            commit='abc',
            mode='nightly',
            iso_week=42,
            provider_id='deepseek',
            clip_id='talk_zh',
            model_source='default',
            base_url_host='https://api.deepseek.com/v1/chat/completions?x=1',
        )
        self.assertEqual(record['base_url_host'], 'api.deepseek.com')
        self.assertNotIn('reason', record)
        self.assertNotIn('api_key', record)
        self.assertNotIn('sk-should-not-leak', json.dumps(record))
        dirty = sanitize_case({
            **record,
            'transcript': '用户口播原文',
            'base_url_host': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        })
        self.assertNotIn('transcript', dirty)
        self.assertEqual(dirty['base_url_host'], 'dashscope.aliyuncs.com')

    def test_live_judge_fail_closed_does_not_hide_provider_failure(self):
        ok = {
            'suite': 'live',
            'status': 'completed',
            'mode': 'nightly',
            'iso_week': 1,
            'planned': [
                {'provider_id': 'deepseek', 'clip_id': 'talk_zh'},
                {'provider_id': 'deepseek', 'clip_id': 'too_short'},
            ],
            'cases': [
                {
                    'id': 'deepseek:talk_zh', 'provider_id': 'deepseek', 'clip_id': 'talk_zh',
                    'expect': 'succeed', 'passed': True,
                },
                {
                    'id': 'deepseek:too_short', 'provider_id': 'deepseek', 'clip_id': 'too_short',
                    'expect': 'block', 'passed': True, 'billable_calls_before_failure': 0,
                },
            ],
            'case_records': [{
                'run_id': 'ok', 'expect': 'succeed', 'passed': True,
                'provider': 'deepseek', 'clip_id': 'talk_zh',
            }],
        }
        self.assertTrue(judge.judge_suite(ok)['passed'])
        failed = {
            'suite': 'live',
            'status': 'completed',
            'planned': [
                {'provider_id': 'deepseek', 'clip_id': 'talk_zh'},
                {'provider_id': 'deepseek', 'clip_id': 'too_short'},
            ],
            'cases': [
                {
                    'id': 'deepseek:talk_zh', 'provider_id': 'deepseek', 'clip_id': 'talk_zh',
                    'expect': 'succeed', 'passed': False, 'error_class': 'unknown',
                },
                {
                    'id': 'deepseek:too_short', 'provider_id': 'deepseek', 'clip_id': 'too_short',
                    'expect': 'block', 'passed': True, 'billable_calls_before_failure': 0,
                },
            ],
            'case_records': [{
                'run_id': 'this', 'expect': 'succeed', 'passed': False,
                'provider': 'deepseek', 'clip_id': 'talk_zh',
            }],
        }
        verdict = judge.judge_suite(failed)
        self.assertFalse(verdict['passed'])
        self.assertFalse((verdict.get('window') or {}).get('enforced'))
        self.assertTrue((verdict.get('window') or {}).get('passed'))
        self.assertTrue(any('provider failure' in item for item in verdict['reasons']))
        combined = {
            'suite': 'combined',
            'mode': 'verify',
            'status': 'completed',
            'planned': [
                {'provider_id': 'deepseek', 'clip_id': 'talk_zh'},
                {'provider_id': 'gemini', 'clip_id': 'with_srt'},
                {'provider_id': 'deepseek', 'clip_id': 'too_short'},
            ],
            'cases': [
                {'id': 'deepseek:talk_zh', 'expect': 'succeed', 'passed': True},
                {'id': 'gemini:with_srt', 'expect': 'succeed', 'passed': False, 'error_class': 'unknown'},
                {'id': 'deepseek:too_short', 'expect': 'block', 'passed': True, 'billable_calls_before_failure': 0},
            ],
            'case_records': [{'run_id': 'v', 'expect': 'succeed', 'passed': True}],
        }
        self.assertFalse(judge.judge_suite(combined)['passed'])
        blocked = dict(failed)
        blocked['status'] = 'budget_blocked'
        blocked['reason'] = 'monthly live budget cap reached'
        self.assertFalse(judge.judge_suite(blocked)['passed'])
        library = []
        for run in range(5):
            for index in range(8):
                library.append({
                    'run_id': f'hist{run}',
                    'expect': 'succeed',
                    'passed': index > 0,
                    'provider': 'deepseek',
                    'clip_id': f'clip{index}',
                })
        windowed = judge.judge_suite(ok, library=library)
        self.assertFalse(windowed['passed'])
        self.assertTrue(any('rolling-window' in item for item in windowed['reasons']))

    def test_mask_does_not_keep_full_url_in_library_host(self):
        from provider_e2e.library import host_only
        self.assertEqual(host_only('https://infistar.ai/v1'), 'infistar.ai')
        self.assertEqual(host_only('https://api.88api.ai/v1/chat'), 'api.88api.ai')


class ProviderE2EFailClosedTests(unittest.TestCase):
    def test_historical_24_of_40_is_red_under_fail_closed(self):
        from provider_e2e.testdata import LIVE_24_OF_40_PATH, live_24_of_40_report
        report = live_24_of_40_report()
        succeed = [row for row in report['cases'] if row['expect'] == 'succeed']
        self.assertEqual(len(succeed), 40)
        self.assertEqual(sum(1 for row in succeed if row['passed']), 24)
        self.assertLess(judge.success_rate(succeed), SUCCESS_RATE_THRESHOLD)
        # Strip the case library so the rolling window is under-sampled (the
        # original GREEN path). Fail-closed must still turn the check RED.
        isolated = dict(report)
        isolated['case_records'] = []
        isolated.pop('window', None)
        verdict = judge.judge_suite(isolated)
        self.assertFalse(verdict['passed'])
        self.assertFalse((verdict.get('window') or {}).get('enforced'))
        self.assertTrue((verdict.get('window') or {}).get('passed'))
        joined = ' '.join(verdict['reasons'])
        self.assertIn('provider failure: api88', joined)
        self.assertIn('provider failure: gemini', joined)
        snapshot = json.loads(LIVE_24_OF_40_PATH.read_text(encoding='utf-8'))
        self.assertEqual(snapshot['run_id'], '38508586808')
        self.assertFalse(judge.judge_suite(snapshot)['passed'])

    def test_undersampled_verify_failures_are_red(self):
        from provider_e2e.testdata import VERIFY_UNDER_SAMPLE_PATH, verify_under_sample_report
        report = verify_under_sample_report()
        verdict = judge.judge_suite(report)
        self.assertFalse(verdict['passed'])
        self.assertFalse((verdict.get('window') or {}).get('enforced'))
        self.assertTrue((verdict.get('window') or {}).get('passed'))
        joined = ' '.join(verdict['reasons'])
        self.assertIn('provider failure: gemini', joined)
        self.assertIn('provider failure: api88', joined)
        snapshot = json.loads(VERIFY_UNDER_SAMPLE_PATH.read_text(encoding='utf-8'))
        self.assertFalse(judge.judge_suite(snapshot)['passed'])

    def test_combined_mock_plus_live_still_fail_closed(self):
        from provider_e2e.report import merge_reports
        from provider_e2e.testdata import live_24_of_40_report, mock_pass_report
        merged = merge_reports([mock_pass_report(), live_24_of_40_report()])
        verdict = judge.judge_suite(merged)
        self.assertFalse(verdict['passed'])
        joined = ' '.join(verdict['reasons'])
        self.assertIn('provider failure: api88', joined)
        self.assertIn('provider failure: gemini', joined)

    def test_workflow_fixture_mock_plus_24_of_40_fails_cli(self):
        import tempfile
        from provider_e2e.testdata import LIVE_24_OF_40_PATH, MOCK_PASS_PATH
        from provider_e2e import __main__ as cli
        with tempfile.TemporaryDirectory() as tmp:
            code = cli.main([
                '--suite', 'judge',
                '--expect-live',
                '--report', str(MOCK_PASS_PATH),
                '--report', str(LIVE_24_OF_40_PATH),
                '--out', tmp,
            ])
        self.assertEqual(code, 1)

    def test_expect_live_missing_empty_unparsable(self):
        import tempfile
        from provider_e2e.testdata import MOCK_PASS_PATH
        missing = judge.load_reports([MOCK_PASS_PATH], expect_live=True)
        self.assertFalse(judge.judge_reports(missing, expect_live=True)['passed'])
        self.assertTrue(any('missing live report' in item for item in judge.judge_reports(missing, expect_live=True)['reasons']))
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / 'live' / 'report.json'
            empty.parent.mkdir()
            empty.write_text('', encoding='utf-8')
            loaded = judge.load_report_file(empty)
            self.assertEqual(loaded['status'], 'empty')
            self.assertFalse(judge.judge_suite(loaded)['passed'])
            broken = Path(tmp) / 'live' / 'broken.json'
            broken.write_text('{not-json', encoding='utf-8')
            parsed = judge.load_report_file(broken)
            self.assertEqual(parsed['status'], 'unparsable')
            self.assertFalse(judge.judge_suite(parsed)['passed'])
            absent = judge.load_report_file(Path(tmp) / 'live' / 'nope.json')
            self.assertEqual(absent['status'], 'missing')

    def test_incomplete_planned_matrix_is_red(self):
        report = {
            'suite': 'live',
            'status': 'completed',
            'planned': [
                {'provider_id': 'deepseek', 'clip_id': 'talk_zh'},
                {'provider_id': 'gemini', 'clip_id': 'with_srt'},
                {'provider_id': 'deepseek', 'clip_id': 'too_short'},
            ],
            'cases': [
                {'id': 'deepseek:talk_zh', 'expect': 'succeed', 'passed': True},
            ],
        }
        verdict = judge.judge_suite(report)
        self.assertFalse(verdict['passed'])
        self.assertTrue(any('incomplete live results' in item for item in verdict['reasons']))
        self.assertIn('gemini:with_srt', verdict['completeness']['missing'])

    def test_diagnose_extracts_http_status_and_redacts(self):
        import tempfile
        from provider_e2e.diagnose import classify_http, from_backend_log, from_workspace, merge_diagnosis
        workspace = {
            'generation': {},
            'analysis': {
                'error': 'OpenAI调用失败 Error code: 404 model does not exist api_key=sk-secretvalue99',
                'http_status': 404,
            },
        }
        extracted = from_workspace(workspace)
        self.assertEqual(extracted['http_status'], 404)
        self.assertEqual(extracted['error_class'], UpstreamErrorType.MODEL_NOT_FOUND.value)
        self.assertNotIn('sk-secretvalue99', extracted['log_excerpt'] or '')
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'backend.log'
            log.write_text(
                'Gemini调用失败 Error code: 404 The model `gemini-2.0-flash` does not exist\n',
                encoding='utf-8',
            )
            logged = from_backend_log(log)
        self.assertEqual(logged['http_status'], 404)
        self.assertEqual(logged['error_class'], UpstreamErrorType.MODEL_NOT_FOUND.value)
        merged = merge_diagnosis({'http_status': None, 'error_class': None}, logged)
        self.assertEqual(merged['http_status'], 404)
        self.assertEqual(classify_http(404), UpstreamErrorType.BAD_ENDPOINT.value)
        self.assertEqual(classify_http(401), UpstreamErrorType.INVALID_KEY.value)

    def test_acceptance_docs_freeze_the_gate(self):
        acceptance = (ROOT / 'docs/TESTING_ACCEPTANCE.md').read_text(encoding='utf-8')
        self.assertIn('不要只靠这一条探针放行', acceptance)
        changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        self.assertIn('gemini-3.5-flash-lite', changelog)
        self.assertIn('api.88api.ai/v1', changelog)
        self.assertIn('deepseek-v4-flash', changelog)


if __name__ == '__main__':
    unittest.main()


class ProviderE2EPaidCallCountTests(unittest.TestCase):
    """#369 / #373: run_case counts paid calls from the observer, the ledger, or a proven import rejection;
    anything else is unknown and a should-block case with an unknown count fails."""

    SOURCE_422 = json.dumps({'detail': {'code': 'source_too_short', 'message': 'x'}})

    def _run(self, *, import_effect, observer=None, poll=None, expect='block'):
        from provider_e2e import harness
        from provider_e2e.http_util import HttpError
        data_dir = Path(tempfile.mkdtemp(prefix='pe2e-count-'))

        class FakeBackend:
            log_path = None
            def __init__(self, *a, **k): pass
            def start(self): return 'http://backend'
            def stop(self): pass
            def kill(self): pass

        def do_import(base_url, fixture):
            return import_effect(data_dir, HttpError)
        with patch.object(harness, 'DesktopBackend', FakeBackend), patch.object(harness, 'write_data_dir', lambda *a, **k: None), \
                patch.object(harness, 'import_project', do_import), \
                patch.object(harness, 'poll_workspace', poll or (lambda *a, **k: {'generation': {'status': 'failed', 'error_code': 'source_too_short', 'failure_stage': 'INGEST'}, 'analysis': {}})):
            return harness.run_case(case_id='c', label='c', expect=expect, fixture={'id': 'too_short', 'block_code': 'source_too_short'},
                                    data_dir=data_dir, connection={'base_url': 'u', 'api_key': 'k', 'provider': 'p', 'model': 'm'},
                                    python=sys.executable, timeout=5, mock_server=observer)

    @staticmethod
    def _observer(events):
        class Obs:
            class state:
                @staticmethod
                def snapshot():
                    return {'events': list(events)}
        return Obs

    def test_live_source_422_without_new_project_is_zero_import_rejected(self):
        row = self._run(import_effect=lambda d, E: (_ for _ in ()).throw(E(422, self.SOURCE_422)))
        self.assertEqual((row['billable_calls_before_failure'], row['count_source']), (0, 'import_rejected'))
        self.assertTrue(row['passed'])
        self.assertTrue(judge.judge_suite({'status': 'ok', 'cases': [row]})['should_block_passed'])

    def test_project_created_but_422_is_unknown_and_fails(self):
        def effect(d, E):
            (d / 'projects' / 'leaked').mkdir(parents=True)
            raise E(422, self.SOURCE_422)
        row = self._run(import_effect=effect)
        self.assertIsNone(row['billable_calls_before_failure'])
        self.assertFalse(row['passed'])

    def test_project_swapped_same_count_is_unknown(self):
        def effect(d, E):
            (d / 'projects' / 'old').rename(d / 'projects' / 'new')
            raise E(422, self.SOURCE_422)
        from provider_e2e import harness
        before = harness.project_ids
        def seeded(data_dir):
            (data_dir / 'projects' / 'old').mkdir(parents=True, exist_ok=True) if not (data_dir / 'projects' / 'new').exists() else None
            return before(data_dir)
        with patch.object(harness, 'project_ids', seeded):
            row = self._run(import_effect=effect)
        self.assertIsNone(row['billable_calls_before_failure'], 'compared by id, not by count')

    def test_project_removed_after_import_is_unknown(self):
        """#407: fewer projects after the import (one deleted) is not a proven rejection; a subset check fails this."""
        from provider_e2e import harness
        self.assertEqual(harness.import_rejected_count('source_too_short', frozenset({'a', 'b'}), frozenset({'a'})), (None, None))
        self.assertEqual(harness.import_rejected_count('source_too_short', frozenset({'a', 'b'}), frozenset({'a', 'b'})), (0, 'import_rejected'))

        def effect(d, E):
            (d / 'projects' / 'gone').rmdir()
            raise E(422, self.SOURCE_422)
        before = harness.project_ids
        seeded_once = []
        def seeded(data_dir):
            if not seeded_once:
                seeded_once.append(1)
                (data_dir / 'projects' / 'kept').mkdir(parents=True, exist_ok=True)
                (data_dir / 'projects' / 'gone').mkdir(parents=True, exist_ok=True)
            return before(data_dir)
        with patch.object(harness, 'project_ids', seeded):
            row = self._run(import_effect=effect)
        self.assertIsNone(row['billable_calls_before_failure'], 'a project disappeared: unknown, not 0')
        self.assertFalse(row['passed'])

    def test_422_without_source_code_is_not_a_block(self):
        row = self._run(import_effect=lambda d, E: (_ for _ in ()).throw(E(422, json.dumps({'detail': {'code': 'whisper_not_installed'}}))))
        self.assertFalse(row['passed'])
        self.assertIsNone(row['billable_calls_before_failure'])

    def test_observer_wiring_counts_a_call_before_the_422(self):
        obs = self._observer([{'path': '/v1/chat/completions'}])
        events = obs.state.snapshot
        calls = {'n': 0}
        def snap():
            calls['n'] += 1
            return {'events': [] if calls['n'] == 1 else [{'path': '/v1/chat/completions'}]}
        obs.state.snapshot = staticmethod(snap)
        row = self._run(import_effect=lambda d, E: (_ for _ in ()).throw(E(422, self.SOURCE_422)), observer=obs)
        self.assertEqual(row['billable_calls_before_failure'], 1)
        self.assertEqual(row['count_source'], 'observer')
        self.assertFalse(row['passed'])
        del events

    def test_ledger_wiring_counts_the_project_ledger(self):
        def effect(d, E):
            meta = d / 'projects' / 'p1' / 'metadata'; meta.mkdir(parents=True)
            (meta / 'llm_usage.jsonl').write_text('{"kind":"chat"}\n{"kind":"timing"}\n{"kind":"chat"}\n')
            return 'p1'
        row = self._run(import_effect=effect)
        self.assertEqual((row['billable_calls_before_failure'], row['count_source']), (2, 'ledger'))
        self.assertFalse(row['passed'])

    def test_missing_or_broken_ledger_is_unknown(self):
        from provider_e2e.harness import billable_calls_before_failure
        d = Path(tempfile.mkdtemp())
        self.assertIsNone(billable_calls_before_failure(d, 'p'))
        meta = d / 'projects' / 'p' / 'metadata'; meta.mkdir(parents=True)
        (meta / 'llm_usage.jsonl').write_text('{"kind":"chat"}\nnot json\n')
        self.assertIsNone(billable_calls_before_failure(d, 'p'))
        (meta / 'llm_usage.jsonl').write_text('')
        self.assertEqual(billable_calls_before_failure(d, 'p'), 0)
        row = self._run(import_effect=lambda dd, E: (dd / 'projects' / 'p2').mkdir(parents=True) or 'p2')
        self.assertIsNone(row['billable_calls_before_failure'], 'project exists, ledger missing -> unknown')
        self.assertFalse(row['passed'])

    def test_judge_rejects_non_integer_counts(self):
        for bad in ('oops', 0.9, 0.0, True, -1, None, '0'):
            row = {'id': 'b', 'expect': 'block', 'passed': True, 'billable_calls_before_failure': bad, 'billable_calls': bad}
            self.assertFalse(judge.judge_suite({'status': 'ok', 'cases': [row]})['should_block_passed'], repr(bad))
        good = {'id': 'b', 'expect': 'block', 'passed': True, 'billable_calls_before_failure': 0}
        self.assertTrue(judge.judge_suite({'status': 'ok', 'cases': [good]})['should_block_passed'])

    def test_mock_observer_zero_does_not_rescue_a_created_project(self):
        obs = self._observer([])
        def effect(d, E):
            (d / 'projects' / 'leaked').mkdir(parents=True)
            raise E(422, self.SOURCE_422)
        row = self._run(import_effect=effect, observer=obs)
        self.assertIsNone(row['billable_calls_before_failure'])
        self.assertFalse(row['passed'])
        ok = self._run(import_effect=lambda d, E: (_ for _ in ()).throw(E(422, self.SOURCE_422)), observer=self._observer([]))
        self.assertEqual((ok['billable_calls_before_failure'], ok['count_source']), (0, 'import_rejected'))
