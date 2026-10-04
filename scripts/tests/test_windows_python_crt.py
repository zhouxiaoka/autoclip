"""The build runner's installed redist must not hide a missing packaged MSVCP."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    spec = importlib.util.spec_from_file_location('windows_python_crt', ROOT / 'scripts/windows_python_crt.py')
    crt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(crt)
finally:
    sys.path.pop(0)


def image(import_name='kernel32.dll', machine=0x8664):
    data = bytearray(2048)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, machine, 1)
    struct.pack_into('<H', data, 0x94, 240)
    optional = 0x98
    struct.pack_into('<H', data, optional, 0x20b)
    struct.pack_into('<Q', data, optional + 24, 0x140000000)
    struct.pack_into('<I', data, optional + 60, 512)
    struct.pack_into('<I', data, optional + 108, 16)
    struct.pack_into('<IIII', data, optional + 240 + 8, 1536, 0x1000, 1536, 512)
    struct.pack_into('<II', data, optional + 120, 0x1000, 40)
    struct.pack_into('<I', data, 524, 0x1100)
    encoded = import_name.encode() + b'\0'
    data[768:768 + len(encoded)] = encoded
    return bytes(data)


def bundle(directory):
    data = image()
    files = []
    for name in sorted(crt.REQUIRED):
        (directory / name).write_bytes(data)
        files.append({'name': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'file_version': '14.44.35211.0', 'architecture': 'x64',
                      'signature_status': 'Valid', 'signer': 'Microsoft Corporation'})
    (directory / 'python.exe').write_bytes(image('vcruntime140.dll'))
    value = {'schema_version': 1, 'source': 'visual-studio-redist', 'architecture': 'x64',
             'version': '14.44.35211.0', 'minimum_version': '14.44.35211.0', 'files': files}
    save(directory, value)
    return value


def save(directory, manifest):
    (directory / 'windows-crt.json').write_text(json.dumps(manifest), encoding='utf-8-sig')


def abi_shim():
    data = bytearray(image())
    struct.pack_into('<H', data, 0x96, 0x2022)  # IMAGE_FILE_DLL, as in actual PBS python3.dll.
    for index in (1, 13):
        struct.pack_into('<II', data, 0x98 + 112 + index * 8, 0, 0)
    return data


class WindowsPythonCRTTests(unittest.TestCase):
    def test_complete_official_set_and_dependency_closure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle(root)
            result = crt.verify(root)
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['version'], '14.44.35211.0')
            self.assertIn('msvcp140.dll', [row['name'] for row in result['files']])

    def test_python_abi_shim_can_have_no_import_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle(root)
            (root / 'python3.dll').write_bytes(abi_shim())
            result = crt.verify(root)
            shim = next(row for row in result['files'] if row['name'] == 'python3.dll')
            self.assertEqual(shim['imports'], [])
            self.assertEqual(result['status'], 'passed')

    def test_empty_abi_shim_requires_real_dll_and_complete_bounded_pe(self):
        modes = ('not-dll', 'x86', 'normal-rva-only', 'normal-size-only',
                 'delay-rva-only', 'delay-size-only', 'empty-table', 'outside-table',
                 'zero-sections', 'raw-outside-file', 'raw-overlaps-header',
                 'oversized-headers', 'undersized-headers', 'truncated-optional',
                 'truncated-section')
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                bundle(root)
                data = abi_shim()
                optional = 0x98
                if mode == 'not-dll':
                    struct.pack_into('<H', data, 0x96, 0x22)
                elif mode == 'x86':
                    struct.pack_into('<H', data, 0x84, 0x14c)
                elif mode.endswith('rva-only') or mode.endswith('size-only'):
                    index = 13 if mode.startswith('delay') else 1
                    rva, size = (0x1000, 0) if mode.endswith('rva-only') else (0, 40)
                    struct.pack_into('<II', data, optional + 112 + index * 8, rva, size)
                elif mode in ('empty-table', 'outside-table'):
                    struct.pack_into('<II', data, optional + 120,
                                     0x900000 if mode == 'outside-table' else 0x1000, 40)
                    data[512:552] = bytes(40)
                elif mode == 'zero-sections':
                    struct.pack_into('<H', data, 0x86, 0)
                elif mode in ('raw-outside-file', 'raw-overlaps-header'):
                    struct.pack_into('<I', data, optional + 240 + 20,
                                     4096 if mode == 'raw-outside-file' else 0)
                elif mode in ('oversized-headers', 'undersized-headers'):
                    struct.pack_into('<I', data, optional + 60,
                                     4096 if mode == 'oversized-headers' else 400)
                elif mode == 'truncated-optional':
                    data = data[:optional + 239]
                else:
                    data = data[:optional + 240 + 39]
                (root / 'python3.dll').write_bytes(data)
                with self.assertRaises(ValueError):
                    crt.verify(root)

    def test_no_import_exception_is_limited_to_python3_dll(self):
        for name in ('python.exe', 'python313.dll', 'msvcp140.dll'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                value = bundle(root)
                data = bytes(abi_shim())
                (root / name).write_bytes(data)
                if name == 'msvcp140.dll':
                    next(row for row in value['files'] if row['name'] == name)['sha256'] = hashlib.sha256(data).hexdigest()
                    save(root, value)
                with self.assertRaisesRegex(ValueError, 'no identifiable imported DLLs'):
                    crt.verify(root)

    def test_old_package_with_vcruntime_but_no_msvcp_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            value = bundle(root)
            value['files'] = [row for row in value['files'] if row['name'].startswith('vcruntime')]
            save(root, value)
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                crt.verify(root)

    def test_tampered_file_wrong_machine_and_missing_dependency_are_rejected(self):
        for mode in ('tamper', 'x86', 'missing-dependency'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                value = bundle(root)
                name = 'msvcp140.dll'
                if mode == 'tamper':
                    (root / name).write_bytes(b'damaged')
                else:
                    data = image(machine=0x14c) if mode == 'x86' else image('vcruntime140_threads.dll')
                    (root / name).write_bytes(data)
                    entry = next(row for row in value['files'] if row['name'] == name)
                    entry['sha256'] = hashlib.sha256(data).hexdigest()
                    save(root, value)
                with self.assertRaises(ValueError):
                    crt.verify(root)

    def test_non_official_mixed_or_old_versions_are_rejected(self):
        for mode in ('unsigned', 'wrong-signer', 'mixed', 'old'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                value = bundle(root)
                if mode == 'unsigned':
                    value['files'][0]['signature_status'] = 'NotSigned'
                elif mode == 'wrong-signer':
                    value['files'][0]['signer'] = 'Other Corporation'
                elif mode == 'mixed':
                    value['files'][0]['file_version'] = '14.0.24215.1'
                else:
                    value['version'] = '14.0.24215.1'
                    value['minimum_version'] = '14.0.24215.1'
                save(root, value)
                with self.assertRaises(ValueError):
                    crt.verify(root)

    def test_unsafe_names_and_duplicate_entries_cannot_pass(self):
        for mode in ('path', 'duplicate', 'symlink'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                value = bundle(root)
                if mode == 'path':
                    value['files'][0]['name'] = '../msvcp140.dll'
                elif mode == 'duplicate':
                    value['files'].append(value['files'][0])
                else:
                    path = root / value['files'][0]['name']
                    target = root / 'untrusted.dll'
                    path.rename(target)
                    path.symlink_to(target)
                save(root, value)
                with self.assertRaises(ValueError):
                    crt.verify(root)

    def test_loaded_module_inspection_rejects_system_runtime_without_preloading(self):
        import ctypes
        class Function:
            def __init__(self, callback):
                self.callback = callback
            def __call__(self, *args):
                return self.callback(*args)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle(root)
            system = root / 'system32'
            system.mkdir()
            (system / 'msvcp140.dll').write_bytes(image())
            for outside in (False, True):
                location = (system if outside else root) / 'msvcp140.dll'
                def filename(_handle, buffer, _length):
                    buffer.value = str(location)
                    return len(buffer.value)
                class Kernel:
                    GetModuleHandleW = Function(lambda name: 1 if name == 'msvcp140.dll' else None)
                    GetModuleFileNameW = Function(filename)
                with patch.object(crt.sys, 'platform', 'win32'), patch.object(ctypes, 'WinDLL', lambda *a, **k: Kernel(), create=True):
                    if outside:
                        with self.assertRaisesRegex(RuntimeError, 'outside portable Python'):
                            crt.loaded_paths(root)
                    else:
                        self.assertEqual(crt.loaded_paths(root), {'msvcp140.dll': 'portable_python_directory'})


if __name__ == '__main__':
    unittest.main()
