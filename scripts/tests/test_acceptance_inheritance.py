"""Impact inheritance preserves execution provenance without clearing required cases."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_acceptance as release
import test_internal_acceptance as internal_tests
import test_release_acceptance as release_tests


class ImpactInheritanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = internal_tests.InternalAcceptanceTests('test_full_internal_acceptance_without_observation_can_pass')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.gate = self.fixture.validate
        self.root = self.fixture.root
        self.current = self.fixture.manifest
        self.old_commit = 'b' * 40
        self.source_bytes = b'unchanged runtime path\n'
        self.diff_bytes = b'diff --git a/post_copy.py b/post_copy.py\n+role guard\n'
        self.reviewed = self.fixture.now.isoformat()
        self.executed = (self.fixture.built - dt.timedelta(hours=1)).isoformat()
        self.old_built = (self.fixture.built - dt.timedelta(hours=2)).isoformat()
        self.raw('original.txt', 'Actual original execution assertions, not a preparation file')
        self.raw('runtime.txt', 'Owned old/current installed identities and unchanged scoped runtime')
        self.label = 'macos-arm64/local_without_subtitles'
        self.platforms = ['macos-arm64']
        self.origin = {'status': 'passed', 'commit': self.old_commit, 'build_run_id': 101,
            'build_completed_at': self.old_built, 'assets': {'old.dmg': 'c' * 64},
            'platforms': self.platforms, 'label': self.label, 'completed_at': self.executed,
            'assertions': ['asr', 'decode'], 'evidence': self.ref('original.txt')}
        self.write('old-build.json', {'id': 101, 'head_sha': self.old_commit,
            'path': '.github/workflows/desktop-build.yml', 'status': 'completed', 'conclusion': 'success',
            'updated_at': self.old_built})
        self.write('old-provenance.json', {'schema_version': 1, 'commit': self.old_commit,
            'build_run_id': 101, 'assets': self.origin['assets']})
        self.origin.update(build=self.ref('old-build.json'), provenance=self.ref('old-provenance.json'))
        self.write('origin.json', self.origin)
        self.write('diff.json', {'from_commit': self.old_commit, 'to_commit': self.current['commit'],
            'diff_sha256': self.sha(self.diff_bytes)})
        self.review = {'contract': 'impact-inheritance/v1', 'reviewer': 'Named scope reviewer',
            'reviewed_at': self.reviewed, 'target': self.target(self.platforms, self.label),
            'required_assertions': ['asr', 'decode', 'description'],
            'inherited_assertions': ['asr', 'decode'], 'affected_assertions': ['description'],
            'origin': self.ref('origin.json'), 'diff': self.ref('diff.json'),
            'dependencies': [{'path': 'backend/asr.py', 'sha256': self.sha(self.source_bytes)}],
            'runtime_evidence': self.ref('runtime.txt'),
            'reason': 'ASR/decoder path unchanged; new description assertion is separately executed',
            'fresh': []}
        self.fresh = {'status': 'passed', **self.target(self.platforms, self.label),
            'completed_at': self.reviewed, 'assertions': ['description'], 'evidence': self.ref('evidence.md')}
        self.write('fresh.json', self.fresh)
        self.review['fresh'] = [self.ref('fresh.json')]
        self.row = self.current['platforms']['macos-arm64']['checks']['local_without_subtitles']
        self.row.update(evidence_mode='inherited', completed_at=self.executed,
            reviewed_at=self.reviewed, evidence='review.json')
        self.current['evidence_contract'] = 'impact-inheritance/v1'
        self.sync()
        self.git_patch = patch.object(release, 'git_bytes', create=True, side_effect=self.git_bytes)
        self.git_patch.start()
        self.addCleanup(self.git_patch.stop)

    @staticmethod
    def sha(value):
        return hashlib.sha256(value).hexdigest()

    def raw(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8')

    def write(self, name, value):
        self.raw(name, json.dumps(value))

    def ref(self, name):
        return {'path': name, 'sha256': self.sha((self.root / name).read_bytes())}

    def target(self, platforms, label):
        return {'commit': self.current['commit'], 'build_run_id': self.current['build_run_id'],
            'assets': self.current['assets'], 'platforms': platforms, 'label': label}

    def sync(self):
        self.write('origin.json', self.origin)
        self.review['origin'] = self.ref('origin.json')
        self.write('fresh.json', self.fresh)
        self.review['fresh'] = [self.ref('fresh.json')] if self.review['fresh'] else []
        self.write('review.json', self.review)

    def git_bytes(self, args):
        return self.source_bytes if args[0] == 'show' else self.diff_bytes

    def blocked(self, mutate):
        original = copy.deepcopy((self.current, self.origin, self.review, self.fresh))
        mutate()
        self.sync()
        with self.assertRaises(release.GateError):
            self.gate()
        self.current.clear(); self.current.update(original[0])
        self.fixture.manifest = self.current
        self.row = self.current['platforms']['macos-arm64']['checks']['local_without_subtitles']
        self.origin, self.review, self.fresh = original[1:]
        self.sync()

    def test_old_execution_with_new_review_and_changed_assertion_can_pass(self):
        before = self.row['completed_at']
        files = self.gate()
        self.assertEqual(self.row['completed_at'], before)
        self.assertEqual({path.name for path in files},
            {'evidence.md', 'original.txt', 'origin.json', 'runtime.txt', 'diff.json', 'fresh.json', 'review.json', 'old-build.json', 'old-provenance.json'})

    def test_each_nonpassed_origin_or_fresh_result_blocks(self):
        for status in ('pending', 'failed', 'unknown', 'skipped', None):
            with self.subTest(origin=status):
                self.blocked(lambda: self.origin.update(status=status))
            with self.subTest(fresh=status):
                self.blocked(lambda: self.fresh.update(status=status))

    def test_incomplete_duplicate_or_affected_inheritance_blocks(self):
        for field, value in [('required_assertions', []), ('required_assertions', ['asr', 'decode', 'description', 'not_done']),
                ('inherited_assertions', ['asr', 'decode', 'description']),
                ('inherited_assertions', ['asr', 'asr']), ('affected_assertions', ['decode']),
                ('fresh', []), ('dependencies', []), ('reason', ''), ('reviewer', '')]:
            with self.subTest(field=field, value=value):
                self.blocked(lambda: self.review.update({field: value}))

    def test_identity_package_source_platform_and_time_mismatch_blocks(self):
        for field, value in [('commit', 'wrong'), ('build_run_id', 0), ('assets', {}),
                ('platforms', ['windows-x64']), ('label', 'macos-arm64/clean_install'),
                ('completed_at', self.reviewed), ('build', {'path': 'missing', 'sha256': 'd' * 64})]:
            with self.subTest(origin=field):
                self.blocked(lambda: self.origin.update({field: value}))
        for field, value in [('commit', 'c' * 40), ('build_run_id', 999), ('assets', {'wrong': 'c' * 64}),
                ('platforms', ['windows-x64']), ('label', 'other')]:
            with self.subTest(target=field):
                self.blocked(lambda: self.review['target'].update({field: value}))
            with self.subTest(fresh=field):
                self.blocked(lambda: self.fresh.update({field: value}))
        for value in (self.executed, (self.fixture.now + dt.timedelta(seconds=1)).isoformat(), 'bad', None):
            with self.subTest(review=value):
                self.blocked(lambda: (self.row.update(reviewed_at=value), self.review.update(reviewed_at=value)))
        self.blocked(lambda: self.row.update(completed_at=self.reviewed))
        self.blocked(lambda: self.fresh.update(completed_at=self.executed))

    def test_proof_hash_escape_missing_dependency_and_actual_git_changes_block(self):
        self.blocked(lambda: self.origin['evidence'].update(sha256='d' * 64))
        self.blocked(lambda: self.review['runtime_evidence'].update(path='../outside'))
        self.blocked(lambda: self.review['dependencies'][0].update(sha256='d' * 64))
        self.blocked(lambda: self.review['dependencies'][0].update(path='../outside.py'))
        self.blocked(lambda: self.review['diff'].update(sha256='d' * 64))
        with patch.object(release, 'git_bytes', side_effect=lambda args: b'changed' if args[0] == 'show' and args[1].startswith(self.current['commit']) else self.git_bytes(args)):
            with self.assertRaises(release.GateError):
                self.gate()
        with patch.object(release, 'git_bytes', return_value=b'wrong diff'):
            with self.assertRaises(release.GateError):
                self.gate()

    def test_execution_cannot_smuggle_inheritance_and_unknown_contract_blocks(self):
        self.blocked(lambda: self.row.update(evidence_mode='execution', completed_at=self.reviewed))
        self.blocked(lambda: self.row.update(evidence_mode='unknown'))
        self.blocked(lambda: self.current.update(evidence_contract='unknown'))
        self.blocked(lambda: self.current.pop('evidence_contract'))

    def test_pending_other_required_case_and_early_approval_still_block(self):
        self.blocked(lambda: self.current['platforms']['windows-x64']['checks']['link_import'].update(status='pending'))
        self.blocked(lambda: self.current['approval'].update(approved_at=self.executed))
        self.blocked(lambda: self.current.update(blockers=['still unknown']))

    def test_inherited_regression_requires_same_source_and_assertion_proofs(self):
        row = copy.deepcopy(self.row)
        row.update(id='#265', platforms=list(release.PLATFORMS))
        self.current['regressions'] = [row]
        self.row.update(evidence_mode='execution', completed_at=self.reviewed, evidence='evidence.md')
        self.row.pop('reviewed_at')
        self.label = 'regression #265'; self.platforms = list(release.PLATFORMS)
        self.origin.update(label=self.label, platforms=self.platforms)
        self.review['target'] = self.target(self.platforms, self.label)
        self.fresh.update(self.target(self.platforms, self.label))
        self.sync()
        self.gate()

    def test_real_git_blobs_and_diff_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            def git(*args):
                return subprocess.check_output(['git', '-c', 'user.name=Gate fixture',
                    '-c', 'user.email=gate@example.invalid', *args], cwd=repo, stderr=subprocess.PIPE).strip().decode()
            git('init', '-q')
            (repo / 'backend').mkdir()
            (repo / 'backend/asr.py').write_bytes(self.source_bytes)
            (repo / 'post_copy.py').write_text('old role behavior\n')
            git('add', '.'); git('commit', '-qm', 'fixture original')
            self.old_commit = git('rev-parse', 'HEAD')
            (repo / 'post_copy.py').write_text('new role guard\n')
            git('add', '.'); git('commit', '-qm', 'fixture role change')
            current = git('rev-parse', 'HEAD')
            self.current['commit'] = self.fixture.commit = current
            self.fixture.build['head_sha'] = current
            (self.fixture.assets / internal_tests.gate.PROVENANCE).write_text(json.dumps(
                internal_tests.gate.provenance(self.fixture.version, current, self.fixture.assets, 123)))
            self.current['assets'] = release.assets_in(self.fixture.assets)
            self.origin['commit'] = self.old_commit
            self.write('old-build.json', {'id': 101, 'head_sha': self.old_commit,
                'path': '.github/workflows/desktop-build.yml', 'status': 'completed',
                'conclusion': 'success', 'updated_at': self.old_built})
            self.write('old-provenance.json', {'schema_version': 1, 'commit': self.old_commit,
                'build_run_id': 101, 'assets': self.origin['assets']})
            self.origin.update(build=self.ref('old-build.json'), provenance=self.ref('old-provenance.json'))
            self.git_patch.stop()
            actual = release.git_bytes
            self.write('diff.json', {'from_commit': self.old_commit, 'to_commit': current,
                'diff_sha256': self.sha(actual(['diff', '--no-ext-diff', '--no-textconv', '--binary',
                    self.old_commit, current, '--'], repo=repo))})
            self.review.update(diff=self.ref('diff.json'), target=self.target(self.platforms, self.label))
            self.fresh.update(self.target(self.platforms, self.label))
            self.sync()
            with patch.object(release, 'git_bytes', side_effect=lambda args: actual(args, repo=repo)):
                self.gate()
                # Exercise the actual CLI from an isolated repository containing the same gate bytes.
                (repo / 'scripts').mkdir()
                for name in ('internal_acceptance.py', 'release_acceptance.py'):
                    (repo / 'scripts' / name).write_bytes((Path(release.__file__).parent / name).read_bytes())
                self.write('manifest.json', self.current)
                self.write('build.json', self.fixture.build)
                self.write('jobs.json', self.fixture.jobs)
                command = [sys.executable, str(repo / 'scripts/internal_acceptance.py'), 'validate',
                    '--version', self.fixture.version, '--commit', current, '--assets', str(self.fixture.assets),
                    '--manifest', str(self.root / 'manifest.json'), '--build-run', str(self.root / 'build.json'),
                    '--build-jobs', str(self.root / 'jobs.json'), '--acceptance-run-id', '456',
                    '--bundle', str(self.root / 'accepted-inheritance')]
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                accepted = self.root / 'accepted-inheritance'
                receipt = json.loads((accepted / 'receipt.json').read_text())
                self.assertEqual(receipt['schema_version'], 1)
                self.assertEqual(receipt['commit'], current)
                self.assertEqual(receipt['evidence_contract'], 'impact-inheritance/v1')
                self.assertEqual(receipt['manifest_sha256'], release.digest(accepted / 'acceptance.json'))
                for name in ('origin.json', 'original.txt', 'old-build.json', 'old-provenance.json',
                             'runtime.txt', 'diff.json', 'fresh.json', 'review.json'):
                    self.assertEqual((accepted / name).read_bytes(), (self.root / name).read_bytes())
                self.assertEqual(json.loads((accepted / 'acceptance.json').read_text())['platforms']
                    ['macos-arm64']['checks']['local_without_subtitles']['completed_at'], self.executed)
                self.current['platforms']['windows-x64']['checks']['link_import']['status'] = 'pending'
                self.write('manifest.json', self.current)
                command[-1] = str(self.root / 'blocked-inheritance')
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse((self.root / 'blocked-inheritance/receipt.json').exists())
                self.current['platforms']['windows-x64']['checks']['link_import']['status'] = 'passed'
                self.review['dependencies'] = [{'path': 'post_copy.py',
                    'sha256': self.sha((repo / 'post_copy.py').read_bytes())}]
                self.sync()
                with self.assertRaisesRegex(release.GateError, 'dependency changed'):
                    self.gate()
            with self.assertRaisesRegex(release.GateError, 'source objects unavailable'):
                actual(['show', 'f' * 40 + ':backend/asr.py'], repo=repo)

    def test_release_inheritance_does_not_replace_current_observation(self):
        fixture = release_tests.AcceptanceTests('test_complete_evidence_passes')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        # Move current tagged build recent enough that actual old execution predates it.
        fixture.built = self.fixture.built
        fixture.build['updated_at'] = fixture.built.isoformat()
        fixture.manifest['release_type'] = 'hotfix'
        fixture.manifest['observation'].update(started_at=fixture.built.isoformat(), ended_at=fixture.now.isoformat())
        for row in fixture.manifest['platforms'].values():
            for check in row['checks'].values():
                check['completed_at'] = fixture.now.isoformat()
        self.current = fixture.manifest
        # Copy only this test's owned evidence to the second isolated bundle.
        for file in self.root.iterdir():
            if file.is_file():
                (fixture.root / file.name).write_bytes(file.read_bytes())
        self.root = fixture.root
        self.row = self.current['platforms']['macos-arm64']['checks']['local_without_subtitles']
        self.row.update(evidence_mode='inherited', completed_at=self.executed, reviewed_at=self.reviewed, evidence='review.json')
        self.review['target'] = self.target(self.platforms, self.label)
        self.fresh.update(self.target(self.platforms, self.label))
        self.current['evidence_contract'] = 'impact-inheritance/v1'
        self.sync()
        # Still blocks: inheritance cannot shorten a 4-hour observation to 2 hours.
        with self.assertRaisesRegex(release.GateError, '4 hours'):
            fixture.validate()
        fixture.built = fixture.now - dt.timedelta(hours=5)
        fixture.build['updated_at'] = fixture.built.isoformat()
        fixture.manifest['observation']['started_at'] = fixture.built.isoformat()
        # Original completion is valid; review/fresh results must precede observation end.
        fixture.validate()
        fixture.manifest['observation']['evidence_mode'] = 'inherited'
        with self.assertRaisesRegex(release.GateError, 'observation cannot be inherited'):
            fixture.validate()
        fixture.manifest['observation'].pop('evidence_mode')
        fixture.manifest['observation']['devices']['windows-x64'] = 0
        with self.assertRaisesRegex(release.GateError, 'silence'):
            fixture.validate()


if __name__ == '__main__':
    unittest.main()
