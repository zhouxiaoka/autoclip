import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('windows_desktop_crt', ROOT / 'scripts/windows_desktop_crt.py')
crt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crt)


def image(name, *, delayed=False):
    data = bytearray(2048)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, 1)
    struct.pack_into('<H', data, 0x94, 240)
    optional = 0x98
    struct.pack_into('<H', data, optional, 0x20b)
    struct.pack_into('<Q', data, optional + 24, 0x140000000)
    struct.pack_into('<I', data, optional + 60, 512)
    struct.pack_into('<I', data, optional + 108, 16)
    struct.pack_into('<IIII', data, optional + 240 + 8, 1536, 0x1000, 1536, 512)
    directory = 13 if delayed else 1
    struct.pack_into('<II', data, optional + 112 + directory * 8, 0x1000, 64 if delayed else 40)
    if delayed:
        struct.pack_into('<II', data, 512, 1, 0x1100)
    else:
        struct.pack_into('<I', data, 512 + 12, 0x1100)
    encoded = name.encode() + b'\0'
    data[768:768 + len(encoded)] = encoded
    return bytes(data)


class WindowsDesktopCRTTests(unittest.TestCase):
    def test_os_dll_imports_are_read_without_loading_the_executable(self):
        self.assertEqual(crt.imported_dlls(image('KERNEL32.dll')), ['kernel32.dll'])

    def test_missing_runtime_is_found_in_normal_and_delayed_imports(self):
        import tempfile
        for delayed in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'desktop.exe'
                path.write_bytes(image('VCRUNTIME140_1.dll', delayed=delayed))
                result = crt.verify(path)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['external_visual_cpp_runtime'], ['vcruntime140_1.dll'])

    def test_truncated_or_non_pe_files_cannot_pass(self):
        for value in (b'', image('kernel32.dll')[:600], b'MZ' + b'\0' * 200):
            with self.assertRaises(ValueError):
                crt.imported_dlls(value)

    def test_unresolvable_import_name_cannot_be_ignored(self):
        data = bytearray(image('kernel32.dll'))
        struct.pack_into('<I', data, 512 + 12, 0x900000)
        with self.assertRaises(ValueError):
            crt.imported_dlls(bytes(data))


if __name__ == '__main__':
    unittest.main()
