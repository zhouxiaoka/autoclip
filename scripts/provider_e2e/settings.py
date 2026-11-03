"""Write an isolated ai-model-settings.json for one e2e case."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_data_dir(data_dir: Path, *, base_url: str, api_key: str, provider: str, model: str) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / 'logs').mkdir(parents=True, exist_ok=True)
    (data_dir / 'privacy.json').write_text(
        json.dumps({'analytics': False, 'crash_reports': False}), encoding='utf-8')
    settings = {
        'version': 1,
        'connections': [{
            'id': 'e2e',
            'name': 'provider-e2e',
            'provider': provider,
            'base_url': base_url,
            'api_key': api_key,
            'image_api': 'auto',
            'image_base_url': '',
        }],
        'analysis': {'connection_id': 'e2e', 'model': model, 'capability': 'text'},
        'vision': None,
        'cover': None,
        'transcription': {'provider': 'whisper_local', 'model': 'base'},
        'cover_enabled': False,
        'allow_send_frame': False,
        'cover_choice_version': 1,
        'cover_ocr_model': '',
        'vision_timeout': 30,
        'analysis_mode': 'subtitle',
        'allow_visual_screening': False,
        'chunk_size': 5000,
        'min_score_threshold': 0.1,
        'max_clips_per_collection': 5,
    }
    path = data_dir / 'ai-model-settings.json'
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def live_ready(provider: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    key = (env.get(provider['secret']) or '').strip()
    configured = (env.get(provider['model_env']) or '').strip()
    default_model = (provider.get('default_model') or '').strip()
    model = configured or default_model
    if not key:
        return {'ready': False, 'reason': f"{provider['secret']} unset"}
    if not model:
        return {'ready': False, 'reason': f"{provider['model_env']} unset and no default"}
    return {
        'ready': True,
        'api_key': key,
        'model': model,
        'model_source': 'secret' if configured else 'default',
        'provider': provider['provider'],
        'base_url': provider['base_url'],
    }
