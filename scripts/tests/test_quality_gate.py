import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import quality_gate


class QualityGateTests(unittest.TestCase):
    def test_backend_checks_run_reload_in_order_and_the_unfiltered_directory(self):
        commands = {name: command for name, command, _ in quality_gate.checks('backend', sys.executable)}
        self.assertIn('backend/tests/test_llm_hot_reload.py', commands['llm_hot_reload_tests'])
        self.assertIn('backend/tests', commands['backend_tests'])
        for name in ('llm_hot_reload_tests', 'backend_tests'):
            self.assertIn('backend/pytest.ini', commands[name])
            self.assertIn('addopts=', commands[name])
            self.assertFalse(set(commands[name][3:]) & {'-k', '-m', '--ignore', '--deselect', '-n'})

    def test_redline_frontend_loads_the_same_strict_setup_as_npm_test(self):
        commands = {name: command for name, command, _ in quality_gate.checks('redline', sys.executable)}
        command = commands['redline_frontend']
        self.assertEqual(command[:4], ['node', '--require', './frontend/tests/setup.cjs', '--test'])
        self.assertTrue((quality_gate.ROOT / command[2]).is_file())
        self.assertTrue(any(arg.endswith('.test.cjs') for arg in command[4:]))
        package = json.loads((quality_gate.ROOT / 'frontend/package.json').read_text())
        self.assertIn('--require ./tests/setup.cjs', package['scripts']['test'])

    def test_backend_evidence_rejects_missing_modules_and_filtered_reload_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'tests.xml'
            cases = ''.join(f'<testcase classname="tests.test_llm_hot_reload" name="{name}"/>' for name in (
                'test_reload_pins_connection_model_and_candidates[False]',
                'test_reload_pins_connection_model_and_candidates[True]',
                'test_reload_false_then_true_with_coarse_write_times',
            ))
            path.write_text('<testsuite>' + cases + '</testsuite>')
            coverage = quality_gate.pytest_coverage(path, {'test_llm_hot_reload', 'test_other'})
            self.assertEqual(coverage['missing_modules'], ['test_other'])
            self.assertEqual(coverage['missing_reload_cases'], [])
            path.write_text('<testsuite>' + cases.replace('[True]', '[filtered]') + '</testsuite>')
            self.assertEqual(quality_gate.pytest_coverage(path, {'test_llm_hot_reload'})['missing_reload_cases'],
                             ['test_reload_pins_connection_model_and_candidates[True]'])

    def test_failure_survives_later_success_and_data_is_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / 'user-data'
            original.mkdir()
            marker = original / 'privacy.json'
            marker.write_text('preserve-user-data')
            report = Path(temp) / 'report.json'
            environments = []

            def execute(command, **kwargs):
                environments.append(kwargs['env'].copy())
                self.assertNotEqual(kwargs['env']['AUTOCLIP_DATA_DIR'], str(original))
                self.assertTrue(Path(kwargs['env']['AUTOCLIP_DATA_DIR']).is_dir())
                return subprocess.CompletedProcess(command, 1 if command[-1] == 'lint' else 0)

            with patch.dict(os.environ, {'PYTEST_ADDOPTS': '-k nothing', 'PYTEST_PLUGINS': 'fixture', 'AUTOCLIP_DATA_DIR': str(original), 'SENTRY_DSN': 'fixture', 'OPENAI_API_KEY': 'fixture-key', 'API_DASHSCOPE_API_KEY': 'fixture-key'}), \
                 patch('quality_gate.subprocess.check_output', side_effect=['a' * 40, '']), \
                 patch('quality_gate.subprocess.run', side_effect=execute):
                self.assertEqual(quality_gate.run('frontend', report, sys.executable), 1)
            value = json.loads(report.read_text())
            self.assertEqual(value['status'], 'failed')
            self.assertEqual([row['status'] for row in value['checks']], ['failed', 'passed', 'passed', 'passed'])
            self.assertEqual(marker.read_text(), 'preserve-user-data')
            self.assertEqual(len(environments), 4)
            self.assertTrue(all(row['SENTRY_DSN'] == '' and row['SENTRY_UPLOAD_SOURCEMAPS'] == 'false' for row in environments))
            self.assertTrue(all(row['OPENAI_API_KEY'] == '' and row['API_DASHSCOPE_API_KEY'] == '' for row in environments))
            self.assertTrue(all(row['REDIS_URL'] == 'redis://127.0.0.1:1/0' for row in environments))
            self.assertTrue(all('PYTEST_ADDOPTS' not in row and 'PYTEST_PLUGINS' not in row for row in environments))

    def test_missing_tool_is_a_failed_check(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('quality_gate.subprocess.check_output', side_effect=['a' * 40, '']), \
             patch('quality_gate.subprocess.run', side_effect=FileNotFoundError):
            report = Path(temp) / 'report.json'
            self.assertEqual(quality_gate.run('contracts', report, sys.executable), 1)
            self.assertEqual(json.loads(report.read_text())['status'], 'failed')

    def test_missing_runtime_regression_is_not_an_allowed_skip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'tests.xml'
            path.write_text('<testsuite><testcase classname="backend.tests.test_whisper_local_subtitle" name="test_empty_audio"><skipped message="numpy missing"/></testcase></testsuite>')
            self.assertEqual(quality_gate.pytest_skips(path), [{'test': 'test_empty_audio', 'allowed': False}])
            path.write_text('<testsuite><testcase classname="backend.tests.test_upload_post_publisher" name="test_live_upload_post_rejects_unknown_key"><skipped/></testcase></testsuite>')
            self.assertEqual(quality_gate.pytest_skips(path), [{'test': 'test_live_upload_post_rejects_unknown_key', 'allowed': True}])
            path.write_text('<testsuite><testcase classname="backend.tests.test_windows_asyncio" name="test_windows_real_reset_and_subprocess"><skipped/></testcase></testsuite>')
            with patch('quality_gate.os.name', 'nt'):
                self.assertFalse(quality_gate.pytest_skips(path)[0]['allowed'])
            path.write_text('<testsuite><testcase classname="backend.tests.test_whisper_snapshot_repair" name="test_real_hub_copy_layout_does_not_replace_an_existing_file"><skipped message="could not import huggingface_hub"/></testcase></testsuite>')
            self.assertEqual(quality_gate.pytest_skips(path), [{'test': 'test_real_hub_copy_layout_does_not_replace_an_existing_file', 'allowed': True}])
            path.write_text('<testsuite><testcase classname="backend.tests.test_whisper_snapshot_repair" name="test_corrupt_file_is_deleted_and_redownloaded_without_force"><skipped/></testcase></testsuite>')
            self.assertFalse(quality_gate.pytest_skips(path)[0]['allowed'])


if __name__ == '__main__':
    unittest.main()
