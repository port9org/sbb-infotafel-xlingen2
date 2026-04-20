#!/usr/bin/env python3
import sys
import time
from PIL import Image

sys.path.append('/home/ke/e-Paper/RaspberryPi_JetsonNano/python/lib')
try:
    from waveshare_epd import epd7in5_V2
except ImportError:
    print('Warning: waveshare_epd not found — preview mode', flush=True)
    epd7in5_V2 = None

IMAGE_PATH = '/home/ke/sbb-infotafel-xlingen2/sbb.png'
HEARTBEAT  = '/tmp/display_heartbeat'

def main():
    epd = epd7in5_V2.EPD() if epd7in5_V2 else None
    if epd:
        epd.init()

    while True:
        try:
            img = Image.open(IMAGE_PATH).convert('1', dither=Image.NONE)
            if epd:
                buf = epd.getbuffer(img)
                epd.display(buf)
                epd.display(buf)
            open(HEARTBEAT, 'w').close()
            print(f'[{time.strftime("%H:%M:%S")}] ok', flush=True)
        except KeyboardInterrupt:
            if epd:
                epd7in5_V2.epdconfig.module_exit(cleanup=True)
            break
        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] error: {e}', flush=True)
        time.sleep(60)

if __name__ == '__main__':
    main()
