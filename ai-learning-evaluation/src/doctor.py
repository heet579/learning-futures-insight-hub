"""Check this computer's Insight Hub setup and say exactly what is wrong.

    python -m src.doctor

Reads .env, tests the Gemini key with a tiny request, connects to the database, and checks
the shared server and Google sign-in. Secrets are never printed.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ENV = APP / '.env'
OK, BAD, WARN = '  OK  ', ' FAIL ', ' WARN '
problems = []


def say(mark, text, fix=''):
    print(f'[{mark}] {text}')
    if fix:
        print(f'         -> {fix}')
    if mark != OK:
        problems.append(text)


def check_env_file():
    print('\n.env file')
    if not ENV.exists():
        say(BAD, f'No .env file in {APP}', 'Copy .env.example to .env and fill in the values.')
        return {}
    raw = ENV.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        say(WARN, '.env starts with an invisible BOM character (saved as "UTF-8 with BOM")',
            'It still works, but resave it as plain UTF-8 to be safe.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        say(BAD, '.env is not plain text (UTF-8)', 'Open it in Notepad and Save As with Encoding: UTF-8.')
        return {}
    values = {}
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if '=' not in stripped:
            say(BAD, f'Line {number} is not KEY=value: "{stripped[:30]}"', 'Fix or delete that line.')
            continue
        key, value = stripped.split('=', 1)
        if key != key.strip() or ' ' in key.strip():
            say(WARN, f'Line {number}: spaces around the name "{key.strip()}"', 'Write it as NAME=value with no spaces.')
        value = value.strip()
        if value[:1] in '"\'' and value[-1:] == value[:1]:
            value = value[1:-1]
        elif value[:1] in '"\'':
            say(BAD, f'{key.strip()}: opening quote without a closing quote', 'Remove the quote marks.')
        if ' ' in value and key.strip().endswith(('KEY', 'URL', 'SECRET', 'ID')):
            say(BAD, f'{key.strip()} contains a space', 'Copy the value again without spaces.')
        values[key.strip()] = value
    for name in ('GEMINI_API_KEY', 'GEMINI_MODEL', 'SERVER_URL'):
        say(OK if values.get(name) else WARN, f'{name} is {"set" if values.get(name) else "empty"}')
    return values


def request(url, data=None, headers=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method='POST' if data else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(getattr(exc, 'reason', exc))


def google_message(body):
    try:
        error = json.loads(body).get('error', {})
        return f"{error.get('status', '')} {error.get('message', '')}".strip()[:300]
    except ValueError:
        return body[:200]


def gemini_call(key, model):
    body = json.dumps({'contents': [{'parts': [{'text': 'Reply with the single word OK.'}]}],
                       'generationConfig': {'maxOutputTokens': 2048}}).encode('utf-8')
    return request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', body,
                   {'Content-Type': 'application/json', 'x-goog-api-key': key})


def check_gemini(values):
    print('\nGemini')
    key, model = values.get('GEMINI_API_KEY', ''), values.get('GEMINI_MODEL', '') or 'gemini-2.5-flash-lite'
    if not key:
        say(WARN, 'No GEMINI_API_KEY: drafts use fixed local wording', 'Create a key at https://aistudio.google.com/apikey')
        return
    kind = 'standard (AIza...)' if key.startswith('AIza') else 'new authentication key (AQ....)' if key.startswith('AQ.') else 'unrecognised format'
    print(f'         key: {len(key)} characters, {kind}; model: {model}')
    status, body = gemini_call(key, model)
    if status == 200:
        say(OK, f'Gemini answered using {model}')
        return
    if status == 0:
        say(BAD, f'Could not reach Google ({body})', 'Check the internet connection, VPN or firewall.')
        return
    message = google_message(body)
    say(BAD, f'Gemini refused the request: HTTP {status} {message}')
    if status == 404 or 'not found' in message.lower():
        print('         -> The model name may be wrong. Trying gemini-2.5-flash-lite with the same key...')
        status2, body2 = gemini_call(key, 'gemini-2.5-flash-lite')
        if status2 == 200:
            say(WARN, 'The key works with gemini-2.5-flash-lite', 'Set GEMINI_MODEL=gemini-2.5-flash-lite in .env.')
        else:
            print(f'         -> That failed too: HTTP {status2} {google_message(body2)}')
    elif status in (400, 401, 403):
        fix = ('Create a new key in Google AI Studio (https://aistudio.google.com/apikey) for a project with the '
               'Gemini API enabled, paste it into .env with no quotes or spaces, then restart the app.')
        if key.startswith('AQ.'):
            fix += (' AI Studio now issues "AQ." keys; if a fresh one is still refused, create the key in Google '
                    'Cloud Console (APIs & Services > Credentials > Create API key) restricted to the '
                    '"Generative Language API" — those keys start with AIza.')
        say(BAD, 'The key was rejected', fix)
    elif status == 429:
        say(WARN, 'Quota reached for this key', 'Wait a minute and run the check again.')


def check_database(values):
    print('\nDatabase (administrators only)')
    url = values.get('DATABASE_URL') or os.getenv('DATABASE_URL', '')
    if not url:
        print('         not set on this computer (fine for team members)')
        return
    try:
        import psycopg
        with psycopg.connect(url if '://' in url else url, connect_timeout=15, prepare_threshold=None) as db:
            users = db.execute('SELECT count(*) FROM users').fetchone()[0]
        say(OK, f'Connected to Neon; {users} accounts')
    except ImportError:
        say(WARN, 'psycopg is not installed', 'pip install -r server/requirements.txt')
    except Exception as exc:
        say(BAD, f'Database connection failed: {str(exc).splitlines()[0][:200]}',
            'Check DATABASE_URL in .env (copy it again from Neon > Connect) and your internet connection.')


def check_server(values):
    print('\nShared server')
    base = (values.get('SERVER_URL') or '').rstrip('/')
    if not base:
        print('         SERVER_URL is empty: the desktop app works on this computer only')
        return
    print(f'         {base}  (the first request can take up to a minute if it was asleep)')
    status, body = request(base + '/health', timeout=90)
    if status != 200:
        say(BAD, f'Server not reachable: {status or body}', 'Open Render and check the service is Live and the URL is right.')
        return
    say(OK, f'Server is up: {body.strip()}')
    status, body = request(base + '/auth/google/config')
    if status == 404:
        say(BAD, 'The server is running old code without Google sign-in',
            'In Render, check the service deploys the main branch and redeploy the latest commit.')
    elif status == 200:
        config = json.loads(body)
        if config.get('enabled'):
            say(OK, 'Google sign-in for the desktop app is set up on the server')
        else:
            say(BAD, 'Google sign-in is not set up on the server',
                'In Render > Environment add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (Desktop app client), then save.')
    status, body = request(base + '/api/config')
    if status == 404:
        say(WARN, 'The browser app is not deployed on the server yet', 'Redeploy the latest main branch on Render.')
    elif status == 200:
        config = json.loads(body)
        if config.get('google_web_client_id'):
            say(OK, 'Google sign-in for the browser app is set up')
        else:
            say(WARN, 'Google sign-in for the browser app is not set up',
                'Create a "Web application" OAuth client and add GOOGLE_WEB_CLIENT_ID in Render (see docs/browser-app.md).')


def main():
    print('Insight Hub setup check')
    values = check_env_file()
    check_gemini(values)
    check_database(values)
    check_server(values)
    print('\n' + ('Everything checked out.' if not problems else f'{len(problems)} thing(s) need attention (see above).'))


if __name__ == '__main__':
    main()
