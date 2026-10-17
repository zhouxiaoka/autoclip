"""#418 R27 #408: preflight uses media_precheck through its public interface, never a private (_name) function."""
import ast
from pathlib import Path

from backend.pipeline import media_precheck

PREFLIGHT = Path(__file__).resolve().parents[1] / 'services' / 'studio' / 'preflight.py'


def test_preflight_uses_no_private_media_precheck_name():
    tree = ast.parse(PREFLIGHT.read_text(encoding='utf-8'))
    used = {node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'media_precheck'}
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and (node.module or '').endswith('media_precheck')
                for alias in node.names}
    private = sorted(name for name in used | imported if name.startswith('_'))
    assert not private, private
    assert 'ffmpeg_decode_duration' in used
    assert callable(media_precheck.ffmpeg_decode_duration)
