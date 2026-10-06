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

            with patch.dict(os.environ, {'AUTOCLIP_DATA_DIR': str(original), 'SENTRY_DSN': 'fixture', 'OPENAI_API_KEY': 'fixture-key', 'API_DASHSCOPE_API_KEY': 'fixture-key'}), \
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


if __name__ == '__main__':
    unittest.main()
