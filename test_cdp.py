#!/usr/bin/env python3
"""Standalone CDP test — run on Pi as root to diagnose WebSocket issue."""
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request

PORT = 9444

# Find chromium
chromium = shutil.which('chromium-browser') or shutil.which('chromium')
print(f'Chromium: {chromium}')
ver = subprocess.run([chromium, '--version'], capture_output=True, text=True)
print(f'Version: {ver.stdout.strip()}')

# Kill old
subprocess.run(['pkill', '-f', 'chromium.*--headless'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)

# Start Chromium
print(f'\nStarting Chromium on port {PORT}...')
proc = subprocess.Popen(
    [chromium, '--headless', '--no-sandbox', '--disable-dev-shm-usage',
     '--disable-gpu', f'--remote-debugging-port={PORT}',
     '--remote-allow-origins=*',
     '--window-size=800,480', '--hide-scrollbars', 'about:blank'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(3)

# Check process
print(f'PID: {proc.pid}, alive: {proc.poll() is None}')

# Check stderr (non-blocking)
import selectors
sel = selectors.DefaultSelector()
sel.register(proc.stderr, selectors.EVENT_READ)
stderr_lines = []
while sel.select(timeout=0.1):
    data = proc.stderr.read1(4096)
    if data:
        stderr_lines.append(data.decode(errors='replace'))
    else:
        break
sel.close()
if stderr_lines:
    print(f'Chromium stderr:\n{"".join(stderr_lines)[:500]}')

# Poll /json/list
print(f'\nPolling http://127.0.0.1:{PORT}/json/list ...')
ws_url = None
for i in range(20):
    try:
        res = urllib.request.urlopen(
            f'http://127.0.0.1:{PORT}/json/list', timeout=2)
        body = res.read()
        targets = json.loads(body)
        print(f'  Attempt {i}: {len(targets)} targets')
        if targets:
            ws_url = targets[0]['webSocketDebuggerUrl']
            print(f'  ws_url: {ws_url}')
            break
    except Exception as e:
        print(f'  Attempt {i}: {e}')
    time.sleep(0.5)

if not ws_url:
    print('FAILED: no DevTools targets')
    proc.kill()
    sys.exit(1)

# Also get /json/version
try:
    res = urllib.request.urlopen(
        f'http://127.0.0.1:{PORT}/json/version', timeout=2)
    version_info = json.loads(res.read())
    print(f'\n/json/version:')
    for k, v in version_info.items():
        print(f'  {k}: {v}')
except Exception as e:
    print(f'/json/version error: {e}')

# Parse ws_url → path
ws_path = ws_url.split(f':{PORT}', 1)[1]
print(f'\nWebSocket path: {ws_path}')

# Raw TCP + WebSocket handshake
print(f'\nConnecting TCP to 127.0.0.1:{PORT}...')
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect(('127.0.0.1', PORT))
print('TCP connected')

key = base64.b64encode(os.urandom(16)).decode()
handshake = (
    f'GET {ws_path} HTTP/1.1\r\n'
    f'Host: 127.0.0.1:{PORT}\r\n'
    f'Upgrade: websocket\r\n'
    f'Connection: Upgrade\r\n'
    f'Sec-WebSocket-Key: {key}\r\n'
    f'Sec-WebSocket-Version: 13\r\n'
    f'Origin: http://127.0.0.1\r\n'
    f'\r\n'
)
print(f'Sending handshake ({len(handshake)} bytes)...')
s.sendall(handshake.encode())

print('Waiting for response (10s timeout)...')
try:
    resp = b''
    while b'\r\n\r\n' not in resp:
        chunk = s.recv(4096)
        if not chunk:
            print(f'Connection closed. Got so far: {resp}')
            break
        resp += chunk
    print(f'Response: {resp[:500]}')
except socket.timeout:
    print('TIMEOUT waiting for WebSocket upgrade response')
    # Try a plain HTTP GET on the same connection to see if the port responds
    print('\nRetrying with plain HTTP GET...')
    s.close()
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(5)
    s2.connect(('127.0.0.1', PORT))
    s2.sendall(f'GET /json/version HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\n\r\n'.encode())
    try:
        resp2 = s2.recv(4096)
        print(f'Plain HTTP response: {resp2[:500]}')
    except socket.timeout:
        print('Plain HTTP also timed out!')
    s2.close()

s.close()
proc.terminate()
proc.wait()
print('\nDone.')
