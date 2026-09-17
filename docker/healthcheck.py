"""Health requires a live app, a VNC listener and the browser client."""
import os
import socket
import urllib.request
from pathlib import Path
os.kill(int(Path('/tmp/insight-hub.pid').read_text().strip()), 0)
with socket.create_connection(('127.0.0.1', 5900), timeout=2) as connection:
    assert connection.recv(12).startswith(b'RFB ')
with urllib.request.urlopen('http://127.0.0.1:6080/vnc.html', timeout=2) as response:
    assert response.status == 200
