#!/usr/bin/env python3
"""
Capture loop for SBB Infotafel.

1. Fetch all API data in Python → write data.json atomically.
2. Launch Chromium headless, screenshot via Chrome DevTools Protocol (CDP).
   Uses a raw-socket WebSocket client to avoid websocket-client library bugs.
3. Sync to :55 of each minute so the screenshot lands after the minute
   boundary and the displayed clock is always accurate.
"""

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SERVE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_FILE     = os.path.join(SERVE_DIR, 'data.json')
SCREENSHOT    = os.path.join(SERVE_DIR, 'sbb.png')
PAGE_URL      = 'http://127.0.0.1:8080/'
TRAIN_STATION = '8506131'
BUS_STATION   = '8581697'
WIDTH, HEIGHT = 800, 480


def find_chromium():
    if sys.platform == 'darwin':
        path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        if os.path.exists(path):
            return path
        raise RuntimeError('Google Chrome not found on macOS')
    for candidate in ('chromium-browser', 'chromium'):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError('Chromium not found — install: sudo apt install chromium-browser')


def now_dt():
    return time.strftime('%Y-%m-%d %H:%M')


def api_get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'sbb-infotafel/2.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))


def fetch_all():
    dt = urllib.parse.quote(now_dt())
    board_base = 'https://transport.opendata.ch/v1/stationboard'
    trains = api_get(board_base + '?station=' + TRAIN_STATION + '&limit=40&passlist=1&datetime=' + dt)
    buses  = api_get(board_base + '?station=' + BUS_STATION   + '&limit=8&passlist=1&datetime='  + dt)
    weather = api_get(
        'https://api.open-meteo.com/v1/forecast'
        '?latitude=47.6465&longitude=9.1764'
        '&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m'
        '&daily=weather_code,temperature_2m_max,temperature_2m_min,'
        'precipitation_sum,precipitation_probability_max'
        '&timezone=Europe%2FBerlin'
    )
    zurich_rain = api_get(
        'https://api.open-meteo.com/v1/forecast'
        '?latitude=47.3769&longitude=8.5417'
        '&hourly=precipitation_probability,precipitation'
        '&timezone=Europe%2FBerlin'
    )
    pollen = api_get(
        'https://air-quality-api.open-meteo.com/v1/air-quality'
        '?latitude=47.64&longitude=9.17'
        '&current=alder_pollen,birch_pollen,grass_pollen,'
        'mugwort_pollen,olive_pollen,ragweed_pollen'
    )
    return {'trains': trains, 'buses': buses, 'weather': weather,
            'zurich_rain': zurich_rain, 'pollen': pollen}


def write_data(data):
    tmp = DATA_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    shutil.move(tmp, DATA_FILE)



def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Minimal raw-socket WebSocket client (no third-party library)
# ---------------------------------------------------------------------------

def _ws_connect(host, port, path):
    """Open a WebSocket connection, return the raw socket."""
    key = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f'GET {path} HTTP/1.1\r\n'
        f'Host: {host}:{port}\r\n'
        f'Upgrade: websocket\r\n'
        f'Connection: Upgrade\r\n'
        f'Sec-WebSocket-Key: {key}\r\n'
        f'Sec-WebSocket-Version: 13\r\n'
        f'Origin: http://{host}\r\n'
        f'\r\n'
    )
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((host, port))
    s.sendall(handshake.encode())
    resp = b''
    while b'\r\n\r\n' not in resp:
        resp += s.recv(4096)
    if b'101' not in resp:
        raise RuntimeError(f'WebSocket upgrade failed: {resp[:200]}')
    return s


def _ws_send(s, data):
    """Send a masked text frame."""
    payload = data.encode() if isinstance(data, str) else data
    length = len(payload)
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    if length < 126:
        header = bytes([0x81, 0x80 | length]) + mask
    elif length < 65536:
        header = bytes([0x81, 0xFE]) + struct.pack('>H', length) + mask
    else:
        header = bytes([0x81, 0xFF]) + struct.pack('>Q', length) + mask
    s.sendall(header + masked)


