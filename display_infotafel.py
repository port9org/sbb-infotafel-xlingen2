#!/usr/bin/env python3
import sys
import time
from PIL import Image

sys.path.append('/home/ke/e-Paper/RaspberryPi_JetsonNano/python/lib')
from waveshare_epd import epd7in5_V2

IMAGE_PATH = '/home/ke/sbb-infotafel-xlingen2/sbb.png'

epd = epd7in5_V2.EPD()
epd.init()

while True:
    buf = epd.getbuffer(Image.open(IMAGE_PATH))
    epd.display(buf)
    epd.display(buf)
    print(f'[{time.strftime("%H:%M:%S")}] ok', flush=True)
    time.sleep(60)
