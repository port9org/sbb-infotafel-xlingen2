#!/usr/bin/env python3
import sys
import time
import urllib.request
from PIL import Image

sys.path.append('/home/ke/e-Paper/RaspberryPi_JetsonNano/python/lib')
try:
    from waveshare_epd import epd7in5_V2
except ImportError:
    epd7in5_V2 = None

IMAGE_URL   = 'http://localhost:8080/sbb.png'
LOCAL_IMAGE = '/tmp/sbb_display.png'

def main():
    epd = epd7in5_V2.EPD() if epd7in5_V2 else None

    if epd:
        epd.init()
        # Waveshare's own "if screen appears gray" fix — override VCOM interval setting
        epd.send_command(0x50)
        epd.send_data(0x10)
        epd.send_data(0x17)
        epd.send_command(0x52)
        epd.send_data(0x03)
        epd.Clear()

    while True:
        try:
            urllib.request.urlretrieve(IMAGE_URL, LOCAL_IMAGE)
            img = Image.open(LOCAL_IMAGE).convert('RGB').convert('L').point(
                lambda x: 255 if x >= 200 else 0, '1')

            if epd:
                epd.display(epd.getbuffer(img))
                print(f'[{time.strftime("%H:%M:%S")}] displayed', flush=True)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f'error: {e}', flush=True)

        time.sleep(60)

if __name__ == '__main__':
    main()
