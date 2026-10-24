"""Run Insight Hub in your browser on this computer.

    python web.py              # opens http://127.0.0.1:8000
    python web.py --port 9000

Uses the settings in .env: DATABASE_URL (the shared Neon database, so you see the same
accounts and reports as everyone else) and GEMINI_API_KEY. Without DATABASE_URL it uses a
local test database in reports/server_dev.sqlite3.
"""
import argparse
import threading
import webbrowser
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Run the Insight Hub browser app locally.')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true', help='Do not open a browser window')
    args = parser.parse_args()
    try:
        import uvicorn
        import fastapi  # noqa: F401
        import multipart  # noqa: F401
    except ImportError:
        raise SystemExit('Install the server packages first:  pip install -r server/requirements.txt')
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / '.env', override=False)
    url = f'http://127.0.0.1:{args.port}'
    print('Starting Insight Hub… (the first start can take up to a minute)')

    def open_when_ready():
        # Open the browser only once the server answers, so it never shows "refused to connect".
        import time
        import urllib.request
        for _ in range(240):
            try:
                urllib.request.urlopen(url + '/health', timeout=2)
                break
            except OSError:
                time.sleep(0.5)
        else:
            print('The server did not start. Check the messages above.')
            return
        print(f'Insight Hub is running at {url}  (keep this window open; press Ctrl+C to stop)')
        if not args.no_browser:
            webbrowser.open(url)

    threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run('server.app:app', host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
