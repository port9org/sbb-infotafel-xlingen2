#!/usr/bin/env python3
"""
Capture loop for SBB Infotafel.

1. Fetch all API data in Python → write data.json atomically.
2. Screenshot via Selenium + chromedriver (handles CDP internally).
3. Sync to :55 of each minute so the screenshot lands after the minute
   boundary and the displayed clock is always accurate.
"""

import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

SERVE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_FILE     = os.path.join(SERVE_DIR, 'data.json')
SCREENSHOT    = os.path.join(SERVE_DIR, 'sbb.png')
PAGE_URL      = 'http://127.0.0.1:8080/'
TRAIN_STATION = '8506131'
BUS_STATION   = '8581697'
WIDTH, HEIGHT = 800, 480


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


def capture():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument(f'--window-size={WIDTH},{HEIGHT}')
    options.add_argument('--hide-scrollbars')

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(PAGE_URL)
        time.sleep(5)
        tmp = SCREENSHOT + '.tmp'
        driver.save_screenshot(tmp)
        shutil.move(tmp, SCREENSHOT)
    finally:
        driver.quit()


def main():
    print(f'Screenshot: {SCREENSHOT}', flush=True)

    while True:
        t0 = time.monotonic()
        try:
            print(f'[{time.strftime("%H:%M:%S")}] Fetching data...', flush=True)
            data = fetch_all()
            write_data(data)

            print(f'[{time.strftime("%H:%M:%S")}] Capturing screenshot...', flush=True)
            capture()

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
