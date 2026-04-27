TEST=False

import time
import json
from PIL import BdfFontFile, Image, ImageDraw
from rgbmatrix import RGBMatrix, RGBMatrixOptions

options = RGBMatrixOptions()
options.hardware_mapping = "adafruit-hat"
options.gpio_slowdown = 2
options.cols = 64

matrix = RGBMatrix(options=options)

with open("/home/pi/adafruit-rgb-led-matrix/fonts/5x8.bdf", "rb") as ff:
    fontfile = BdfFontFile.BdfFontFile(ff)
    font = fontfile.to_imagefont()


def show_flights(testarray=None):
    if testarray:
        data = {"aircraft":[{"flight":test_callsign} for test_callsign in testarray]}
    else:
        with open("/run/dump1090-fa/aircraft.json", "r") as f:
            data = json.load(f)

    img = Image.new('RGB', (64, 32))
    draw = ImageDraw.Draw(img)

    ypos = 0
    for aircraft in data['aircraft']:
        if 'flight' in aircraft.keys():
            callsign = aircraft['flight']
            draw.text((0,ypos), callsign, fill=(255,255,255), font=font)
            ypos += 9

    matrix.SetImage(img)


def watch_flights():
    while True:
        show_flights()
        time.sleep(2)


if __name__ == "__main__":
    if TEST:
        show_flights(['SKW5389','testing...'])
        time.sleep(10)
    else:
        watch_flights()
