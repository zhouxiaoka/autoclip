"""Native Gemini request and completion envelopes shared by text and vision callers."""
from __future__ import annotations

import base64
import binascii
from urllib.parse import quote, urlsplit, urlunsplit


def is_official_gemini(provider: str, base_url: str) -> bool:
    return provider == 'gemini' and urlsplit(base_url).hostname == 'generativelanguage.googleapis.com'


def native_root(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.username or parsed.password:
        raise ValueError('Gemini endpoint must not contain credentials')
    path = parsed.path.rstrip('/').removesuffix('/openai')
    return urlunsplit((parsed.scheme, parsed.netloc, path, '', ''))


def native_headers(api_key: str) -> dict:
    return {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}


def native_auth(prepared_request):
    """Prevent requests sessions or netrc from adding a second credential."""
    prepared_request.headers.pop('Authorization', None)
    return prepared_request


def _parts(content) -> list[dict]:
    if isinstance(content, str):
        return [{'text': content}] if content else []
    if not isinstance(content, list):
        raise ValueError('Unsupported Gemini message content')
    parts = []
    for part in content:
        if part.get('type') == 'text':
            parts.append({'text': part['text']})
        elif part.get('type') == 'image_url':
            url = part['image_url']['url']
            header, separator, data = url.partition(',')
            if not separator or not data or not header.startswith('data:image/') or not header.endswith(';base64'):
                raise ValueError('Gemini images must be base64 image data URLs; remote URLs are not fetched')
            try:
                base64.b64decode(data, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError('Invalid Gemini image data') from None
            parts.append({'inlineData': {'mimeType': header[5:-7], 'data': data}})
        else:
            raise ValueError('Unsupported Gemini message part')
    return parts


def request(base_url: str, api_key: str, payload: dict) -> tuple[str, dict, dict]:
    contents, system = [], []
    for message in payload['messages']:
        parts = _parts(message.get('content', ''))
        role = message['role']
        if role == 'system':
            system.extend(parts)
        elif role in ('user', 'assistant'):
            if parts:
                contents.append({'role': 'model' if role == 'assistant' else 'user', 'parts': parts})
        else:
            raise ValueError('Unsupported Gemini message role')
    if not contents:
        raise ValueError('Gemini requires nonempty message content')
    body = {'contents': contents}
    if system:
        body['systemInstruction'] = {'parts': system}
    config = {}
    for source, target in [('temperature', 'temperature'), ('top_p', 'topP'),
                           ('max_tokens', 'maxOutputTokens'), ('max_completion_tokens', 'maxOutputTokens')]:
        if payload.get(source) is not None:
            config[target] = payload[source]
    if (payload.get('response_format') or {}).get('type') in ('json_object', 'json_schema'):
        config['responseMimeType'] = 'application/json'
    if config:
        body['generationConfig'] = config
    model = quote(payload['model'].removeprefix('models/'), safe='')
    return f'{native_root(base_url)}/models/{model}:generateContent', native_headers(api_key), body


def completion(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError('Gemini returned an invalid response')
    feedback = data.get('promptFeedback') or {}
    if feedback.get('blockReason'):
        raise ValueError('Gemini blocked the prompt (promptFeedback.blockReason)')
    candidates = data.get('candidates') or []
    if not candidates:
        raise ValueError('Gemini returned no candidates')
    candidate = candidates[0]
    reason = candidate.get('finishReason')
    text = ''.join(part.get('text', '') for part in (candidate.get('content') or {}).get('parts', [])
                   if not part.get('thought'))
    if reason not in (None, 'STOP', 'MAX_TOKENS'):
        raise ValueError(f'Gemini did not complete the response ({reason})')
    if not text and reason != 'MAX_TOKENS':
        raise ValueError('Gemini returned empty text')
    usage = data.get('usageMetadata') or {}
    return {'choices': [{'message': {'content': text},
                         'finish_reason': 'length' if reason == 'MAX_TOKENS' else 'stop'}],
            'usage': {'prompt_tokens': usage.get('promptTokenCount', 0),
                      'completion_tokens': usage.get('candidatesTokenCount', 0),
                      'total_tokens': usage.get('totalTokenCount', 0)}}
