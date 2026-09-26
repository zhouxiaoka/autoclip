"""Authentication before routing, with explicit browser origins and admission."""
import base64
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import urlsplit, parse_qsl, urlencode, quote, unquote

from starlette.requests import Request
from starlette.responses import JSONResponse
from backend.core.usage_guard import UsageDenied, admit_http, limit


def media_target(target):
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError("Relative media path required")
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != '_media'])
    return quote(unquote(parsed.path), safe='/') + ('?' + query if query else '')


def media_path(target):
    path = urlsplit(target).path
    return bool(re.fullmatch(r'/api/v1/(?:projects/[^/]+/(?:clips/[^/]+|collections/[^/]+/thumbnail|video|download|exports/[^/]+/download|files/[^/]+\.(?:mp4|mov|mkv|webm))|files/projects/[^/]+/collections/[^/]+)', path))


class APISecurity:
    def __init__(self, app, mode='web'):
        self.app = app
        self.secret = os.getenv('AUTOCLIP_AUTH_TOKEN', '')
        self.mode = mode
        self.hosts = set(os.getenv('AUTOCLIP_ALLOWED_HOSTS', 'localhost,127.0.0.1,::1').split(','))
        self.origins = set(filter(None, os.getenv('AUTOCLIP_ALLOWED_ORIGINS', '').split(',')))
        if mode == 'desktop':
            self.origins.update(('tauri://localhost', 'http://tauri.localhost', 'https://tauri.localhost'))

    def sign(self, kind, value='', seconds=28800):
        body = base64.urlsafe_b64encode(json.dumps([kind, value, int(time.time()) + seconds], separators=(',', ':')).encode()).decode()
        signature = hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        return body + '.' + signature

    def valid(self, token, kind, value=''):
        try:
            body, signature = token.rsplit('.', 1)
            expected = hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return False
            actual_kind, actual_value, expiry = json.loads(base64.urlsafe_b64decode(body))
            return actual_kind == kind and actual_value == value and int(time.time()) < expiry
        except (ValueError, TypeError, UnicodeError):
            return False

    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http', 'websocket'):
            return await self.app(scope, receive, send)
        if scope['type'] == 'websocket':
            return await send({'type': 'websocket.close', 'code': 1008})
        original_send = send
        origin = None
        approved = False
        async def secured_send(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers += [(b'cache-control', b'no-store'), (b'referrer-policy', b'no-referrer')]
                if approved:
                    headers += [(b'access-control-allow-origin', origin.encode()), (b'access-control-allow-credentials', b'true'), (b'vary', b'Origin')]
                message = {**message, 'headers': headers}
            await original_send(message)
        send = secured_send
        request = Request(scope, receive)
        path = scope['path']
        async def respond(status, message):
            await JSONResponse({'detail': message}, status_code=status, headers={'Cache-Control': 'no-store'})(scope, receive, send)
        if path == '/health' and request.method in ('GET', 'HEAD'):
            return await JSONResponse({'status': 'ok'})(scope, receive, send)
        host = request.headers.get('host', '')
        try:
            hostname = urlsplit('http://' + host).hostname
        except ValueError:
            hostname = None
        if not hostname or hostname not in self.hosts:
            return await respond(400, 'Unapproved host')
        if len(self.secret) < 32:
            return await respond(503, 'Operator must configure AUTOCLIP_AUTH_TOKEN (at least 32 characters)')
        origin = request.headers.get('origin')
        same_origin = f"{scope.get('scheme', 'http')}://{host}"
        approved = origin is not None and origin != 'null' and (origin == same_origin or origin in self.origins)
        if origin is not None and not approved:
            return await respond(403, 'Unapproved origin')
        if request.method == 'OPTIONS':
            if not approved:
                return await respond(403, 'Origin required')
            response = JSONResponse({})
            response.headers.update({'Access-Control-Allow-Methods': 'GET,HEAD,POST,PUT,PATCH,DELETE,OPTIONS', 'Access-Control-Allow-Headers': 'Authorization,Content-Type,Range'})
            return await response(scope, receive, send)
        bearer = request.headers.get('authorization', '')
        authenticated = bearer.startswith('Bearer ') and hmac.compare_digest(bearer[7:], self.secret)
        cookie_auth = self.valid(request.cookies.get('autoclip_session', ''), 'session')
        if cookie_auth and (request.method not in ('GET', 'HEAD') and not approved):
            return await respond(403, 'Browser origin required')
        authenticated = authenticated or cookie_auth
        ticket = request.query_params.get('_media', '')
        media_auth = request.method in ('GET', 'HEAD') and media_path(path) and self.valid(ticket, 'media', media_target(path + ('?' + scope['query_string'].decode() if scope.get('query_string') else '')))
        try:
            if path == '/api/auth/login' and request.method == 'POST':
                admit_http('login', True)
                if not approved:
                    return await respond(403, 'Browser origin required')
                body = await self.read_small(request, 4096)
                supplied = json.loads(body).get('token', '')
                if not isinstance(supplied, str) or not hmac.compare_digest(supplied, self.secret):
                    return await respond(401, 'Invalid access token')
                response = JSONResponse({'authenticated': True})
                response.set_cookie('autoclip_session', self.sign('session'), httponly=True, secure=scope.get('scheme') == 'https', samesite='strict', max_age=28800, path='/')
                response.headers['Cache-Control'] = 'no-store'
                return await response(scope, receive, send)
            if not authenticated and not media_auth:
                return await respond(401, 'Authentication required')
            # Single operator principal; neither spoofed IPs nor changing provider keys reset it.
            admit_http('operator', request.method not in ('GET', 'HEAD') and path != '/api/auth/media')
            if path == '/api/auth/session' and request.method == 'GET':
                return await JSONResponse({'authenticated': True}, headers={'Cache-Control': 'no-store'})(scope, receive, send)
            if path == '/api/auth/media' and request.method == 'POST':
                body = json.loads(await self.read_small(request, 4096))
                target = media_target(body.get('path', ''))
                if not isinstance(target, str) or not media_path(target):
                    return await respond(400, 'Unsupported media path')
                return await JSONResponse({'token': self.sign('media', target, 60), 'expires_in': 60}, headers={'Cache-Control': 'no-store'})(scope, receive, send)
            if path == '/api/auth/logout' and request.method == 'POST':
                response = JSONResponse({'authenticated': False})
                response.delete_cookie('autoclip_session')
                return await response(scope, receive, send)
            maximum = limit('REQUEST_BYTES', 536870912) if 'multipart/form-data' in request.headers.get('content-type', '') else limit('JSON_REQUEST_BYTES', 1048576)
            if int(request.headers.get('content-length', '0')) > maximum:
                return await respond(413, 'Request body too large')
            seen = 0
            async def bounded_receive():
                nonlocal seen
                message = await receive()
                seen += len(message.get('body', b''))
                if seen > maximum:
                    raise UsageDenied('Request body too large')
                return message
            await self.app(scope, bounded_receive, send)
        except UsageDenied as exc:
            await respond(429, str(exc))
        except (ValueError, TypeError, json.JSONDecodeError):
            await respond(400, 'Invalid request')

    @staticmethod
    async def read_small(request, maximum):
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > maximum:
                raise UsageDenied('Request body too large')
        return bytes(chunks)
