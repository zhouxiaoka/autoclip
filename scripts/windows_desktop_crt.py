#!/usr/bin/env python3
"""Reject desktop PE binaries that require a separately installed Visual C++ runtime.

Inspect ordinary and delayed DLL imports directly, so a CI runner's installed
redistributable cannot hide dependencies missing on a clean Windows machine.
This check supplements installed-package/UI acceptance; it does not replace it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def imported_dlls(data: bytes) -> list[str]:
    def unpack(fmt, offset):
        if offset < 0 or offset + struct.calcsize(fmt) > len(data):
            raise ValueError('truncated PE image')
        return struct.unpack_from(fmt, data, offset)

    if data[:2] != b'MZ':
        raise ValueError('not a PE image')
    pe, = unpack('<I', 0x3c)
    if data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('invalid PE signature')
    machine, section_count = unpack('<HH', pe + 4)
    if machine != 0x8664:
        raise ValueError('desktop image must be Windows x64')
    optional_size, = unpack('<H', pe + 20)
    optional = pe + 24
    magic, = unpack('<H', optional)
    if magic != 0x20b or optional_size < 112:
        raise ValueError('invalid PE32+ optional header')
    image_base, = unpack('<Q', optional + 24)
    header_size, = unpack('<I', optional + 60)
    directory_count, = unpack('<I', optional + 108)
    if directory_count < 2 or directory_count > (optional_size - 112) // 8:
        raise ValueError('invalid PE directory count')
    sections = []
    for index in range(section_count):
        _, virtual, raw_size, raw = unpack('<IIII', optional + optional_size + index * 40 + 8)
        sections.append((virtual, raw_size, raw))

    def file_offset(rva, size=1):
        if rva < 0 or size <= 0:
            raise ValueError('invalid PE address')
        if rva < header_size:
            if rva + size <= min(header_size, len(data)):
                return rva
        for virtual, raw_size, raw in sections:
            if virtual <= rva and rva + size <= virtual + raw_size:
                offset = raw + rva - virtual
                if offset + size <= len(data):
                    return offset
        raise ValueError('PE directory points outside file-backed data')

    imports = set()
    for directory_index, descriptor_size in ((1, 20), (13, 32)):
        if directory_index >= directory_count:
            continue
        rva, size = unpack('<II', optional + 112 + directory_index * 8)
        if not rva and not size:
            continue
        if not rva or size < descriptor_size:
            raise ValueError('invalid PE import directory')
        offset = file_offset(rva, size)
        terminated = False
        for position in range(offset, offset + size - descriptor_size + 1, descriptor_size):
            words = unpack('<' + 'I' * (descriptor_size // 4), position)
            if not any(words):
                terminated = True
                break
            name_rva = words[3] if directory_index == 1 else words[1]
            if directory_index == 13 and not words[0] & 1:
                name_rva -= image_base
            name_offset = file_offset(name_rva)
            end = data.find(b'\0', name_offset, min(name_offset + 256, len(data)))
            if end < 0:
                raise ValueError('unterminated imported DLL name')
            name = data[name_offset:end].decode('ascii').lower()
            if not re.fullmatch(r'[\w.\-]+\.dll', name):
                raise ValueError('invalid imported DLL name')
            imports.add(name)
        if not terminated:
            raise ValueError('unterminated PE import descriptors')
    if not imports:
        raise ValueError('desktop image has no identifiable imported DLLs')
    return sorted(imports)


def verify(path: Path) -> dict:
    data = path.read_bytes()
    imports = imported_dlls(data)
    external = [name for name in imports if name.startswith(('vcruntime', 'msvcp', 'concrt')) or name == 'msvcrtd.dll']
    return {'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
            'imports': imports, 'external_visual_cpp_runtime': external,
            'status': 'failed' if external else 'passed'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.exe)
    except (OSError, ValueError, UnicodeError, struct.error) as error:
        result = {'file': args.exe.name, 'status': 'failed', 'error': str(error)}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    return int(result['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
