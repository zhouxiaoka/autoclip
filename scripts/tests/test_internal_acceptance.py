import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import internal_acceptance as gate
import release_acceptance as release


class InternalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        self.version, self.commit = '1.6.0', 'a' * 40
        self.now = dt.datetime.now(dt.timezone.utc)
        self.built = self.now - dt.timedelta(hours=2)
        for name in ('AutoClip Desktop.dmg', 'AutoClip.app.tar.gz', 'AutoClip-x64-setup.exe',
                     'AutoClip.app.tar.gz.sig', 'AutoClip-x64-setup.exe.sig'):
            (self.assets / name).write_text('package fixture', encoding='utf-8')
        (self.assets / gate.PROVENANCE).write_text(json.dumps(gate.provenance(self.version, self.commit, self.assets, 123)), encoding='utf-8')
        (self.root / 'evidence.md').write_text('Sanitized internal acceptance fixture', encoding='utf-8')
        self.manifest = gate.template(self.version, self.commit, self.assets, 123)
        completed = (self.built + dt.timedelta(hours=1)).isoformat()
        for platform in release.PLATFORMS:
            row = self.manifest['platforms'][platform]
            row.update(os='test OS', machine='test emulator', runtime='installed internal package')
            for check in row['checks'].values():
                check.update(status='passed', completed_at=completed, evidence='evidence.md')
        self.manifest['regressions'] = [{'id': '#265', 'platforms': list(release.PLATFORMS),
            'status': 'passed', 'completed_at': completed, 'evidence': 'evidence.md'}]
        self.manifest['approval'] = {'name': 'Fixture reviewer', 'approved_at': self.now.isoformat()}
        self.build = {'id': 123, 'head_sha': self.commit, 'head_branch': 'codex/internal-candidate',
            'event': 'workflow_dispatch', 'status': 'completed', 'conclusion': 'success',
            'path': '.github/workflows/desktop-build.yml', 'updated_at': self.built.isoformat()}
        self.jobs = {'jobs': [{'name': name, 'conclusion': 'success'} for name in gate.BUILD_JOBS]}

    def validate(self, value=None):
        return gate.validate(self.manifest if value is None else value, self.root, self.assets,
            self.version, self.commit, self.build, self.jobs, self.now)

    def test_full_internal_acceptance_without_observation_can_pass(self):
        self.assertNotIn('observation', self.manifest)
        self.assertNotIn('tag', self.manifest)
        self.assertEqual(self.validate(), {(self.root / 'evidence.md').resolve()})

    def test_template_and_every_missing_failed_or_skipped_case_block_tagging(self):
        with self.assertRaises(release.GateError):
            self.validate(gate.template(self.version, self.commit, self.assets, 123))
        for platform in release.PLATFORMS:
            for case in release.CASES:
                for status in ('pending', 'failed', 'skipped', None):
                    with self.subTest(platform=platform, case=case, status=status):
                        value = copy.deepcopy(self.manifest)
                        if status is None:
                            value['platforms'][platform]['checks'].pop(case)
                        else:
                            value['platforms'][platform]['checks'][case]['status'] = status
                        with self.assertRaises(release.GateError):
                            self.validate(value)

    def test_repair_or_version_change_cannot_reuse_old_acceptance(self):
        for field, wrong in (('commit', 'b' * 40), ('version', '1.6.1')):
            value = copy.deepcopy(self.manifest)
            value[field] = wrong
            with self.assertRaisesRegex(release.GateError, 'mismatch'):
                self.validate(value)
        self.build['head_sha'] = 'b' * 40
        with self.assertRaisesRegex(release.GateError, 'commit mismatch'):
            self.validate()

    def test_replaced_package_cannot_be_hidden_by_updating_manual_hashes(self):
        (self.assets / 'AutoClip-x64-setup.exe').write_text('changed package', encoding='utf-8')
        with self.assertRaisesRegex(release.GateError, 'hashes'):
            self.validate()
        self.manifest['assets'] = release.assets_in(self.assets)
        with self.assertRaisesRegex(release.GateError, 'provenance mismatch'):
            self.validate()

    def test_source_ci_tag_build_partial_build_and_failed_checks_are_insufficient(self):
        for field, wrong in (('path', '.github/workflows/ci.yml'), ('event', 'push'),
                             ('head_branch', 'v1.6.0'), ('conclusion', 'failure'), ('id', 999)):
            old = self.build[field]
            self.build[field] = wrong
            with self.subTest(field=field), self.assertRaises(release.GateError):
                self.validate()
            self.build[field] = old
        for job in self.jobs['jobs']:
            job['conclusion'] = 'skipped'
            with self.subTest(job=job['name']), self.assertRaises(release.GateError):
                self.validate()
            job['conclusion'] = 'success'
        self.jobs['jobs'] = [row for row in self.jobs['jobs'] if row['name'] != 'build-windows-x64']
        with self.assertRaisesRegex(release.GateError, 'build-windows-x64'):
            self.validate()

    def test_stale_future_or_unreviewed_evidence_and_unresolved_blockers_block(self):
        for completed in (self.built - dt.timedelta(seconds=1), self.now + dt.timedelta(seconds=1)):
            value = copy.deepcopy(self.manifest)
            value['regressions'][0]['completed_at'] = completed.isoformat()
            with self.assertRaisesRegex(release.GateError, 'predates|future'):
                self.validate(value)
        self.manifest['approval']['approved_at'] = self.built.isoformat()
        with self.assertRaisesRegex(release.GateError, 'approval'):
            self.validate()
        self.manifest['approval']['approved_at'] = self.now.isoformat()
        self.manifest['blockers'] = ['unexplained render failure']
        with self.assertRaisesRegex(release.GateError, 'blockers'):
            self.validate()

    def test_missing_regressions_platforms_and_evidence_cannot_pass(self):
        for field, wrong in (('platforms', []), ('evidence', '../outside.md'),
                             ('evidence', 'missing.md'), ('completed_at', None)):
            value = copy.deepcopy(self.manifest)
            value['regressions'][0][field] = wrong
            with self.subTest(field=field), self.assertRaises(release.GateError):
                self.validate(value)
        self.manifest['regressions'] = []
        with self.assertRaisesRegex(release.GateError, 'regression'):
            self.validate()

    def test_receipt_rejects_wrong_source_version_run_and_non_acceptance_workflow(self):
        receipt = {'schema_version': 1, 'stage': 'internal', 'status': 'passed',
                   'version': self.version, 'commit': self.commit, 'acceptance_run_id': 456,
                   'assets': self.manifest['assets'], 'approved_at': self.now.isoformat()}
        run = {'id': 456, 'path': '.github/workflows/internal-acceptance.yml',
               'event': 'workflow_dispatch', 'status': 'completed', 'conclusion': 'success'}
        gate.check_receipt(receipt, self.version, self.commit, run)
        for field, wrong in (('version', '1.6.1'), ('commit', 'b' * 40),
                             ('acceptance_run_id', 457), ('status', 'pending'), ('assets', {})):
            value = copy.deepcopy(receipt)
            value[field] = wrong
            with self.subTest(field=field), self.assertRaises(release.GateError):
                gate.check_receipt(value, self.version, self.commit, run)
        for field, wrong in (('path', '.github/workflows/ci.yml'), ('event', 'push'),
                             ('status', 'in_progress'), ('conclusion', 'failure')):
            value = dict(run, **{field: wrong})
            with self.subTest(field=field), self.assertRaises(release.GateError):
                gate.check_receipt(receipt, self.version, self.commit, value)

    def test_tag_build_restores_annotated_tag_before_reading_trailer(self):
        workflow = (Path(__file__).resolve().parents[2] / '.github/workflows/desktop-build.yml').read_text(encoding='utf-8')
        restore = workflow.index('git fetch --no-tags --force origin "refs/tags/$TAG:refs/tags/$TAG"')
        self.assertLess(restore, workflow.index('internal_acceptance.py tag-run --tag "$TAG"'))

    def test_tag_requires_one_numeric_internal_acceptance_trailer(self):
        self.assertEqual(gate.tag_run('v1.6.0', 'Release\n\nInternal-Acceptance-Run: 456\n', 'tag\n'), 456)
        for annotation, kind in (('Release', 'tag'), ('Internal-Acceptance-Run: 0', 'tag'),
                                 ('Internal-Acceptance-Run: 456', 'commit'),
                                 ('Internal-Acceptance-Run: 456\nInternal-Acceptance-Run: 789', 'tag'),
                                 ('Internal-Acceptance-Run: $(command)', 'tag')):
            with self.subTest(annotation=annotation), self.assertRaises(release.GateError):
                gate.tag_run('v1.6.0', annotation, kind)

    def test_cli_preserves_evidence_and_creates_receipt_only_after_full_acceptance(self):
        for name, value in (('manifest.json', self.manifest), ('build.json', self.build), ('jobs.json', self.jobs)):
            (self.root / name).write_text(json.dumps(value), encoding='utf-8')
        command = [sys.executable, gate.__file__, 'validate', '--version', self.version,
                   '--commit', self.commit, '--assets', str(self.assets), '--manifest', str(self.root / 'manifest.json'),
                   '--build-run', str(self.root / 'build.json'), '--build-jobs', str(self.root / 'jobs.json'),
                   '--acceptance-run-id', '456', '--bundle', str(self.root / 'accepted')]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'accepted/evidence.md').is_file())
        receipt = json.loads((self.root / 'accepted/receipt.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['commit'], self.commit)
        self.assertEqual(receipt['assets'], self.manifest['assets'])
        self.manifest['platforms']['windows-x64']['checks']['failure_recovery']['status'] = 'pending'
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        command[-1] = str(self.root / 'blocked')
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'blocked/receipt.json').exists())

    def test_waived_rows_require_named_owner_and_reason_and_are_recorded(self):
        value = copy.deepcopy(self.manifest)
        value['platforms']['windows-x64']['checks']['link_import'] = {
            'status': 'waived', 'waiver_reason': 'Owner ships without a real link import run'}
        value['regressions'][0] = {'id': '#265', 'platforms': ['macos-arm64'], 'status': 'waived',
                                   'waiver_reason': 'Covered only by source CI'}
        with self.assertRaisesRegex(release.GateError, 'without a named owner waiver'):
            self.validate(value)
        value['owner_waiver'] = {'name': 'Owner', 'reason': 'Ship and fix forward',
                                 'approved_at': (self.now - dt.timedelta(minutes=5)).isoformat()}
        waived = []
        gate.validate(value, self.root, self.assets, self.version, self.commit, self.build, self.jobs,
                      self.now, waived=waived)
        self.assertEqual(waived, ['windows-x64/link_import', 'regression #265'])
        for broken in ({'name': ' ', 'reason': 'x', 'approved_at': self.now.isoformat()},
                       {'name': 'Owner', 'reason': 'x', 'approved_at': (self.built - dt.timedelta(hours=1)).isoformat()},
                       {'name': 'Owner', 'reason': 'x', 'approved_at': (self.now + dt.timedelta(hours=1)).isoformat()}):
            with self.subTest(waiver=broken), self.assertRaises(release.GateError):
                self.validate(dict(value, owner_waiver=broken))
        value['regressions'][0]['waiver_reason'] = ''
        with self.assertRaisesRegex(release.GateError, 'waiver reason required'):
            self.validate(value)

    def test_owner_waiver_does_not_turn_pending_or_failed_into_passed(self):
        value = copy.deepcopy(self.manifest)
        value['owner_waiver'] = {'name': 'Owner', 'reason': 'Ship and fix forward',
                                 'approved_at': (self.now - dt.timedelta(minutes=5)).isoformat()}
        for status in ('pending', 'failed', 'skipped'):
            value['platforms']['macos-arm64']['checks']['visual_generation']['status'] = status
            with self.subTest(status=status), self.assertRaises(release.GateError):
                self.validate(value)

    def test_cli_receipt_lists_every_waived_row(self):
        self.manifest['platforms']['windows-x64']['checks']['visual_generation'] = {
            'status': 'waived', 'waiver_reason': 'No real Windows vision run'}
        self.manifest['owner_waiver'] = {'name': 'Owner', 'reason': 'Ship and fix forward',
                                         'approved_at': (self.now - dt.timedelta(minutes=5)).isoformat()}
        for name, value in (('manifest.json', self.manifest), ('build.json', self.build), ('jobs.json', self.jobs)):
            (self.root / name).write_text(json.dumps(value), encoding='utf-8')
        result = subprocess.run([sys.executable, gate.__file__, 'validate', '--version', self.version,
                                 '--commit', self.commit, '--assets', str(self.assets),
                                 '--manifest', str(self.root / 'manifest.json'),
                                 '--build-run', str(self.root / 'build.json'), '--build-jobs', str(self.root / 'jobs.json'),
                                 '--acceptance-run-id', '456', '--bundle', str(self.root / 'accepted')],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads((self.root / 'accepted/receipt.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['waived'], ['windows-x64/visual_generation'])
        self.assertEqual(receipt['owner_waiver']['name'], 'Owner')


if __name__ == '__main__':
    unittest.main()
