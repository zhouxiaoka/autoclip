"""Build a CLI/MCP handoff ZIP from explicit public files, never local data."""
import argparse
import hashlib
import json
import subprocess
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(wheel: Path, out: Path):
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    if wheel.name != f'autoclip-{version}-py3-none-any.whl':
        raise ValueError('wheel does not match the source release version')
    with zipfile.ZipFile(wheel) as archive:
        for name in ('backend/assets/models/face_detection_yunet_2023mar.onnx',
                     'backend/assets/models/face_detection_yunet-LICENSE.txt'):
            if name not in archive.namelist():
                raise ValueError(f'missing wheel resource: {name}')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    instructions = f'''# AutoClip {version} CLI / MCP

Python 3.11+ and FFmpeg/FFprobe are required. In a fresh virtual environment:

```sh
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps {wheel.name}
python -m pip install 'opencv-python-headless>=4.10'
autoclip --version
autoclip produce /absolute/path/video.mp4 --srt /absolute/path/video.srt --platform douyin --portrait-style podcast --json
```

Use the virtual environment's absolute autoclip path with args ["mcp"] in an MCP client.
Tools: start_quick_output / get_quick_output_status / get_version.
portrait_style: auto / interview / podcast. Platform controls language; layout is independent.
The default configuration shares the desktop's saved AI settings. For isolation set AUTOCLIP_DATA_DIR.
See CLI_AND_MCP.md for setup and API options. Credentials and user data are not included.
If replacing an earlier 1.5.0 candidate, --force-reinstall is required.
Source commit: {commit}
'''
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(wheel, wheel.name)
        for source, name in [('requirements.txt', 'requirements.txt'),
                             ('docs/CLI_AND_MCP.md', 'CLI_AND_MCP.md'),
                             ('docs/RELEASE_1_5.md', 'RELEASE_1_5.md'),
                             ('scripts/verify_python_wheel.py', 'verify_python_wheel.py')]:
            archive.write(ROOT / source, name)
        archive.writestr('README.md', instructions)
        archive.writestr('BUILD.json', json.dumps({'version': version, 'commit': commit, 'wheel_sha256': digest}, indent=2))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    build(args.wheel, args.out)
