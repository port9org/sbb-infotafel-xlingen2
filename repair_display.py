#!/usr/bin/env python3
"""Run N full black/white cycles to clear ghost images and reset pixel charge."""
import sys
import time

sys.path.append('/home/ke/e-Paper/RaspberryPi_JetsonNano/python/lib')
from waveshare_epd import epd7in5_V2
from PIL import Image

CYCLES = 10

epd = epd7in5_V2.EPD()
epd.init()

black = epd.getbuffer(Image.new('1', (epd.width, epd.height), 0))
white = epd.getbuffer(Image.new('1', (epd.width, epd.height), 1))

for i in range(CYCLES):
    print(f'Cycle {i+1}/{CYCLES}...', flush=True)
    epd.display(black)
    epd.display(white)

epd.sleep()
print('Done.', flush=True)
