#!/usr/bin/env python3
import sys
import time
from PIL import Image

sys.path.append('/home/ke/e-Paper/RaspberryPi_JetsonNano/python/lib')
from waveshare_epd import epd7in5_V2

IMAGE_PATH = '/home/ke/sbb-infotafel-xlingen2/sbb.png'

epd = epd7in5_V2.EPD()
epd.init()
epd.Clear()

while True:
    img = Image.open(IMAGE_PATH).convert('RGB').convert('L').point(lambda x: 255 if x >= 200 else 0, '1')
    buf = epd.getbuffer(img)
    epd.display(buf)
    epd.display(buf)
    print(f'[{time.strftime("%H:%M:%S")}] ok', flush=True)
    time.sleep(60)
