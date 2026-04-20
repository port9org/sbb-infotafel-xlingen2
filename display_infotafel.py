#!/usr/bin/env python3
import sys
import time
import urllib.request
from PIL import Image

sys.path.append('/home/ke/e-Paper/RaspberryPi_JetsonNano/python/lib')
from waveshare_epd import epd7in5_V2

IMAGE_URL   = 'http://localhost:8080/sbb.png'
LOCAL_IMAGE = '/tmp/sbb_display.png'

epd = epd7in5_V2.EPD()
epd.init()
epd.Clear()

while True:
    urllib.request.urlretrieve(IMAGE_URL, LOCAL_IMAGE)
    img = Image.open(LOCAL_IMAGE).convert('RGB').convert('L').point(lambda x: 255 if x >= 200 else 0, '1')
    epd.display(epd.getbuffer(img))
    print(f'[{time.strftime("%H:%M:%S")}] ok', flush=True)
    time.sleep(60)
