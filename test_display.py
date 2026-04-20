#!/usr/bin/env python3
"""
Standalone display test — bypasses the app pipeline entirely.
Draws a simple pattern directly to the e-paper to isolate
whether the degradation is in image processing or the display driver.

Run on the Pi:
  python3 test_display.py
"""

import sys
import time
from PIL import Image, ImageDraw, ImageFont

sys.path.append('/home/ke/e-Paper/RaspberryPi_JetsonNano/python/lib')
from waveshare_epd import epd7in5_V2

W, H = 800, 480

def make_test_image():
    img = Image.new('RGB', (W, H), 255)  # white background
    draw = ImageDraw.Draw(img)

    # Solid black bar across the top
    draw.rectangle([0, 0, W, 60], fill=0)

    # Large black rectangle left side
    draw.rectangle([20, 80, 200, 400], fill=0)

    # Thick border bottom-right
    draw.rectangle([400, 200, 780, 460], outline=0, width=6)

    # Diagonal lines
    for i in range(0, W, 40):
        draw.line([(i, 80), (i + 40, 160)], fill=0, width=2)

    try:
        font = ImageFont.truetype(
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 36)
    except Exception:
        font = ImageFont.load_default()

    draw.text((240, 10), 'DISPLAY TEST', font=font, fill=255)
    draw.text((220, 200), 'BLACK OK?', font=font, fill=0)

    return img

def run_test(mode):
    """
    mode: 'RGB', 'L', or '1'
    Tests whether getbuffer behaves differently across PIL image modes.
    """
    print(f'\n--- Test: mode={mode} ---', flush=True)
    epd = epd7in5_V2.EPD()

    print('Init + clear...', flush=True)
    epd.init()
    epd.Clear()
    time.sleep(1)

    img = make_test_image()

    if mode == 'L':
        img = img.convert('L')
    elif mode == '1':
        img = img.convert('L').point(lambda x: 255 if x >= 128 else 0, '1')

    print(f'Displaying ({mode} mode)...', flush=True)
    epd.init()
    epd.display(epd.getbuffer(img))

    print('Waiting 3s before sleep to let pixels settle...', flush=True)
    time.sleep(3)

    epd.sleep()
    print(f'Done. Observe display — is black sharp or washed out?', flush=True)
    input('Press Enter to continue to next test...\n')


if __name__ == '__main__':
    print('E-paper isolation test', flush=True)
    print('Tests RGB, L, and 1-bit modes to find which getbuffer handles correctly.')
    print('Watch the display after each refresh settles.\n')

    try:
        run_test('RGB')
        run_test('L')
        run_test('1')
        print('All tests done.')
    except KeyboardInterrupt:
        print('\nAborted.')
        epd7in5_V2.epdconfig.module_exit(cleanup=True)
