"""Desktop Build may overlap full tests with packaging, and still fail closed."""
from __future__ import annotations

import hashlib
import json
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import platform_qa_ready as qa
import release_acceptance as release

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github' / 'workflows' / 'desktop-build.yml'
FINAL_JOBS = (
    'candidate-gate', 'ci-guards', 'source-quality', 'sensevoice-runtime',
    'whisper-runtime', 'provider-e2e', 'build-macos-arm64', 'build-windows-x64',
    'smoke-windows-x64',
)
PACKAGING_JOBS = ('build-macos-arm64', 'build-windows-x64')


def workflow_jobs(text: str) -> dict[str, str]:
    body = text.split('\njobs:\n', 1)[1]
    jobs: dict[str, list[str]] = {}
    name = None
    for line in body.splitlines():
        if line.startswith('  ') and not line.startswith('   ') and line.endswith(':') and not line.lstrip().startswith('#'):
            name = line.strip()[:-1]
            jobs[name] = []
        elif name is not None:
            jobs[name].append(line)
    return {key: '\n'.join(value) for key, value in jobs.items()}


def field(body: str, key: str) -> str:
    prefix = f'    {key}:'
    for line in body.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    raise AssertionError(f'missing {key}')


def listed(value: str) -> list[str]:
    value = value.strip()
    if value.startswith('[') and value.endswith(']'):
        return [part.strip() for part in value[1:-1].split(',') if part.strip()]
    return [value]


def gate_allows(expr: str, results: dict[str, str], event: str, ref: str) -> bool:
    for part in (piece.strip() for piece in expr.split('&&')):
        if part == "github.event_name == 'workflow_dispatch'":
            if event != 'workflow_dispatch':
                return False
        elif part == "startsWith(github.ref, 'refs/tags/v')":
            if not ref.startswith('refs/tags/v'):
                return False
        else:
            match = re.fullmatch(r"needs\.([A-Za-z0-9_-]+)\.result == 'success'", part)
            if match is None:
                raise AssertionError(f'unparsed gate term: {part}')
            if results.get(match.group(1)) != 'success':
                return False
    return True


def bash(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['bash', '-c', script], cwd=ROOT, capture_output=True, text=True, check=False)


class DesktopBuildWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding='utf-8')
        cls.jobs = workflow_jobs(cls.text)
        cls.pins = {}
        for line in (ROOT / 'scripts/lib/desktop_toolchain.env').read_text(encoding='utf-8').splitlines():
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                cls.pins[key] = value

    def test_dispatch_and_tags_keep_minimum_permissions(self):
        header = self.text.split('\njobs:\n', 1)[0]
        self.assertIn('workflow_dispatch:', header)
        self.assertIn("tags:", header)
        self.assertNotIn('pull_request:', header)
        self.assertNotIn('schedule:', header)
        self.assertNotIn('workflow_run:', header)
        self.assertIn('contents: write', header)
        self.assertIn('actions: read', header)
        self.assertIn('issues: write', header)
        self.assertNotIn('contents: write\n  actions: write', header)
        self.assertNotIn('cargo install tauri-cli', self.text)
        self.assertNotIn('dtolnay/rust-toolchain@stable', self.text)
        self.assertNotIn("toolchain: stable", self.text)
        self.assertNotIn('^2.0', self.text)
        self.assertNotIn('casefold', self.text)
        self.assertNotIn('FailureHint', self.text)
        self.assertEqual(self.text.count('python scripts/ci_guards.py'), 1)

    def test_packaging_waits_for_the_shared_guard_and_not_the_full_suite(self):
        self.assertNotIn('needs:', self.jobs['ci-guards'])
        self.assertIn('python scripts/ci_guards.py', self.jobs['ci-guards'])
        for name in PACKAGING_JOBS:
            self.assertEqual(listed(field(self.jobs[name], 'needs')), ['candidate-gate', 'ci-guards'])
            self.assertNotIn('source-quality', field(self.jobs[name], 'needs'))
            self.assertNotIn('sensevoice-runtime', field(self.jobs[name], 'needs'))
            self.assertNotIn('whisper-runtime', field(self.jobs[name], 'needs'))
            setup = self.jobs[name]
            self.assertNotIn('Run CI guards', setup)
            self.assertLess(self.text.index('name: ci-guards'), self.text.index(f'  {name}:'))
            self.assertIn('Remove restored installers from the Rust cache', setup)
            self.assertLess(setup.index('Cache Rust build'), setup.index('Remove restored installers'))
            self.assertLess(setup.index('Remove restored installers'), setup.index('Install pinned Tauri CLI'))
            self.assertLess(setup.index('Install pinned Tauri CLI'), setup.index('Build desktop app (PBS route)'))
            self.assertIn('Keep shipped bundles out of the Rust cache', setup)

    def test_quality_failure_blocks_the_final_gate_without_mixing_runs(self):
        self.assertIn('ci-guards', release.BUILD_JOBS)
        for job_name in ('internal-provenance', 'release'):
            body = self.jobs[job_name]
            self.assertEqual(listed(field(body, 'needs')), list(FINAL_JOBS))
            expr = field(body, 'if')
            for required in FINAL_JOBS:
                self.assertIn(f"needs.{required}.result == 'success'", expr)
            success = {name: 'success' for name in FINAL_JOBS}
            self.assertTrue(gate_allows(expr, success, 'workflow_dispatch', 'refs/heads/integration/1.5.9-rc')
                            if job_name == 'internal-provenance'
                            else not gate_allows(expr, success, 'workflow_dispatch', 'refs/heads/integration/1.5.9-rc'))
            self.assertTrue(gate_allows(expr, success, 'push', 'refs/tags/v1.5.9')
                            if job_name == 'release'
                            else not gate_allows(expr, success, 'push', 'refs/tags/v1.5.9'))
            for failed in FINAL_JOBS:
                broken = dict(success, **{failed: 'failure'})
                self.assertFalse(gate_allows(expr, broken, 'workflow_dispatch', 'refs/heads/integration/1.5.9-rc'))
                self.assertFalse(gate_allows(expr, broken, 'push', 'refs/tags/v1.5.9'))
                skipped = dict(success, **{failed: 'skipped'})
                self.assertFalse(gate_allows(expr, skipped, 'workflow_dispatch', 'refs/heads/integration/1.5.9-rc'))
        for body in (self.jobs['internal-provenance'], self.jobs['release']):
            self.assertIn('"$GITHUB_SHA"', body)
            self.assertIn('"$GITHUB_RUN_ID"', body)
            self.assertNotIn('github.event.inputs', body)
        self.assertIn('pattern: autoclip-desktop-*', self.jobs['internal-provenance'])
        self.assertNotIn('platform-qa-ready', self.jobs['internal-provenance'])
        self.assertNotIn('gh run download', self.jobs['build-macos-arm64'])
        self.assertNotIn('gh run download', self.jobs['build-windows-x64'])

    def test_cache_keys_separate_tools_from_packages(self):
        for name, ffmpeg in (
            ('build-macos-arm64', 'scripts/ffmpeg-macos-arm64.env'),
            ('build-windows-x64', 'scripts/ffmpeg-win64.env'),
        ):
            body = self.jobs[name]
            self.assertIn(
                "desktop-tool-tauri-cli-${{ runner.os }}-${{ runner.arch }}-${{ steps.pins.outputs.tauri_cli }}",
                body,
            )
            self.assertIn(
                "desktop-download-${{ runner.os }}-${{ runner.arch }}-${{ hashFiles('scripts/lib/desktop_download_pins.env', '"
                + ffmpeg + "') }}",
                body,
            )
            download = body[body.index('Cache portable Python'):body.index('Cache pinned Tauri CLI')]
            self.assertNotIn('build_macos_arm.sh', download)
            self.assertNotIn('build_windows_x64.sh', download)
            self.assertNotIn('desktop_build_common.sh', download)
            self.assertNotIn('ffmpeg_pin.sh', download)
            self.assertNotIn('restore-keys:', body)
            self.assertIn('path: build/tool-cache/tauri-cli', body)
            self.assertIn('build/pbs-cache', body)
            self.assertIn('build/ffmpeg-cache', body)
            cache_blocks = body.split('uses: actions/cache@v4')[1:]
            for block in cache_blocks:
                head = block.split('- name:', 1)[0]
                self.assertNotIn('src-tauri/target/release/bundle', head)
                self.assertNotIn('src-tauri/resources', head)
                self.assertNotIn('.env', head.replace('ffmpeg-macos-arm64.env', '').replace('ffmpeg-win64.env', '').replace('desktop_download_pins.env', ''))
            self.assertIn('cache: npm', body)
            self.assertIn('cache-dependency-path: frontend/package-lock.json', body)
            self.assertIn('node-version: ${{ steps.pins.outputs.node }}', body)
            self.assertIn(f"dtolnay/rust-toolchain@{self.pins['RUSTUP_ACTION_SHA']}", body)
            self.assertIn('toolchain: ${{ steps.pins.outputs.rust }}', body)
            self.assertIn('workspaces: src-tauri', body)
            self.assertIn('cache-on-failure: false', body)
            self.assertIn('cache-bin: false', body)
        self.assertEqual(self.jobs['build-macos-arm64'].count('runs-on: macos-15'), 1)
        self.assertIn('runs-on: windows-latest', self.jobs['build-windows-x64'])
        self.assertIn('targets: aarch64-apple-darwin', self.jobs['build-macos-arm64'])
        self.assertIn('targets: x86_64-pc-windows-msvc', self.jobs['build-windows-x64'])
        self.assertEqual(self.pins['MACOS_RUNNER'], 'macos-15')
        self.assertEqual(self.pins['WINDOWS_RUNNER'], 'windows-latest')
        self.assertEqual(self.pins['NODE_VERSION'], '20.20.2')
        self.assertEqual(self.pins['RUST_TOOLCHAIN'], '1.100.0')
        self.assertEqual(self.pins['TAURI_CLI_VERSION'], '2.12.5')

    def test_platform_scripts_drop_restored_bundles_before_packaging(self):
        for name in ('build_macos_arm.sh', 'build_macos_intel.sh', 'build_windows_x64.sh'):
            text = (ROOT / 'scripts' / name).read_text(encoding='utf-8')
            self.assertLess(text.index('clean_shipped_bundles'), text.index('cargo tauri build'))


