"""Scrub the real QA key (read from env, never printed) and the app's masked key form from evidence text files.

Usage: python3 redact.py EVIDENCE_DIR  (key from WINQA_MODEL_API_KEY, or legacy AUTOCLIP_QA_DASHSCOPE_KEY)
"""
import os, re, sys
from pathlib import Path
key = os.environ.get('WINQA_MODEL_API_KEY') or os.environ.get('AUTOCLIP_QA_DASHSCOPE_KEY', '')
hits = 0
for p in Path(sys.argv[1]).rglob('*'):
    if not p.is_file() or p.suffix.lower() not in ('.json', '.log', '.err', '.txt', '.md', '.cmd'):
        continue
    t = p.read_text(encoding='utf-8', errors='replace')
    n = t
    if key:
        n = n.replace(key, '***')
    n = re.sub(r'("api_key_masked"\s*:\s*")[^"]*(")', r'\1***\2', n)
    if key and len(key) > 8:
        n = n.replace(key[:3] + '…' + key[-3:], '***')
    if n != t:
        hits += 1
        p.write_text(n, encoding='utf-8')
print(f'redact: rewrote {hits} file(s)')
