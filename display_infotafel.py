#!/usr/bin/env python3
"""
E-paper display driver for SBB Infotafel.

Fetches sbb.png from the local capture server, converts to 1-bit,
and pushes it to the Waveshare 7.5" V2 e-paper display.
Between full refreshes, partial refresh adds keepalive dots every 10s.
Draws a diagnostic screen on connection failure.
"""

import os
import subprocess
import sys
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

sys.path.append('/home/ke/e-Paper/RaspberryPi_JetsonNano/python/lib')
try:
    from waveshare_epd import epd7in5_V2
except ImportError:
    print('Warning: waveshare_epd not found — running in preview mode',
          flush=True)
    epd7in5_V2 = None

IMAGE_URL    = 'http://localhost:8080/sbb.png'
LOCAL_IMAGE  = '/tmp/sbb_display.png'
HEARTBEAT    = '/tmp/display_heartbeat'
INVERT_FLAG  = '/tmp/display_invert'   # touch to enable white-on-black; rm to revert
BACKEND_NODE = '1.1.1.1'


DEEP_CLEAN_INTERVAL = 5   # full black→white wipe every N updates


def sys_cmd(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return 'Unknown'


def ping_ok():
    try:
        return subprocess.call(
            'ping -c 1 -W 2 ' + BACKEND_NODE,
            shell=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0
    except Exception:
        return False


def draw_error_screen(epd, error_msg):
    try:
        img  = Image.new('1', (epd.width, epd.height), 255)
        draw = ImageDraw.Draw(img)
        try:
            f_title = ImageFont.truetype(
                '/usr/share/fonts/truetype/liberation/'
                'LiberationSans-Regular.ttf', 36)
            f_text = ImageFont.truetype(
                '/usr/share/fonts/truetype/liberation/'
                'LiberationSans-Regular.ttf', 20)
            f_mono = ImageFont.truetype(
                '/usr/share/fonts/truetype/liberation/'
                'LiberationMono-Regular.ttf', 14)
        except Exception:
            f_title = f_text = f_mono = ImageFont.load_default()

        now = time.strftime('%Y-%m-%d %H:%M:%S')
        ip  = sys_cmd("hostname -I | awk '{print $1}'")
        ssid = sys_cmd('iwgetid -r')
        inet = 'ONLINE' if ping_ok() else 'OFFLINE'
        ts   = sys_cmd('tailscale status')

        draw.text((20, 20), 'CONNECTION ERROR', font=f_title, fill=0)
        draw.line((20, 65, epd.width - 20, 65), fill=0, width=3)

        y = 80
        for line in [
            f'Timestamp:     {now}',
            f'RPi IP:        {ip}',
            f'WLAN SSID:     {ssid}',
            f'Internet:      {inet}',
            f'Error:         {error_msg}',
        ]:
            draw.text((20, y), line, font=f_text, fill=0)
            y += 30

        y += 10
        draw.text((20, y), 'Tailscale:', font=f_text, fill=0)
        y += 25
        for ts_line in ts.split('\n'):
            if not ts_line.strip():
                continue
            draw.text((20, y), ts_line[:120], font=f_mono, fill=0)
            y += 18
            if y > epd.height - 20:
                break

        epd.init()
        epd.display(epd.getbuffer(img))
        epd.sleep()
    except Exception as e:
        print(f'Failed to draw error screen: {e}', flush=True)


def deep_clean(epd):
    """Cycle pixels through full black→white to prevent charge buildup."""
    print('Deep clean: black frame...', flush=True)
    epd.init()
    epd.display(epd.getbuffer(Image.new('1', (epd.width, epd.height), 0)))
    print('Deep clean: white clear...', flush=True)
    epd.init()
    epd.Clear()


def main():
    print('Initializing e-paper display loop...', flush=True)

    if epd7in5_V2:
        epd = epd7in5_V2.EPD()
    else:
        epd = None

    if epd:
        deep_clean(epd)
        epd.sleep()

    consecutive_errors = 0
    cycle_count = 0

    while True:
        try:
            print(f'[{time.strftime("%H:%M:%S")}] Fetching {IMAGE_URL}...',
                  flush=True)
            urllib.request.urlretrieve(IMAGE_URL, LOCAL_IMAGE)
            consecutive_errors = 0

            img = Image.open(LOCAL_IMAGE)
            if epd and img.size != (epd.width, epd.height):
                img = img.resize(
                    (epd.width, epd.height), Image.Resampling.LANCZOS)
            # Flatten RGBA → RGB before converting to avoid alpha compositing artifacts.
            # Then threshold at 200 and convert directly to '1' to bypass getbuffer's
            # internal dithering (convert('1') on a pre-'1' image is a no-op).
            inverted = os.path.exists(INVERT_FLAG)
            lut = (lambda x: 0 if x >= 200 else 255) if inverted else (lambda x: 255 if x >= 200 else 0)
            img = img.convert('RGB').convert('L').point(lut, '1')
            if inverted:
                print(f'[{time.strftime("%H:%M:%S")}] Invert mode ON', flush=True)

            if epd:
                cycle_count += 1
                if cycle_count % DEEP_CLEAN_INTERVAL == 0:
                    print(f'Periodic deep clean at cycle {cycle_count}...',
                          flush=True)
                    deep_clean(epd)

                epd.init()
                epd.display(epd.getbuffer(img))
                print(f'[{time.strftime("%H:%M:%S")}] Displayed.',
                      flush=True)
            else:
                print(f'[{time.strftime("%H:%M:%S")}] Preview mode — OK.',
                      flush=True)
            open(HEARTBEAT, 'w').close()

            if epd:
                epd.sleep()

            # Sync to :32 of the next minute
            curr = time.localtime().tm_sec
            delay = 32 - curr if curr <= 32 else 92 - curr
            time.sleep(max(1, delay))

        except KeyboardInterrupt:
            print('Exiting...', flush=True)
            if epd7in5_V2 and epd:
                epd7in5_V2.epdconfig.module_exit(cleanup=True)
            break
        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] Error: {e}', flush=True)
            consecutive_errors += 1
            if consecutive_errors == 1 and epd:
                draw_error_screen(epd, str(e))
            time.sleep(10)


if __name__ == '__main__':
    main()
