"""Sign in with Google from the desktop app (OAuth 2.0 for installed apps, with PKCE).

The user's own browser opens Google's sign-in page; Google redirects back to a one-time
listener on 127.0.0.1, and the app exchanges the code for an ID token. The app never sees
the Google password. The Insight Hub server then verifies the ID token with Google.
Standard library only.
"""
import base64
import hashlib
import http.server
import json
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
PAGE = ('<!doctype html><meta charset="utf-8"><title>Insight Hub</title>'
        '<body style="font-family:sans-serif;margin:3em;color:#222">'
        '<h2>{heading}</h2><p>{message}</p></body>')


class GoogleSignInError(Exception):
    """Sign-in was cancelled, timed out or failed; the message is safe to show."""


def _pkce():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b'=').decode('ascii')
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return verifier, challenge


def _wait_for_code(state, open_url, timeout):
    """Run a one-request listener on 127.0.0.1 and return the authorisation code."""
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
            if 'code' not in query and 'error' not in query:
                self.send_response(404)
                self.end_headers()
                return
            result.update(query)
            ok = 'code' in query and query.get('state') == state
            body = PAGE.format(heading='Signed in' if ok else 'Sign-in was not completed',
                               message='You can close this tab and return to Insight Hub.')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body.encode('utf-8'))

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    server.timeout = 1
    redirect_uri = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        open_url(redirect_uri)
        deadline = threading.Event()
        timer = threading.Timer(timeout, deadline.set)
        timer.start()
        try:
            while not result and not deadline.is_set():
                server.handle_request()
        finally:
            timer.cancel()
    finally:
        server.server_close()
    if not result:
        raise GoogleSignInError('Google sign-in timed out. Please try again.')
    if result.get('state') != state:
        raise GoogleSignInError('Google sign-in could not be confirmed. Please try again.')
    if 'error' in result:
        raise GoogleSignInError('Google sign-in was cancelled.' if result['error'] == 'access_denied'
                                else f'Google sign-in failed ({result["error"]}).')
    return result['code'], redirect_uri


def get_id_token(client_id, client_secret, *, timeout=180, open_browser=webbrowser.open):
    """Open the browser for Google sign-in and return a Google ID token for this user."""
    if not client_id:
        raise GoogleSignInError('Google sign-in is not set up on the server yet.')
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce()

    def open_url(redirect_uri):
        params = {'client_id': client_id, 'redirect_uri': redirect_uri, 'response_type': 'code',
                  'scope': 'openid email profile', 'state': state, 'code_challenge': challenge,
                  'code_challenge_method': 'S256', 'prompt': 'select_account'}
        if not open_browser(AUTH_URL + '?' + urllib.parse.urlencode(params)):
            raise GoogleSignInError('Could not open a web browser for Google sign-in.')

    code, redirect_uri = _wait_for_code(state, open_url, timeout)
    data = urllib.parse.urlencode({'code': code, 'client_id': client_id, 'client_secret': client_secret,
                                   'redirect_uri': redirect_uri, 'grant_type': 'authorization_code',
                                   'code_verifier': verifier}).encode('ascii')
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=30) as response:
            token = json.loads(response.read().decode('utf-8')).get('id_token')
    except (urllib.error.URLError, OSError, ValueError):
        raise GoogleSignInError('Could not finish Google sign-in. Check your internet connection.') from None
    if not token:
        raise GoogleSignInError('Google did not return a sign-in token. Please try again.')
    return token
