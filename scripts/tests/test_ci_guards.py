"""Locks for review-round filenames, review ids in notes, and catalog error codes."""
import io
import json
import os
from contextlib import redirect_stderr
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_guards
import quality_gate

ITEM = 'I' + '575'


class CiGuardTests(unittest.TestCase):
    def test_status_codes_versions_and_ordinary_words_are_not_review_ids(self):
        for text in ('HTTP 500', 'status 404', 'version 1.5.7', 'Render the page', 'done', 'dongle'):
            self.assertIsNone(ci_guards._REVIEW_ID.search(text), text)

    def test_casefold_names_do_not_share_a_resolver_hit(self):
        spec = 'frontend/src/features/diagnostics/FailureHint'
        broken = [spec + '.tsx', 'frontend/src/features/diagnostics/failureHint.ts']
        self.assertTrue(ci_guards.casefold_collisions(broken))
        self.assertEqual(ci_guards.resolve_casefolded(spec, broken), broken[1])
        fixed = [spec + '.tsx', 'frontend/src/features/diagnostics/failureHintPolicy.ts']
        self.assertEqual(ci_guards.casefold_collisions(fixed), [])
        self.assertEqual(ci_guards.resolve_casefolded(spec, fixed), fixed[0])
        self.assertTrue(ci_guards.casefold_collisions(['docs/Readme.md', 'docs/readme.md']))
        self.assertEqual(ci_guards.casefold_collisions(['a/Foo.ts', 'b/foo.ts']), [])
        self.assertEqual(ci_guards.casefold_collisions(ci_guards.tracked_paths()), [])

    def test_review_round_filenames(self):
        self.assertTrue(ci_guards._REVIEW_FILE.match('test_' + 'r12.py'))
        self.assertTrue(ci_guards._REVIEW_FILE.match('test_' + 'i575.ts'))
        self.assertTrue(ci_guards._REVIEW_FILE.match('r158-foo.test.cjs'))
        for name in ('test_render.py', 'test_import.py', 'test_issue.py', 'retry-lineage.test.cjs'):
            self.assertIsNone(ci_guards._REVIEW_FILE.match(name), name)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / 'backend' / 'tests'
            tests.mkdir(parents=True)
            banned = tests / ('test_r' + '9.py')
            banned.write_text('x = 1\n', encoding='utf-8')
            (tests / 'test_render.py').write_text('x = 1\n', encoding='utf-8')
            (tests / '__pycache__').mkdir()
            (tests / '__pycache__' / ('test_r' + '9.pyc')).write_bytes(b'')
            self.assertEqual(ci_guards.review_filenames(root), [str(banned.relative_to(root))])

    def test_notes_and_unknown_error_codes(self):
        catalog = ci_guards._catalog_error_codes()
        mcp = ci_guards._mcp_error_codes()
        self.assertIn('timeout', catalog)
        self.assertIn('cancelled', mcp)
        for code in ('timeout', 'cancelled', 'VALIDATION_ERROR', 'http_429'):
            self.assertTrue(ci_guards.error_code_literal_allowed(code, catalog, mcp), code)
        self.assertIn('bad_endpoint', catalog)
        self.assertFalse(ci_guards.error_code_literal_allowed('not_a_real_code', catalog, mcp))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / 'backend'
            sample.mkdir()
            target = sample / 'sample.py'
            target.write_text("error_code = 'not_a_real_code'\n", encoding='utf-8')
            self.assertTrue(any('not_a_real_code' in row for row in ci_guards.error_code_literals(root)))
            target.write_text("error_code = 'timeout'\n", encoding='utf-8')
            self.assertEqual(ci_guards.error_code_literals(root), [])
            target.write_text("payload = {'error_code': 'not_a_real_code'}\n", encoding='utf-8')
            self.assertTrue(any('not_a_real_code' in row for row in ci_guards.error_code_literals(root)))
            target.write_text('payload = {"errorCode": "bad_endpoint"}\n', encoding='utf-8')
            self.assertEqual(ci_guards.error_code_literals(root), [])
            table = next(codes for label, codes in ci_guards._catalog_error_sets() if label.endswith('connection_test_error_code'))
            literal = ', '.join(repr(code) for code in sorted(table))
            target.write_text(f'COPIED = ({literal},)\n', encoding='utf-8')
            self.assertTrue(any('connection_test_error_code' in row for row in ci_guards.handwritten_error_code_sets(root)))
            caused = next(codes for label, codes in ci_guards._catalog_error_sets() if label.endswith('user_caused_error_codes'))
            caused_literal = ', '.join(repr(code) for code in sorted(caused))
            target.write_text(f'USER = ({caused_literal},)\n', encoding='utf-8')
            self.assertTrue(any('user_caused_error_codes' in row for row in ci_guards.handwritten_error_code_sets(root)))
            target.write_text("MODEL = {'timeout', 'connection'}\n", encoding='utf-8')
            self.assertEqual(ci_guards.handwritten_error_code_sets(root), [])
            target.write_text(f'x = 1  # {ITEM} keep this reason\n', encoding='utf-8')
            self.assertEqual(ci_guards.review_notes(root), [f'{target.relative_to(root)}:1'])
            js = root / 'frontend' / 'src'
            js.mkdir(parents=True)
            note = js / 'note.ts'
            note.write_text(f'export const x = 1 // {ITEM} keep\n', encoding='utf-8')
            self.assertIn(f'{note.relative_to(root)}:1', ci_guards.review_notes(root))

    def test_catalog_sentence_copies_are_flagged(self):
        self.assertEqual(ci_guards.catalog_sentence_copies(), [])
        sentence = '应用刚重启，这次制作已中断，请重试。'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog = root / 'backend' / 'core'
            catalog.mkdir(parents=True)
            (catalog / 'failure_messages.json').write_text(
                json.dumps({'service_restarted': sentence}), encoding='utf-8')
            sample = root / 'backend' / 'sample.py'
            sample.write_text(f'error = {sentence!r}\n', encoding='utf-8')
            self.assertTrue(any('sample.py' in row for row in ci_guards.catalog_sentence_copies(root)))
            sample.write_text("error = sentence('service_restarted')\n", encoding='utf-8')
            self.assertEqual(ci_guards.catalog_sentence_copies(root), [])
            sample.write_text(f'# {sentence}\nnote = {("prefix " + sentence)!r}\n', encoding='utf-8')
            self.assertEqual(ci_guards.catalog_sentence_copies(root), [])
            tests = root / 'backend' / 'tests'
            tests.mkdir()
            (tests / 'test_copy.py').write_text(f'error = {sentence!r}\n', encoding='utf-8')
            self.assertEqual(ci_guards.catalog_sentence_copies(root), [])

    def test_summary_lists_buckets_and_does_not_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = Path(temp) / 'summary.md'
            counts = {'product': [4, 1], 'tests': [2, 9], 'docs': [1, 0], 'other': [0, 0]}
            with patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': str(summary)}):
                ci_guards.write_summary(counts)
                ci_guards.write_summary(None)
            text = summary.read_text(encoding='utf-8')
        self.assertIn('产品', text)
        self.assertIn('测试', text)
        self.assertIn('文档', text)
        self.assertNotIn('其他', text)
        self.assertIn('未能和基线比较', text)
        self.assertEqual(ci_guards._bucket('backend/core/store.py'), 'product')
        self.assertEqual(ci_guards._bucket('backend/tests/test_store_lock.py'), 'tests')
        self.assertEqual(ci_guards._bucket('docs/TESTING_ACCEPTANCE.md'), 'docs')
        self.assertEqual(ci_guards._bucket('frontend/tests/api-retry.test.cjs'), 'tests')

    def test_directory_casefold_catches_parent_segments_only(self):
        self.assertEqual(ci_guards.directory_casefold_collisions([
            'frontend/src/features/diagnostics/FailureHint.tsx',
            'frontend/src/features/diagnostics/failureHint.ts',
        ]), [])
        self.assertEqual(ci_guards.directory_casefold_collisions(['docs/Readme.md', 'docs/readme.md']), [])
        self.assertEqual(ci_guards.directory_casefold_collisions(['a/Foo.ts', 'b/foo.ts']), [])
        self.assertEqual(ci_guards.directory_casefold_collisions(['Foo/a.ts', 'Foo/b.ts']), [])
        different = ci_guards.directory_casefold_collisions(['Foo/a.ts', 'foo/b.ts'])
        self.assertTrue(any('Foo' in row and 'foo' in row for row in different), different)
        nested = ci_guards.directory_casefold_collisions([
            'frontend/src/features/diagnostics/FailureHint.tsx',
            'frontend/src/Features/diagnostics/other.ts',
        ])
        self.assertTrue(any('features' in row and 'Features' in row for row in nested), nested)
        file_dir = ci_guards.directory_casefold_collisions(['Foo', 'foo/a.ts'])
        self.assertTrue(any('Foo' in row and 'foo' in row for row in file_dir), file_dir)
        self.assertEqual(ci_guards.directory_casefold_collisions(ci_guards.tracked_paths()), [])

    def test_global_urlopen_capture_must_drop_bodies_without_an_event(self):
        broken = '''
import json
def test_settle(monkeypatch):
    monkeypatch.setenv("AUTOCLIP_POSTHOG_KEY", "phc_test")
    posted = []
    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        raise OSError("tests do not send")
    monkeypatch.setattr("urllib.request.urlopen", fake)
    body = posted[0]
    assert body["event"] == "studio_generation_finished"
'''
        counted = '''
import json
def test_rejected(monkeypatch):
    monkeypatch.setenv("AUTOCLIP_POSTHOG_KEY", "phc_test")
    calls = []
    def rejected(req, timeout=0):
        calls.append(json.loads(req.data.decode()))
        raise OSError("no")
    monkeypatch.setattr("urllib.request.urlopen", rejected)
    assert len(calls) == 1
'''
        guarded = '''
import json
def test_settle(monkeypatch):
    monkeypatch.setenv("AUTOCLIP_POSTHOG_KEY", "phc_test")
    posted = []
    def fake(req, timeout=0):
        body = json.loads(req.data.decode())
        if isinstance(body, dict) and isinstance(body.get("event"), str):
            posted.append(body)
        raise OSError("tests do not send")
    monkeypatch.setattr("urllib.request.urlopen", fake)
    assert posted[0]["event"] == "studio_generation_finished"
'''
        module_local = '''
import json
def test_post(monkeypatch):
    posted = []
    def urlopen(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
    monkeypatch.setattr(telem.urllib.request, "urlopen", urlopen)
    assert posted[0]["event"] == "studio_generation_finished"
'''
        vision = '''
import json
import urllib.request
def test_vision(monkeypatch):
    sent = []
    def fake_urlopen(req, timeout=None):
        payload = json.loads(req.data)
        sent.append(payload)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert sent[0]["model"] == "vision"
'''
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / 'backend' / 'tests' / 'test_mix.py'
            sample.parent.mkdir(parents=True)
            sample.write_text(broken, encoding='utf-8')
            flagged = ci_guards.global_urlopen_telemetry_mixes(root)
            self.assertTrue(any('test_mix.py' in row and 'PostHog' in row for row in flagged), flagged)
            sample.write_text(counted, encoding='utf-8')
            self.assertTrue(ci_guards.global_urlopen_telemetry_mixes(root))
            sample.write_text(guarded, encoding='utf-8')
            self.assertEqual(ci_guards.global_urlopen_telemetry_mixes(root), [])
            sample.write_text(module_local, encoding='utf-8')
            self.assertEqual(ci_guards.global_urlopen_telemetry_mixes(root), [])
            sample.write_text(vision, encoding='utf-8')
            self.assertEqual(ci_guards.global_urlopen_telemetry_mixes(root), [])
        self.assertEqual(ci_guards.global_urlopen_telemetry_mixes(), [])

    def test_new_guards_name_the_root_cause(self):
        stderr = io.StringIO()
        with patch.object(ci_guards, 'review_filenames', return_value=[]), \
                patch.object(ci_guards, 'review_notes', return_value=[]), \
                patch.object(ci_guards, 'error_code_literals', return_value=[]), \
                patch.object(ci_guards, 'handwritten_error_code_sets', return_value=[]), \
                patch.object(ci_guards, 'catalog_sentence_copies', return_value=[]), \
                patch.object(ci_guards, 'tracked_paths', return_value=['Foo/a.ts', 'foo/b.ts']), \
                patch.object(ci_guards, 'global_urlopen_telemetry_mixes', return_value=[
                    'backend/tests/test_mix.py:4: 未过滤的 JSON body 被当成 PostHog 事件',
                ]), \
                patch.dict(os.environ, {'GITHUB_BASE_REF': ''}):
            with redirect_stderr(stderr):
                code = ci_guards.main()
        text = stderr.getvalue()
        self.assertEqual(code, 1)
        self.assertIn('casefold', text)
        self.assertIn('Foo', text)
        self.assertIn('foo', text)
        self.assertIn('不要 patch 进程全局的 urllib.request.urlopen', text)
        self.assertIn('test_mix.py:4', text)

    def test_contracts_job_runs_the_guard(self):
        commands = {name: command for name, command, _ in quality_gate.checks('contracts', sys.executable)}
        self.assertEqual(commands['ci_guards'][-1], 'scripts/ci_guards.py')
        backend = {name: command for name, command, _ in quality_gate.checks('backend', sys.executable)}
        self.assertIn('scripts/ci_guards.py', backend['python_correctness'])

    def test_tauri_invoke_contracts_blocks_unregistered_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'src-tauri/src').mkdir(parents=True)
            (root / 'frontend/src/desktop').mkdir(parents=True)
            (root / 'src-tauri/src/lib.rs').write_text(
                'tauri::generate_handler![restart_backend_service, reveal_in_folder]\n',
                encoding='utf-8',
            )
            (root / 'frontend/src/desktop/Banner.tsx').write_text(
                "invoke('restart_backend_service'); invoke('missing_cmd');\n",
                encoding='utf-8',
            )
            hits = ci_guards.tauri_invoke_contracts(root)
            self.assertEqual(len(hits), 1)
            self.assertIn('missing_cmd', hits[0])

    def test_orphaned_ui_components_blocks_new_dead_feature_components(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'frontend/src/features/studio').mkdir(parents=True)
            (root / 'frontend/src/features/studio/UsedCard.tsx').write_text('export default function UsedCard() {}\n', encoding='utf-8')
            (root / 'frontend/src/features/studio/DeadCard.tsx').write_text('export default function DeadCard() {}\n', encoding='utf-8')
            (root / 'frontend/src/features/studio/Page.tsx').write_text("import UsedCard from './UsedCard'\n", encoding='utf-8')
            hits = ci_guards.orphaned_ui_components(root)
            self.assertTrue(any('DeadCard.tsx' in h for h in hits))
            self.assertFalse(any('UsedCard.tsx' in h for h in hits))


if __name__ == '__main__':
    unittest.main()
