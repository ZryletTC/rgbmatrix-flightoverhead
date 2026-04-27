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


def get_flights():
    with open("/run/dump1090-fa/aircraft.json", "r") as f:
        data = json.load(f)

    lines = []
    for aircraft in data['aircraft']:
        if 'flight' in aircraft.keys():
            lines.append(aircraft['flight'])

    return lines


def display_text(text_array=[]):
    img = Image.new('RGB', (64, 32))
    draw = ImageDraw.Draw(img)
    ypos = 0

    for line in text_array:
        draw.text((0,ypos), line, fill=(255,255,255), font=font)
        ypos += 9

    matrix.SetImage(img)


def watch_flights():
    while True:
        if TEST:
            lines = ["testing...", "1", "2", "3"]
        else:
            lines = get_flights()
        display_text(text_array=lines)
        time.sleep(2)


if __name__ == "__main__":
    watch_flights()
