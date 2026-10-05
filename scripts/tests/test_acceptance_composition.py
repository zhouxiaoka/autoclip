"""Multiple original executions remain distinct and never waive required assertions."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import internal_acceptance as internal
import release_acceptance as release
import test_acceptance_inheritance as inheritance
import test_release_acceptance as release_tests


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = inheritance.ImpactInheritanceTests(
            'test_old_execution_with_new_review_and_changed_assertion_can_pass')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.current, self.root = f.current, f.root
        self.second = copy.deepcopy(f.origin)
        self.second.update(commit='c' * 40, build_run_id=102, assertions=['decode'],
            assets={'second.dmg': 'd' * 64},
            completed_at=(release.timestamp(f.executed) + inheritance.dt.timedelta(minutes=5)).isoformat())
        f.write('second-build.json', {'id': 102, 'head_sha': self.second['commit'],
            'path': '.github/workflows/desktop-build.yml', 'status': 'completed',
            'conclusion': 'success', 'updated_at': f.old_built})
        f.write('second-provenance.json', {'schema_version': 1, 'commit': self.second['commit'],
            'build_run_id': 102, 'assets': self.second['assets']})
        self.second.update(build=f.ref('second-build.json'), provenance=f.ref('second-provenance.json'))
        f.write('second-diff.json', {'from_commit': self.second['commit'], 'to_commit': self.current['commit'],
            'diff_sha256': f.sha(f.diff_bytes)})
        self.components = [
            {key: copy.deepcopy(f.review[key]) for key in
             ('origin', 'diff', 'dependencies', 'runtime_evidence')},
            {'origin': {}, 'diff': f.ref('second-diff.json'),
             'dependencies': copy.deepcopy(f.review['dependencies']),
             'runtime_evidence': f.ref('runtime.txt')}]
        self.components[0]['inherited_assertions'] = ['asr']
        self.components[1]['inherited_assertions'] = ['decode']
        self.review = {key: copy.deepcopy(f.review[key]) for key in
                      ('reviewer', 'reviewed_at', 'target', 'required_assertions',
                       'affected_assertions', 'reason', 'fresh')}
        self.review.update(contract='impact-inheritance/v2', inherited_origins=self.components)
        self.current['evidence_contract'] = 'impact-inheritance/v2'
        f.row.update(completed_at=None, evidence='composition.json')
        self.sync()

    def sync(self):
        f = self.fixture
        f.write('second-origin.json', self.second)
        self.components[1]['origin'] = f.ref('second-origin.json')
        f.write('fresh.json', f.fresh)
        self.review['fresh'] = [f.ref('fresh.json')] if self.review['fresh'] else []
        f.write('composition.json', self.review)

    def validate(self):
        return self.fixture.gate()

    def test_two_originals_and_current_fresh_cover_exact_case(self):
        original_times = (self.fixture.origin['completed_at'], self.second['completed_at'])
        files = self.validate()
        self.assertIsNone(self.fixture.row['completed_at'])
        self.assertEqual(original_times, (self.fixture.origin['completed_at'], self.second['completed_at']))
        self.assertTrue({'origin.json', 'second-origin.json', 'old-build.json',
            'second-build.json', 'old-provenance.json', 'second-provenance.json',
            'diff.json', 'second-diff.json', 'runtime.txt', 'fresh.json'} <= {p.name for p in files})

    def test_each_nonpassed_original_is_rejected(self):
        for status in ('pending', 'failed', 'unknown', 'skipped', None):
            with self.subTest(status=status):
                self.second['status'] = status
                self.sync()
                with self.assertRaisesRegex(release.GateError, 'original execution did not pass'):
                    self.validate()

    def test_each_nonpassed_fresh_result_and_unproved_original_assertion_are_rejected(self):
        for status in ('pending', 'failed', 'unknown', 'skipped', None):
            self.fixture.fresh['status'] = status
            self.sync()
            with self.subTest(status=status), self.assertRaisesRegex(release.GateError, 'fresh assertion/current target'):
                self.validate()
        self.fixture.fresh['status'] = 'passed'
        self.components[1]['inherited_assertions'].append('never_passed')
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'original passed assertions missing'):
            self.validate()

    def test_overlap_between_originals_is_rejected(self):
        self.second['assertions'].append('asr')
        self.components[1]['inherited_assertions'].append('asr')
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'duplicate inherited'):
            self.validate()

    def test_missing_or_extra_coverage_is_rejected(self):
        for ids in (['asr', 'description'], ['asr', 'decode', 'description', 'missing']):
            self.review['required_assertions'] = ids
            self.sync()
            with self.subTest(ids=ids), self.assertRaisesRegex(release.GateError, 'incomplete required'):
                self.validate()

    def test_affected_original_cannot_be_inherited(self):
        self.review['affected_assertions'].append('decode')
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'affected assertions cannot be inherited'):
            self.validate()

    def test_original_and_fresh_cannot_overlap(self):
        self.fixture.fresh['assertions'].append('decode')
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'duplicate inherited/fresh'):
            self.validate()

    def test_missing_current_affected_evidence_is_rejected(self):
        self.review['fresh'] = []
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'incomplete required'):
            self.validate()

    def test_original_completion_cannot_predate_its_build(self):
        self.second['completed_at'] = (self.fixture.fixture.built - inheritance.dt.timedelta(hours=3)).isoformat()
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'original execution/build time mismatch'):
            self.validate()

    def test_composite_cannot_claim_a_single_execution_time(self):
        self.fixture.row['completed_at'] = self.fixture.executed
        with self.assertRaisesRegex(release.GateError, 'composed row must preserve'):
            self.validate()

    def test_old_or_future_review_and_stale_fresh_are_rejected(self):
        self.fixture.fresh['completed_at'] = self.fixture.executed
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'after current build'):
            self.validate()
        self.fixture.fresh['completed_at'] = self.fixture.reviewed
        for value in (self.fixture.executed,
                      (self.fixture.fixture.now + inheritance.dt.timedelta(seconds=1)).isoformat()):
            self.review['reviewed_at'] = self.fixture.row['reviewed_at'] = value
            self.sync()
            with self.subTest(value=value), self.assertRaisesRegex(release.GateError, 'impact review must follow'):
                self.validate()

    def test_wrong_original_identity_or_scope_is_rejected(self):
        original = copy.deepcopy(self.second)
        for key, value in (('commit', 'not-sha'), ('build_run_id', True), ('assets', {}),
                           ('label', 'other'), ('platforms', ['windows-x64'])):
            self.second.clear(); self.second.update(original)
            self.second[key] = value
            self.sync()
            with self.subTest(key=key), self.assertRaises(release.GateError):
                self.validate()

    def test_wrong_current_fresh_target_is_rejected(self):
        self.fixture.fresh['build_run_id'] = 101
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'fresh assertion/current target mismatch'):
            self.validate()

    def test_original_build_and_provenance_cannot_refer_to_another_run(self):
        f = self.fixture
        bad = json.loads((self.root / 'second-build.json').read_text())
        bad['head_sha'] = f.old_commit
        f.write('second-build.json', bad)
        self.second['build'] = f.ref('second-build.json')
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'Desktop Build identity mismatch'):
            self.validate()
        bad['head_sha'] = self.second['commit']
        f.write('second-build.json', bad)
        self.second['build'] = f.ref('second-build.json')
        pv = json.loads((self.root / 'second-provenance.json').read_text())
        pv['build_run_id'] = 101
        f.write('second-provenance.json', pv)
        self.second['provenance'] = f.ref('second-provenance.json')
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'package provenance mismatch'):
            self.validate()

    def test_wrong_diff_and_changed_dependency_are_rejected(self):
        f = self.fixture
        f.write('second-diff.json', {'from_commit': self.second['commit'], 'to_commit': self.current['commit'],
                                   'diff_sha256': '0' * 64})
        self.components[1]['diff'] = f.ref('second-diff.json')
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'impact diff mismatch'):
            self.validate()
        f.write('second-diff.json', {'from_commit': self.second['commit'], 'to_commit': self.current['commit'],
                                   'diff_sha256': f.sha(f.diff_bytes)})
        self.components[1]['diff'] = f.ref('second-diff.json')
        self.sync()
        with patch.object(release, 'git_bytes', side_effect=lambda args:
                b'changed' if args[0] == 'show' and args[1].startswith(self.second['commit']) else f.git_bytes(args)):
            with self.assertRaisesRegex(release.GateError, 'dependency changed'):
                self.validate()

    def test_missing_git_objects_fail_closed(self):
        with patch.object(release, 'git_bytes', side_effect=release.GateError('source objects unavailable')):
            with self.assertRaisesRegex(release.GateError, 'source objects unavailable'):
                self.validate()

    def test_hashed_runtime_and_original_files_cannot_be_replaced(self):
        self.components[1]['runtime_evidence']['sha256'] = '0' * 64
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'SHA-256 mismatch'):
            self.validate()

    def test_ambiguous_v1_fields_duplicate_origin_or_empty_list_are_rejected(self):
        self.review['origin'] = self.components[0]['origin']
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'single-origin fields'):
            self.validate()
        self.review.pop('origin')
        self.review['inherited_origins'] = [copy.deepcopy(self.components[0]), copy.deepcopy(self.components[0])]
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'duplicate original execution'):
            self.validate()
        self.review['inherited_origins'] = []
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'nonempty original'):
            self.validate()

    def test_pending_other_case_and_early_approval_still_block(self):
        self.current['platforms']['windows-x64']['checks']['link_import']['status'] = 'pending'
        with self.assertRaisesRegex(release.GateError, 'not passed'):
            self.validate()
        self.current['platforms']['windows-x64']['checks']['link_import']['status'] = 'passed'
        self.current['approval']['approved_at'] = self.fixture.executed
        with self.assertRaisesRegex(release.GateError, 'approval'):
            self.validate()

    def test_source_collection_hash_checks_refs_and_only_returns_full_shas(self):
        commits = release.source_commits(self.current, self.root)
        self.assertEqual(commits, sorted([self.current['commit'], self.fixture.old_commit, self.second['commit']]))
        self.components[0]['origin']['sha256'] = '0' * 64
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'SHA-256 mismatch'):
            release.source_commits(self.current, self.root)

    def test_source_collection_rejects_non_sha_and_path_escape(self):
        self.second['commit'] = '$(command)'
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'full commit SHA'):
            release.source_commits(self.current, self.root)
        self.second['commit'] = 'c' * 40
        self.components[0]['origin']['path'] = '../outside'
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'inside its bundle'):
            release.source_commits(self.current, self.root)

    def test_real_git_and_cli_receipt_preserve_both_original_sources(self):
        f = self.fixture
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            def git(*args):
                return subprocess.check_output(['git', '-c', 'user.name=Contract fixture',
                    '-c', 'user.email=fixture@example.invalid', *args], cwd=repo, stderr=subprocess.PIPE).strip().decode()
            git('init', '-q')
            (repo / 'backend').mkdir()
            (repo / 'backend/asr.py').write_bytes(f.source_bytes)
            (repo / 'copy.py').write_text('old copy\n')
            git('add', '.'); git('commit', '-qm', 'original one')
            old = git('rev-parse', 'HEAD')
            (repo / 'copy.py').write_text('middle copy\n')
            git('add', '.'); git('commit', '-qm', 'original two')
            middle = git('rev-parse', 'HEAD')
            (repo / 'copy.py').write_text('current copy\n')
            git('add', '.'); git('commit', '-qm', 'current')
            current = git('rev-parse', 'HEAD')
            self.current['commit'] = f.fixture.commit = current
            f.fixture.build['head_sha'] = current
            (f.fixture.assets / internal.PROVENANCE).write_text(json.dumps(
                internal.provenance(f.fixture.version, current, f.fixture.assets, 123)))
            self.current['assets'] = release.assets_in(f.fixture.assets)
            originals = [copy.deepcopy(f.origin), self.second]
            f.git_patch.stop()
            actual_git = release.git_bytes
            for index, (origin, commit) in enumerate(zip(originals, [old, middle])):
                origin['commit'] = commit
                f.write(f'real-build-{index}.json', {'id': origin['build_run_id'], 'head_sha': commit,
                    'path': '.github/workflows/desktop-build.yml', 'status': 'completed',
                    'conclusion': 'success', 'updated_at': f.old_built})
                f.write(f'real-pv-{index}.json', {'schema_version': 1, 'commit': commit,
                    'build_run_id': origin['build_run_id'], 'assets': origin['assets']})
                origin.update(build=f.ref(f'real-build-{index}.json'), provenance=f.ref(f'real-pv-{index}.json'))
                f.write(f'real-origin-{index}.json', origin)
                f.write(f'real-diff-{index}.json', {'from_commit': commit, 'to_commit': current,
                    'diff_sha256': f.sha(actual_git(['diff', '--no-ext-diff', '--no-textconv', '--binary', commit, current, '--'], repo=repo))})
                self.components[index].update(origin=f.ref(f'real-origin-{index}.json'), diff=f.ref(f'real-diff-{index}.json'))
            self.review['target'] = f.target(f.platforms, f.label)
            f.fresh.update(f.target(f.platforms, f.label))
            f.write('fresh.json', f.fresh); self.review['fresh'] = [f.ref('fresh.json')]
            f.write('composition.json', self.review)
            with patch.object(release, 'git_bytes', side_effect=lambda args: actual_git(args, repo=repo)):
                self.validate()
            (repo / 'scripts').mkdir()
            for name in ('internal_acceptance.py', 'release_acceptance.py'):
                (repo / 'scripts' / name).write_bytes((Path(release.__file__).parent / name).read_bytes())
            f.write('manifest.json', self.current); f.write('build.json', f.fixture.build); f.write('jobs.json', f.fixture.jobs)
            bundle = self.root / 'composed-accepted'
            result = subprocess.run([sys.executable, str(repo / 'scripts/internal_acceptance.py'), 'validate',
                '--version', f.fixture.version, '--commit', current, '--assets', str(f.fixture.assets),
                '--manifest', str(self.root / 'manifest.json'), '--build-run', str(self.root / 'build.json'),
                '--build-jobs', str(self.root / 'jobs.json'), '--acceptance-run-id', '456', '--bundle', str(bundle)],
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            receipt = json.loads((bundle / 'receipt.json').read_text())
            self.assertEqual(receipt['schema_version'], 1)
            self.assertEqual(receipt['commit'], current)
            self.assertEqual(receipt['evidence_contract'], 'impact-inheritance/v2')
            for name in ('real-origin-0.json', 'real-origin-1.json', 'real-build-0.json',
                         'real-build-1.json', 'real-pv-0.json', 'real-pv-1.json', 'real-diff-0.json', 'real-diff-1.json'):
                self.assertEqual((bundle / name).read_bytes(), (self.root / name).read_bytes())
            internal.check_receipt(receipt, f.fixture.version, current, {'id': 456,
                'path': '.github/workflows/internal-acceptance.yml', 'event': 'workflow_dispatch',
                'status': 'completed', 'conclusion': 'success'})
            result = subprocess.run([sys.executable, str(repo / 'scripts/release_acceptance.py'),
                'source-commits', '--manifest', str(bundle / 'acceptance.json')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(result.stdout.splitlines(), sorted([old, middle, current]))
            missing = copy.deepcopy(originals[1])
            missing['commit'] = 'f' * 40
            f.write('missing-build.json', {'id': missing['build_run_id'], 'head_sha': missing['commit'],
                'path': '.github/workflows/desktop-build.yml', 'status': 'completed',
                'conclusion': 'success', 'updated_at': f.old_built})
            f.write('missing-pv.json', {'schema_version': 1, 'commit': missing['commit'],
                'build_run_id': missing['build_run_id'], 'assets': missing['assets']})
            missing.update(build=f.ref('missing-build.json'), provenance=f.ref('missing-pv.json'))
            f.write('missing-origin.json', missing)
            f.write('missing-diff.json', {'from_commit': missing['commit'], 'to_commit': current,
                                        'diff_sha256': '0' * 64})
            self.components[1].update(origin=f.ref('missing-origin.json'), diff=f.ref('missing-diff.json'))
            f.write('composition.json', self.review)
            with patch.object(release, 'git_bytes', side_effect=lambda args: actual_git(args, repo=repo)):
                with self.assertRaisesRegex(release.GateError, 'source objects unavailable'):
                    self.validate()

    def test_release_composition_still_requires_current_observation(self):
        fixture = release_tests.AcceptanceTests('test_complete_evidence_passes')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.current['commit'] = fixture.commit
        fixture.manifest['evidence_contract'] = 'impact-inheritance/v2'
        fixture.manifest['platforms']['macos-arm64']['checks']['local_without_subtitles'] = copy.deepcopy(self.fixture.row)
        self.current = fixture.manifest
        self.fixture.current = self.current
        for p in self.root.iterdir():
            if p.is_file():
                (fixture.root / p.name).write_bytes(p.read_bytes())
        self.root = self.fixture.root = fixture.root
        self.review['target'] = self.fixture.target(self.fixture.platforms, self.fixture.label)
        self.fixture.fresh.update(self.fixture.target(self.fixture.platforms, self.fixture.label))
        self.sync()
        with self.assertRaisesRegex(release.GateError, 'acceptance finished after observation'):
            fixture.validate()
        fixture.manifest['observation']['ended_at'] = fixture.now.isoformat()
        fixture.validate()
        fixture.manifest['observation']['evidence_mode'] = 'inherited'
        with self.assertRaisesRegex(release.GateError, 'observation cannot be inherited'):
            fixture.validate()


if __name__ == '__main__':
    unittest.main()
