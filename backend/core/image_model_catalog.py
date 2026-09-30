"""Verified public image model IDs. Supplements live discovery; not an account allowlist.

Checked 2026-09-29. Keep exact provider IDs: gateway aliases are not official IDs.
Sources are retained so catalog additions can be reviewed against provider docs.
"""
SOURCES = {
    'api88': 'https://88api.ai/zh/docs/api/image/openai-image/',
    'seed': 'https://docs.volcengine.com/docs/ark/model-release-announcement?lang=zh',
    'dashscope': 'https://help.aliyun.com/en/model-studio/image-model/',
    'openai': 'https://developers.openai.com/api/docs/guides/image-generation',
    'gemini': 'https://ai.google.dev/gemini-api/docs/image-generation',
    'grok': 'https://docs.x.ai/developers/model-capabilities/images/generation',
    'glm': 'https://docs.bigmodel.cn/cn/guide/models/image-generation/glm-image',
}
MODELS = {
    'api88': ['gpt-image-1', 'dall-e-3', 'dall-e-2'],
    'seed': ['doubao-seedream-5-0-flash-260915', 'doubao-seedream-5-0-pro-260628', 'doubao-seedream-4-0-20260415'],
    'openai': ['gpt-image-2.5-flare', 'gpt-image-2.5-sunburst', 'gpt-image-2', 'gpt-image-1.5', 'gpt-image-1', 'gpt-image-1-mini', 'chatgpt-image-latest'],
    'gemini': ['gemini-3.1-flash-lite-image', 'gemini-3.1-flash-image', 'gemini-3-pro-image', 'gemini-2.5-flash-image'],
    'grok': ['grok-imagine-image-2.0', 'grok-imagine-image', 'grok-imagine-image-quality'],
    'glm': ['glm-image', 'cogview-4-250304', 'cogview-4', 'cogview-3-flash'],
    'dashscope': [
        'qwen-image-3.0-pro', 'qwen-image-3.0', 'qwen-image-2.0-pro', 'qwen-image-2.0',
        'qwen-image-2.0-pro-2026-06-22', 'qwen-image-2.0-pro-2026-04-22', 'qwen-image-2.0-pro-2026-03-03', 'qwen-image-2.0-2026-03-03',
        'qwen-image-max', 'qwen-image-max-2025-12-30', 'qwen-image-plus', 'qwen-image-plus-2026-01-09', 'qwen-image',
        'wan2.7-image-pro', 'wan2.7-image', 'wan2.6-t2i', 'wan2.6-image', 'wan2.5-t2i-preview',
        'wan2.2-t2i-plus', 'wan2.2-t2i-flash', 'wan2.1-t2i-plus', 'wan2.1-t2i-turbo', 'z-image-turbo',
    ],
}
# These are edit-only in the official API, even if a gateway exposes a generation route.
EDIT_ONLY = {'dashscope': {'qwen-image-edit', 'qwen-image-edit-plus', 'qwen-image-edit-max',
    'qwen-image-edit-max-2026-01-16', 'qwen-image-edit-plus-2025-12-15', 'qwen-image-edit-plus-2025-10-30', 'wan2.5-i2i-preview', 'wanx2.1-imageedit'}}
# Research agents output diagrams through Interactions, not the model image API.
# https://ai.google.dev/gemini-api/docs/models/deep-research-preview-04-2026
UNSUPPORTED_ROUTES = {'gemini': {'deep-research-preview-04-2026', 'deep-research-max-preview-04-2026'}}
# Removed from the official service. Existing explicit configurations remain editable.
RETIRED = {
    'seed': {'doubao-seedream-4-0-250828', 'doubao-seedream-4-5-251128', 'doubao-seedream-5-0-lite-260128', 'doubao-seedream-5-0-260128'},
    'gemini': {'imagen-3.0-generate-002', 'imagen-4.0-generate-001', 'imagen-4.0-ultra-generate-001', 'imagen-4.0-fast-generate-001'},
}
