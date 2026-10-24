"""Signed session tokens. The signed-in account always comes from the token, never the request body."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

TOKEN_HOURS = 12
_fallback_secret = secrets.token_hex(32)


def secret_key():
    key = os.getenv('SECRET_KEY', '').strip()
    # Without SECRET_KEY, tokens stop working when the server restarts (fine for local tests only).
    return (key or _fallback_secret).encode('utf-8')


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _unb64(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def issue_token(username, role, hours=TOKEN_HOURS):
    body = _b64(json.dumps({'u': username, 'r': role, 'exp': int(time.time() + hours * 3600)},
                           separators=(',', ':')).encode('utf-8'))
    signature = _b64(hmac.new(secret_key(), body.encode('ascii'), hashlib.sha256).digest())
    return f'{body}.{signature}'


def read_token(token):
    """Return {'u', 'r', 'exp'} for a valid unexpired token, else None."""
    try:
        body, signature = token.split('.')
        expected = _b64(hmac.new(secret_key(), body.encode('ascii'), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_unb64(body))
        return claims if claims.get('exp', 0) > time.time() and claims.get('u') else None
    except (ValueError, AttributeError, TypeError):
        return None