class PinAndQaTests(unittest.TestCase):
    def test_pin_files_reject_ranges_and_bind_official_urls(self):
        result = bash(textwrap.dedent("""
            set -euo pipefail
            source scripts/lib/desktop_pins.sh
            load_desktop_pins "$PWD"
            test "$(tauri_cli_asset_url "$TAURI_CLI_VERSION" "$MACOS_TARGET")" = \
                "https://github.com/tauri-apps/tauri/releases/download/tauri-cli-v2.12.5/cargo-tauri-aarch64-apple-darwin.zip"
            test "$(tauri_cli_asset_url "$TAURI_CLI_VERSION" "$WINDOWS_TARGET")" = \
                "https://github.com/tauri-apps/tauri/releases/download/tauri-cli-v2.12.5/cargo-tauri-x86_64-pc-windows-msvc.zip"
            test "$(tauri_cli_sha256_for "$MACOS_TARGET")" = "$TAURI_CLI_SHA256_aarch64_apple_darwin"
            test "$(pbs_sha256_for_triple x86_64-pc-windows-msvc)" = "$PBS_SHA256_x86_64_pc_windows_msvc"
            if tauri_cli_asset_url '^2.0' aarch64-apple-darwin >/dev/null 2>&1; then exit 2; fi
            if tauri_cli_target_for Linux x86_64 >/dev/null 2>&1; then exit 3; fi
            printf '%s\\n' "$PBS_VERSION $PBS_PYTHON_VERSION"
        """))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('20260510 3.13.13', result.stdout)

    def test_cached_download_must_match_its_sha256(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'payload'
            path.write_bytes(b'portable-python')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            ok = bash(f'source scripts/lib/desktop_pins.sh && verify_sha256_file "{path}" "{digest}"')
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertTrue(path.is_file())
            bad = bash(f'source scripts/lib/desktop_pins.sh && verify_sha256_file "{path}" "{"0"*64}"')
            self.assertNotEqual(bad.returncode, 0)
            self.assertFalse(path.exists())

    def test_tauri_zip_extract_rejects_traversal_and_checks_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad_zip = root / 'bad.zip'
            with zipfile.ZipFile(bad_zip, 'w') as archive:
                archive.writestr('../cargo-tauri', 'echo bad\n')
            escaped = bash(
                f'source scripts/install_tauri_cli.sh && extract_tauri_binary "{bad_zip}" "{root}/out" cargo-tauri'
            )
            self.assertNotEqual(escaped.returncode, 0, escaped.stdout + escaped.stderr)
            good_zip = root / 'good.zip'
            with zipfile.ZipFile(good_zip, 'w') as archive:
                info = zipfile.ZipInfo('cargo-tauri')
                info.external_attr = stat.S_IFREG | 0o755
                archive.writestr(info, '#!/bin/sh\necho "tauri-cli 2.12.5"\n')
            extracted = bash(
                f'source scripts/install_tauri_cli.sh && extract_tauri_binary "{good_zip}" "{root}/out" cargo-tauri'
                f' && source scripts/lib/desktop_pins.sh'
                f' && assert_tauri_cli_output 2.12.5 "$("{root}/out/cargo-tauri" --version)"'
            )
            self.assertEqual(extracted.returncode, 0, extracted.stdout + extracted.stderr)
            wrong = bash(
                f'source scripts/lib/desktop_pins.sh && assert_tauri_cli_output 2.12.4 "$("{root}/out/cargo-tauri" --version)"'
            )
            self.assertNotEqual(wrong.returncode, 0)

    def test_platform_qa_marker_cannot_authorize_another_commit_or_release(self):
        commit = 'a' * 40
        other = 'b' * 40
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / 'assets'
            assets.mkdir()
            (assets / 'AutoClip_1.5.9_aarch64.dmg').write_bytes(b'dmg')
            (assets / 'AutoClip_1.5.9_aarch64.app.tar.gz').write_bytes(b'tar')
            output = Path(temp) / 'platform-qa-ready.json'
            record = qa.write_record('macos-arm64', commit, 44272188938, assets, output)
            self.assertFalse(record['release_ready'])
            self.assertEqual(record['stage'], 'platform-qa-ready')
            self.assertEqual(record['commit'], commit)
            self.assertEqual(record['build_run_id'], 44272188938)
            again = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(again, record)
            with self.assertRaises(release.GateError):
                release.assert_not_platform_qa(record)
            other_record = qa.build_record('macos-arm64', other, 44272188939, assets)
            self.assertNotEqual(other_record['commit'], record['commit'])
            self.assertNotEqual(other_record['build_run_id'], record['build_run_id'])
            for forbidden in ('internal-build-provenance.json', 'build-provenance.json'):
                with self.assertRaises(ValueError):
                    qa.write_record('macos-arm64', commit, 1, assets, Path(temp) / forbidden)
            with self.assertRaises(ValueError):
                qa.build_record('macos-arm64', 'A' * 40, 1, assets)
            with self.assertRaises(ValueError):
                qa.build_record('macos-arm64', commit, True, assets)
            empty = Path(temp) / 'empty'
            empty.mkdir()
            with self.assertRaises(ValueError):
                qa.build_record('windows-x64', commit, 1, empty)


if __name__ == '__main__':
    unittest.main()
