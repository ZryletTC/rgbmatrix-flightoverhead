import sys
import time
import json
from pathlib import Path
from PIL import BdfFontFile, Image, ImageDraw
from rgbmatrix import RGBMatrix, RGBMatrixOptions

TEST=False
HERE_DIR = Path(__file__).resolve().parent


options = RGBMatrixOptions()
options.hardware_mapping = "adafruit-hat"
options.gpio_slowdown = 2
options.cols = 64

matrix = RGBMatrix(options=options)


with open(HERE_DIR/"settings.json", "r") as f:
    settings = json.load(f)


with open("/home/pi/adafruit-rgb-led-matrix/fonts/5x8.bdf", "rb") as ff:
    fontfile = BdfFontFile.BdfFontFile(ff)
    font = fontfile.to_imagefont()


def is_overhead(aircraft):
    keys = aircraft.keys()

    if 'flight' not in keys:
        return False

    try:
        alt = aircraft['alt_baro']
        lat = aircraft['lat']
        lon = aircraft['lon']
    except KeyError as e:
        print(f"Key not found in json. {e}", file=sys.stderr)
        return False

    return (alt < 5000 and
            lat > settings['lat_min'] and lat < settings['lat_max'] and
            lon > settings['lon_min'] and lon < settings['lon_max'])


def get_flights():
    if TEST:
        json_path = HERE_DIR/"test.json"
    else:
        json_path = "/run/dump1090-fa/aircraft.json"

    with open(json_path, "r") as f:
        data = json.load(f)

    lines = []
    for aircraft in data['aircraft']:
        if is_overhead(aircraft):
            lines.append(aircraft['flight'])
    return lines


def display_text(text_array=[]):
    if text_array:
        img = Image.new('RGB', (64, 32), settings['bg_color'])
        draw = ImageDraw.Draw(img)
        ypos = 0

        for line in text_array:
            draw.text((0,ypos), line, fill=(255,255,255), font=font)
            ypos += 9

        matrix.SetImage(img)
    else:
        matrix.Clear()


def watch_flights():
    while True:
        lines = get_flights()
        display_text(text_array=lines)
        time.sleep(2)


if __name__ == "__main__":
    watch_flights()
