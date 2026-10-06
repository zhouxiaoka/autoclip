import copy
import datetime as dt
import json
from pathlib import Path
import sys
import subprocess
import shutil
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_acceptance as gate


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        self.tag, self.commit, self.repo = 'v1.5.1', 'a' * 40, 'owner/autoclip'
        self.now = dt.datetime.now(dt.timezone.utc)
        self.built = self.now - dt.timedelta(hours=30)
        files = ('AutoClip.dmg', 'AutoClip.app.tar.gz', 'AutoClip-x64-setup.exe',
                 'AutoClip.app.tar.gz.sig', 'AutoClip-x64-setup.exe.sig',
                 'autoclip-1.5.1-py3-none-any.whl', 'autoclip-1.5.1-cli-mcp.zip')
        for name in files:
            (self.assets / name).write_text('fixture-signature' if name.endswith('.sig') else 'fixture-package')
        (self.assets / 'latest.json').write_text(json.dumps({'version': '1.5.1', 'platforms': {
            platform: {'signature': 'fixture-signature', 'url': f'https://github.com/{self.repo}/releases/download/{self.tag}/{name}'}
            for platform, name in (('darwin-aarch64', 'AutoClip.app.tar.gz'), ('windows-x86_64', 'AutoClip-x64-setup.exe'))}}))
        (self.root / 'evidence.md').write_text('Sanitized device acceptance and observation fixture')
        self.manifest = gate.template(self.tag, self.commit, self.assets, 'routine', 123)
        for platform in gate.PLATFORMS:
            row = self.manifest['platforms'][platform]
            row.update(os='test OS', machine='test VM', runtime='installed package')
            for check in row['checks'].values():
                check.update(status='passed', evidence='evidence.md', completed_at=(self.built + dt.timedelta(hours=1)).isoformat())
        self.manifest['regressions'] = [{'id': '#258', 'status': 'passed', 'evidence': 'evidence.md'}]
        self.manifest['observation'].update(status='passed', evidence='evidence.md',
            started_at=self.built.isoformat(), ended_at=(self.now - dt.timedelta(hours=1)).isoformat(),
            devices={p: 1 for p in gate.PLATFORMS}, completed_flows={p: 1 for p in gate.PLATFORMS})
        self.manifest['approval'] = {'name': 'Fixture reviewer', 'approved_at': self.now.isoformat()}
        self.refresh_assets()
        self.build = {'id': 123, 'head_sha': self.commit, 'head_branch': self.tag, 'event': 'push',
                      'status': 'completed', 'conclusion': 'success', 'path': '.github/workflows/desktop-build.yml',
                      'updated_at': self.built.isoformat()}
        self.jobs = {'jobs': [{'name': 'source-quality / ' + name if ' ' in name else name, 'conclusion': 'success'} for name in gate.BUILD_JOBS]}

    def refresh_assets(self):
        (self.assets / 'build-provenance.json').write_text(json.dumps(gate.provenance(self.tag, self.commit, self.assets, 123)))
        self.manifest['assets'] = gate.assets_in(self.assets)

    def validate(self, value=None):
        return gate.validate(value or self.manifest, self.root, self.assets, self.tag, self.commit,
                             self.repo, self.build, self.jobs, self.now)

    def test_complete_evidence_passes(self):
        self.assertEqual(self.validate(), {(self.root / 'evidence.md').resolve()})

    def test_owner_waiver_can_replace_observation_but_not_pending_rows(self):
        value = copy.deepcopy(self.manifest)
        value['observation'] = {'status': 'waived', 'waiver_reason': 'Owner ships without observation'}
        with self.assertRaisesRegex(gate.GateError, 'without a named owner waiver'):
            self.validate(value)
        value['owner_waiver'] = {'name': 'Owner', 'reason': 'Ship and fix forward',
                                 'approved_at': (self.now - dt.timedelta(minutes=5)).isoformat()}
        self.assertEqual(self.validate(value), {(self.root / 'evidence.md').resolve()})
        late = copy.deepcopy(value)
        late['approval']['approved_at'] = (self.now - dt.timedelta(minutes=10)).isoformat()
        with self.assertRaisesRegex(gate.GateError, 'approval must follow observation'):
            self.validate(late)
        value['platforms']['windows-x64']['checks']['link_import']['status'] = 'pending'
        with self.assertRaises(gate.GateError):
            self.validate(value)
        value['platforms']['windows-x64']['checks']['link_import'] = {
            'status': 'waived', 'waiver_reason': 'No real link import run'}
        self.validate(value)

    def test_pending_template_cannot_promote(self):
        value = gate.template(self.tag, self.commit, self.assets, 'hotfix', 123)
        with self.assertRaises(gate.GateError):
            self.validate(value)

    def test_missing_skipped_or_failed_device_checks_block(self):
        for platform in gate.PLATFORMS:
            for case in gate.CASES:
                for status in ('pending', 'skipped', 'failed'):
                    with self.subTest(platform=platform, case=case, status=status):
                        value = copy.deepcopy(self.manifest)
                        value['platforms'][platform]['checks'][case]['status'] = status
                        with self.assertRaises(gate.GateError):
                            self.validate(value)

    def test_rebuilt_or_wrong_version_assets_block(self):
        (self.assets / 'AutoClip-x64-setup.exe').write_text('rebuilt-package')
        with self.assertRaisesRegex(gate.GateError, 'hashes'):
            self.validate()
        self.refresh_assets()
        updater = json.loads((self.assets / 'latest.json').read_text())
        updater['version'] = '1.5.0'
        (self.assets / 'latest.json').write_text(json.dumps(updater))
        self.refresh_assets()
        with self.assertRaisesRegex(gate.GateError, 'version mismatch'):
            self.validate()

    def test_wrong_tag_commit_or_build_cannot_reuse_evidence(self):
        for field, wrong in (('head_sha', 'b' * 40), ('head_branch', 'v1.5.0'),
                             ('event', 'workflow_dispatch'), ('conclusion', 'failure'),
                             ('path', '.github/workflows/ci.yml'), ('id', 124)):
            with self.subTest(field=field):
                old = self.build[field]
                self.build[field] = wrong
                with self.assertRaises(gate.GateError):
                    self.validate()
                self.build[field] = old
        self.manifest['commit'] = 'b' * 40
        with self.assertRaises(gate.GateError):
            self.validate()

    def test_successful_build_with_skipped_quality_or_smoke_blocks(self):
        for job in self.jobs['jobs']:
            with self.subTest(job=job['name']):
                job['conclusion'] = 'skipped'
                with self.assertRaises(gate.GateError):
                    self.validate()
                job['conclusion'] = 'success'

    def test_observation_requires_time_and_real_samples_on_both_platforms(self):
        self.manifest['observation']['started_at'] = (self.now - dt.timedelta(hours=3)).isoformat()
        with self.assertRaisesRegex(gate.GateError, '24 hours'):
            self.validate()
        self.manifest['release_type'] = 'hotfix'
        with self.assertRaisesRegex(gate.GateError, '4 hours'):
            self.validate()
        self.manifest['observation']['started_at'] = self.built.isoformat()
        for platform in gate.PLATFORMS:
            for field in ('devices', 'completed_flows'):
                self.manifest['observation'][field][platform] = 0
                with self.assertRaisesRegex(gate.GateError, 'silence'):
                    self.validate()
                self.manifest['observation'][field][platform] = 1

    def test_unresolved_blocker_or_no_regressions_blocks(self):
        self.manifest['blockers'] = ['Settings cannot open']
        with self.assertRaisesRegex(gate.GateError, 'blockers'):
            self.validate()
        self.manifest['blockers'] = []
        self.manifest['regressions'] = []
        with self.assertRaisesRegex(gate.GateError, 'regression'):
            self.validate()

    def test_missing_evidence_and_path_escape_block(self):
        for name in ('missing.md', '../outside.md', str(self.root / 'evidence.md')):
            with self.subTest(name=name):
                self.manifest['regressions'][0]['evidence'] = name
                with self.assertRaises(gate.GateError):
                    self.validate()
        (self.root / 'empty.md').touch()
        self.manifest['regressions'][0]['evidence'] = 'empty.md'
        with self.assertRaises(gate.GateError):
            self.validate()

    def test_stale_device_check_future_observation_or_early_approval_blocks(self):
        value = copy.deepcopy(self.manifest)
        value['platforms']['windows-x64']['checks']['upgrade_legacy']['completed_at'] = (self.built - dt.timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(gate.GateError, 'predates'):
            self.validate(value)
        value = copy.deepcopy(self.manifest)
        value['observation']['ended_at'] = (self.now + dt.timedelta(hours=1)).isoformat()
        with self.assertRaises(gate.GateError):
            self.validate(value)
        self.manifest['approval']['approved_at'] = self.built.isoformat()
        with self.assertRaisesRegex(gate.GateError, 'approval'):
            self.validate()

    def test_updater_cannot_reference_another_release_or_wrong_signature(self):
        for wrong in ('https://github.com/owner/autoclip/releases/download/v1.5.0/AutoClip.app.tar.gz',
                      'https://other.example/owner/autoclip/releases/download/v1.5.1/AutoClip.app.tar.gz'):
            updater = json.loads((self.assets / 'latest.json').read_text())
            updater['platforms']['darwin-aarch64']['url'] = wrong
            (self.assets / 'latest.json').write_text(json.dumps(updater))
            self.refresh_assets()
            with self.assertRaisesRegex(gate.GateError, 'different release'):
                self.validate()

    def test_updating_only_manual_asset_hashes_cannot_hide_replaced_build(self):
        (self.assets / 'AutoClip-x64-setup.exe').write_text('different-build')
        self.manifest['assets'] = gate.assets_in(self.assets)
        with self.assertRaisesRegex(gate.GateError, 'provenance'):
            self.validate()

    def test_signature_mismatch_and_missing_required_assets_block(self):
        (self.assets / 'AutoClip.app.tar.gz.sig').write_text('wrong-signature')
        self.refresh_assets()
        with self.assertRaisesRegex(gate.GateError, 'signature mismatch'):
            self.validate()
        (self.assets / 'AutoClip.dmg').unlink()
        self.refresh_assets()
        with self.assertRaisesRegex(gate.GateError, 'missing .dmg'):
            self.validate()

    def test_cli_bundled_evidence_can_be_revalidated_before_promotion(self):
        for name, value in (('acceptance.json', self.manifest), ('build.json', self.build), ('jobs.json', self.jobs)):
            (self.root / name).write_text(json.dumps(value))
        bundle = self.root / 'accepted'
        command = [sys.executable, gate.__file__, 'validate', '--tag', self.tag, '--commit', self.commit,
                   '--assets', str(self.assets), '--manifest', str(self.root / 'acceptance.json'),
                   '--repository', self.repo, '--build-run', str(self.root / 'build.json'),
                   '--build-jobs', str(self.root / 'jobs.json'), '--bundle', str(bundle)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((bundle / 'evidence.md').is_file())
        value = json.loads((bundle / 'acceptance.json').read_text())
        gate.validate(value, bundle, self.assets, self.tag, self.commit, self.repo, self.build, self.jobs)
        (bundle / 'evidence.md').unlink()
        with self.assertRaises(gate.GateError):
            gate.validate(value, bundle, self.assets, self.tag, self.commit, self.repo, self.build, self.jobs)

    def test_build_provenance_survives_github_asset_name_normalization(self):
        (self.assets / 'AutoClip.dmg').rename(self.assets / 'AutoClip Desktop.dmg')
        build = gate.provenance(self.tag, self.commit, self.assets, 123)
        (self.assets / 'build-provenance.json').write_text(json.dumps(build))
        downloaded = self.root / 'downloaded'
        downloaded.mkdir()
        for path in self.assets.iterdir():
            shutil.copyfile(path, downloaded / path.name.replace(' ', '.'))
        value = copy.deepcopy(self.manifest)
        value['assets'] = gate.assets_in(downloaded)
        gate.validate(value, self.root, downloaded, self.tag, self.commit, self.repo, self.build, self.jobs, self.now)

    def test_colliding_build_names_are_rejected(self):
        (self.assets / 'AutoClip Desktop.dmg').write_text('one')
        (self.assets / 'AutoClip.Desktop.dmg').write_text('two')
        with self.assertRaisesRegex(gate.GateError, 'collide'):
            gate.provenance(self.tag, self.commit, self.assets, 123)


if __name__ == '__main__':
    unittest.main()
