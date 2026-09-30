"""Verified ASR routing, 2026-09-29. Only timestamp-capable adapters are selectable.

Sources and intentionally unsupported integrations: docs/AI_MODEL_CONFIGURATION.md.
The public/account catalog still determines availability, not this routing table.
"""
# 88API: https://88api.ai/zh/docs/api/audio/openai-audio/
MODELS = {
    'api88': ['whisper-1'],
    'openai': ['whisper-1', 'gpt-4o-transcribe-diarize', 'gpt-4o-transcribe', 'gpt-4o-mini-transcribe'],
    'dashscope': ['qwen-audio-3.1-asr-flash', 'qwen-audio-3.0-asr-flash', 'fun-asr-flash-2026-06-15',
                  'qwen-audio-3.1-asr-flash-filetrans', 'qwen-audio-3.0-asr-flash-filetrans',
                  'qwen3-asr-flash-filetrans', 'qwen3-asr-flash', 'fun-asr', 'paraformer-v2'],
    'glm': ['glm-asr-2512'],
    'siliconflow': ['FunAudioLLM/SenseVoiceSmall'],
}
DASHSCOPE_SYNC = frozenset(MODELS['dashscope'][:3])


def adapter(provider, model):
    if provider == 'api88':
        return 'openai' if model == 'whisper-1' else None
    if provider == 'dashscope' and model in DASHSCOPE_SYNC:
        return 'dashscope'
    if provider in {'openai', 'infistar', 'compatible'}:
        if model == 'gpt-4o-transcribe-diarize':
            return 'diarized'
        if model == 'whisper-1' or provider == 'compatible' and model not in MODELS['openai'][2:]:
            return 'openai'
    return None


def metadata(provider, model, endpoints=()):
    known = model in MODELS.get(provider, []) or 'audio-transcription' in endpoints or '/v1/audio/transcriptions' in endpoints
    route = adapter(provider, model)
    reason = None
    if known and not route:
        reason = ('需要公网音频地址，暂未接入' if 'filetrans' in model or model in {'fun-asr', 'paraformer-v2'} else
                  '实时转写接口，暂未接入' if 'streaming' in model else
                  '字幕时间戳接口尚未适配')
    return {'asr': bool(known or (route and provider != 'compatible')), 'asr_supported': bool(route), 'asr_note': reason}
