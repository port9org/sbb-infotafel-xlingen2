#!/usr/bin/env python3
"""
E-paper display driver for SBB Infotafel.

Fetches sbb.png from the local capture server, converts to 1-bit,
and pushes it to the Waveshare 7.5" V2 e-paper display.
Between full refreshes, partial refresh adds keepalive dots every 10s.
Draws a diagnostic screen on connection failure.
"""

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
BACKEND_NODE = '1.1.1.1'

DOT_X       = 784   # must be multiple of 8 for e-paper partial refresh
DOT_SIZE    = 6
DOT_SPACING = 10
DOT_MAX_Y   = 60    # stay within header area


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


def main():
    print('Initializing e-paper display loop...', flush=True)

    if epd7in5_V2:
        epd = epd7in5_V2.EPD()
    else:
        epd = None

    has_partial = epd and hasattr(epd, 'display_Partial')
    print(f'Partial refresh: '
          f'{"available" if has_partial else "not available"}',
          flush=True)

    consecutive_errors = 0

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

            if epd:
                epd.init()
                epd.display(epd.getbuffer(img))
                print(f'[{time.strftime("%H:%M:%S")}] Displayed.',
                      flush=True)
            else:
                print(f'[{time.strftime("%H:%M:%S")}] Preview mode — OK.',
                      flush=True)

            if has_partial:
                try:
                    dot_count = 0
                    tick = 0
                    dot_x = DOT_X
                    t_start = time.monotonic()

                    while time.monotonic() - t_start < 50:
                        draw = ImageDraw.Draw(img)

                        # Every 5 ticks (10s), solidify the blinking dot
                        if tick > 0 and tick % 5 == 0:
                            py = 2 + dot_count * DOT_SPACING
                            draw.rectangle(
                                [dot_x, py,
                                 dot_x + DOT_SIZE, py + DOT_SIZE],
                                fill=0)
                            dot_count += 1

                        blink_y = 2 + dot_count * DOT_SPACING
                        if blink_y > DOT_MAX_Y:
                            break

                        # Toggle blink: ON on even ticks, OFF on odd
                        fill = 0 if tick % 2 == 0 else 255
                        draw.rectangle(
                            [dot_x, blink_y,
                             dot_x + DOT_SIZE, blink_y + DOT_SIZE],
                            fill=fill)

                        epd.init_part()
                        epd.display_Partial(
                            epd.getbuffer(img),
                            0, 0, epd.width, epd.height)

                        tick += 1
                        time.sleep(2)
                except Exception as e:
                    print(f'[{time.strftime("%H:%M:%S")}] '
                          f'Partial refresh failed: {e}', flush=True)

            if epd:
                epd.sleep()

            # Sync to :12 of the next minute
            curr = time.localtime().tm_sec
            delay = 12 - curr if curr <= 12 else 72 - curr
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
