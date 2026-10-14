import json
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from provider_e2e import SUCCESS_RATE_THRESHOLD, judge, mask, matrix, mock_openai
from provider_e2e.report import merge_reports
from provider_e2e.settings import live_ready
import release_acceptance as gate


class ProviderE2EContractTests(unittest.TestCase):
    def test_matrix_has_eight_success_and_two_blocks(self):
        succeed = matrix.assets(expect='succeed')
        blocked = matrix.assets(expect='block')
        self.assertEqual(len(succeed), 8)
        self.assertEqual(len(blocked), 2)
        self.assertEqual({item['id'] for item in blocked}, {'too_short', 'no_audio'})
        self.assertLess(matrix.TOO_SHORT_DURATION_SEC, 20)
        self.assertGreaterEqual(matrix.SUCCESS_DURATION_SEC, 20)
        self.assertTrue(all(item['duration_sec'] >= 20 for item in succeed))
        labels = {item['label'] for item in succeed}
        for name in ('中文口播', '中文访谈', '英文播客', '带字幕', '竖屏', '游戏', '体育', '纯音乐'):
            self.assertIn(name, labels)
        self.assertEqual({item['id']: item['block_code'] for item in blocked}, {
            'too_short': 'source_too_short',
            'no_audio': 'source_no_audio',
        })

    def test_live_providers_and_faults(self):
        ids = {item['id'] for item in matrix.live_providers()}
        self.assertEqual(ids, {'api88', 'deepseek', 'gemini'})
        faults = {item['fault'] for item in matrix.faults()}
        self.assertEqual(faults, {'429', '503', 'disconnect', 'kill'})

    def test_release_acceptance_requires_provider_e2e_job(self):
        self.assertIn('provider-e2e', gate.BUILD_JOBS)
        workflow = (ROOT / '.github/workflows/provider-e2e-gate.yml').read_text(encoding='utf-8')
        desktop = (ROOT / '.github/workflows/desktop-build.yml').read_text(encoding='utf-8')
        self.assertIn('environment: provider-e2e', workflow)
        self.assertIn('workflow_call', workflow)
        self.assertIn('head.repo.full_name == github.repository', workflow)
        self.assertIn('scripts/provider_e2e/**', workflow)
        self.assertIn('fork-skip', workflow)
        self.assertIn('uses: ./.github/workflows/provider-e2e-gate.yml', desktop)
        self.assertIn('needs: [candidate-gate]', desktop)
        self.assertIn('needs.provider-e2e.result == \'success\'', desktop)

    def test_mask_redacts_keys(self):
        text = mask.redact_text('Authorization: Bearer sk-abc123456789 and api_key=supersecretvalue')
        self.assertNotIn('sk-abc123456789', text)
        self.assertNotIn('supersecretvalue', text)
        self.assertIn('***', text)
        hidden = mask.redact({'api_key': 'sk-live-should-hide', 'ok': 'plain'}, ['sk-live-should-hide'])
        self.assertEqual(hidden['api_key'], '***')
        self.assertEqual(hidden['ok'], 'plain')

    def test_live_ready_skips_without_secrets(self):
        provider = matrix.live_providers()[0]
        self.assertFalse(live_ready(provider, {})['ready'])
        ready = live_ready(provider, {provider['secret']: 'sk-test-key'})
        self.assertTrue(ready['ready'])
        self.assertEqual(ready['model'], provider['default_model'])

    def test_judge_thresholds(self):
        succeed = [{'expect': 'succeed', 'passed': True} for _ in range(8)]
        blocked = [
            {'expect': 'block', 'passed': True, 'billable_calls': 0},
            {'expect': 'block', 'passed': True, 'billable_calls': 0},
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
            {'expect': 'block', 'passed': True, 'billable_calls': 1},
            {'expect': 'block', 'passed': True, 'billable_calls': 0},
        ]
        self.assertFalse(judge.judge_suite(billed)['passed'])

        skipped = {'status': 'skipped', 'reason': 'secrets unset', 'cases': []}
        self.assertTrue(judge.judge_suite(skipped)['skipped'])
        self.assertTrue(judge.judge_reports([report, skipped])['passed'])

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
            second = json.loads(chat(root + '/fault/429/v1/chat/completions').read().decode())
            self.assertIn('final_score', second['choices'][0]['message']['content'])

            with self.assertRaises(HTTPError) as unavailable:
                chat(root + '/fault/503/v1/chat/completions')
            self.assertEqual(unavailable.exception.code, 503)
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
        self.assertIn('API88_API_KEY', doc)
        self.assertIn('¥500–1000', doc)
        self.assertIn('PROVIDER_E2E_GATE.md', (ROOT / 'docs/README.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
