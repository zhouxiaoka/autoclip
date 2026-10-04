#!/usr/bin/env python3
"""Verify app-local Python CRT contents and actual Windows DLL resolution.

The signed release files come from Visual Studio's official Redist folder at
build time. This supplements the desktop executable's static CRT guard; optional
Python extensions need a matching dynamic C++ runtime on users' machines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from windows_desktop_crt import imported_dlls

REQUIRED = frozenset({
    'concrt140.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll', 'msvcp140_codecvt_ids.dll',
    'vcruntime140.dll', 'vcruntime140_1.dll',
})
MINIMUM = (14, 44, 35211, 0)


def version(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', value):
        raise ValueError('invalid CRT version')
    return tuple(map(int, value.split('.')))


def verify(directory: Path) -> dict:
    directory = directory.resolve(strict=True)
    manifest = json.loads((directory / 'windows-crt.json').read_text(encoding='utf-8-sig'))
    if (manifest.get('schema_version') != 1 or manifest.get('source') != 'visual-studio-redist'
            or manifest.get('architecture') != 'x64'):
        raise ValueError('invalid official x64 CRT manifest')
    selected, minimum = version(manifest['version']), version(manifest['minimum_version'])
    if minimum < MINIMUM or selected < minimum:
        raise ValueError('CRT is older than portable Python requires')
    entries = manifest['files']
    if not isinstance(entries, list) or not entries:
        raise ValueError('missing CRT DLL entries')
    names = set()
    checked = []
    for entry in entries:
        name = entry['name']
        if (not isinstance(name, str) or not re.fullmatch(
                r'(?:msvcp140(?:_[a-z0-9_]+)?|vcruntime140(?:_[a-z0-9_]+)?|concrt140|vccorlib140)\.dll', name)
                or name in names):
            raise ValueError('unsafe or duplicate CRT DLL name')
        names.add(name)
        if (entry.get('signature_status') != 'Valid' or entry.get('signer') != 'Microsoft Corporation'
                or entry.get('architecture') != 'x64' or version(entry['file_version']) != selected):
            raise ValueError('CRT provenance, architecture or version mismatch')
        path = directory / name
        if path.is_symlink() or path.resolve(strict=True).parent != directory:
            raise ValueError('CRT DLL must be inside portable Python')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != entry['size'] or digest != entry['sha256']:
            raise ValueError('CRT DLL digest mismatch: ' + name)
        checked.append({'name': name, 'sha256': digest, 'imports': imported_dlls(data)})
    if not REQUIRED <= names:
        raise ValueError('incomplete application-local CRT set')
    for path in (directory / 'python.exe', *directory.glob('python3*.dll')):
        # PBS python3.dll is the stable-ABI forwarding shim: its real ordinary
        # and delayed import directories are both zero. Keep every other image
        # on the default nonempty-import rule.
        checked.append({'name': path.name, 'imports': imported_dlls(
            path.read_bytes(), allow_no_imports=path.name.lower() == 'python3.dll')})
    for image in checked:
        missing = [name for name in image['imports']
                   if (name.startswith(('vcruntime', 'msvcp', 'concrt', 'vccorlib')) or name == 'msvcrtd.dll')
                   and name not in names]
        if missing:
            raise ValueError('unbundled C++ runtime imports: ' + ','.join(missing))
    return {'status': 'passed', 'source': manifest['source'], 'architecture': 'x64',
            'version': manifest['version'], 'minimum_version': manifest['minimum_version'], 'files': checked}


def loaded_paths(directory: Path, *, require_msvcp: bool = True) -> dict:
    """Inspect already loaded modules; do not preload DLLs to mask inference failures."""
    if sys.platform != 'win32':
        raise RuntimeError('Windows loaded-module verification required')
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel.GetModuleHandleW.restype = wintypes.HMODULE
    kernel.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetModuleFileNameW.restype = wintypes.DWORD
    directory = directory.resolve(strict=True)
    result = {}
    for name in sorted(REQUIRED):
        handle = kernel.GetModuleHandleW(name)
        if not handle:
            continue
        buffer = ctypes.create_unicode_buffer(32768)
        count = kernel.GetModuleFileNameW(handle, buffer, len(buffer))
        if not count or count >= len(buffer):
            raise ctypes.WinError(ctypes.get_last_error())
        if Path(buffer.value).resolve(strict=True) != (directory / name).resolve(strict=True):
            raise RuntimeError('C++ runtime loaded outside portable Python: ' + name)
        result[name] = 'portable_python_directory'
    if require_msvcp and 'msvcp140.dll' not in result:
        raise RuntimeError('Whisper must load application-local msvcp140.dll')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.python_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'status': 'failed', 'error': str(error)}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    return int(result['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