def _ws_recv(s):
    """Receive one text frame (blocks until complete)."""
    def recv_exact(n):
        buf = b''
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise RuntimeError('WebSocket connection closed')
            buf += chunk
        return buf

    header = recv_exact(2)
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack('>H', recv_exact(2))[0]
    elif length == 127:
        length = struct.unpack('>Q', recv_exact(8))[0]
    return recv_exact(length).decode('utf-8')


def _cdp(s, method, params=None, msg_id=1):
    _ws_send(s, json.dumps({'id': msg_id, 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(_ws_recv(s))
        if msg.get('id') == msg_id:
            if 'error' in msg:
                raise RuntimeError(f'CDP {method}: {msg["error"]}')
            return msg.get('result', {})


def capture(chromium):
    subprocess.run(['pkill', '-f', 'chromium.*--headless'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)

    debug_port = _free_port()
    proc = subprocess.Popen(
        [chromium, '--headless', '--no-sandbox', '--disable-dev-shm-usage',
         '--disable-gpu', f'--remote-debugging-port={debug_port}',
         '--remote-allow-origins=*',
         f'--window-size={WIDTH},{HEIGHT}', '--hide-scrollbars', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # Wait for DevTools HTTP endpoint (up to 20s)
        ws_path = None
        for _ in range(40):
            try:
                res = urllib.request.urlopen(
                    f'http://127.0.0.1:{debug_port}/json/list', timeout=1)
                targets = json.loads(res.read())
                if targets:
                    url = targets[0]['webSocketDebuggerUrl']
                    ws_path = url.split(f':{debug_port}', 1)[1]
                    break
            except Exception:
                pass
            time.sleep(0.5)

        if not ws_path:
            raise RuntimeError('Chrome DevTools did not start')

        ws = _ws_connect('127.0.0.1', debug_port, ws_path)
        ws.settimeout(30)
        try:
            _cdp(ws, 'Emulation.setDeviceMetricsOverride', {
                'width': WIDTH, 'height': HEIGHT,
                'deviceScaleFactor': 1, 'mobile': False,
            }, msg_id=1)
            _cdp(ws, 'Page.navigate', {'url': PAGE_URL}, msg_id=2)
            time.sleep(5)
            result = _cdp(ws, 'Page.captureScreenshot', {
                'format': 'png',
                'clip': {'x': 0, 'y': 0, 'width': WIDTH, 'height': HEIGHT, 'scale': 1},
            }, msg_id=3)
        finally:
            ws.close()

        tmp = SCREENSHOT + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(base64.b64decode(result['data']))
        shutil.move(tmp, SCREENSHOT)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main():
    chromium = find_chromium()
    print(f'Chromium: {chromium}', flush=True)
    print(f'Screenshot: {SCREENSHOT}', flush=True)

    while True:
        t0 = time.monotonic()
        try:
            print(f'[{time.strftime("%H:%M:%S")}] Fetching data...', flush=True)
            data = fetch_all()
            write_data(data)

            print(f'[{time.strftime("%H:%M:%S")}] Capturing screenshot...', flush=True)
            capture(chromium)

            elapsed = time.monotonic() - t0
            print(f'[{time.strftime("%H:%M:%S")}] Done ({elapsed:.1f}s)', flush=True)

        except urllib.error.URLError as e:
            print(f'[{time.strftime("%H:%M:%S")}] Network error: {e}', flush=True)
        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] Error: {e}', flush=True)

        # Sync to :55 of the current minute so the screenshot lands after
        # the next minute boundary, keeping the displayed clock accurate.
        secs = time.time() % 60
        sleep_s = (55 - secs) if secs <= 55 else (115 - secs)
        time.sleep(sleep_s)


if __name__ == '__main__':
    main()
