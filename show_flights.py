#!/home/pi/rgbmatrix-flightoverhead/pyrgbmatrix/bin/python

import sys
import time
import json
import numpy as np
from pathlib import Path
from PIL import BdfFontFile, Image, ImageDraw
from rgbmatrix import RGBMatrix, RGBMatrixOptions

TEST = False
HERE_DIR = Path(__file__).resolve().parent


options = RGBMatrixOptions()
options.hardware_mapping = "adafruit-hat"
options.gpio_slowdown = 2
options.cols = 64

matrix = RGBMatrix(options=options)


# Default settings, will be overwritten by values in settings.json
SETTINGS = {
    "selection_method": "radius",
    "bg_color": "#000",
    "fg_color": "#fff",
    "lat": 34.427746,
    "lon": -119.840742,
    "radius": 4
}

try:
    with open(HERE_DIR/"settings.json", "r") as f:
        json_settings = json.load(f)
        for key, val in json_settings.items():
            SETTINGS[key] = val
except OSError:
    print("settings.json not found. Using default settings.")



with open("/home/pi/adafruit-rgb-led-matrix/fonts/5x8.bdf", "rb") as ff:
    fontfile = BdfFontFile.BdfFontFile(ff)
    font = fontfile.to_imagefont()


def get_distance(lat2, lon2):
    R = 6373  # Earth radius in km
    lat1 = SETTINGS['lat']  # Receiver latitude
    lon1 = SETTINGS['lon']  # Receiver longitude

    d_lat = np.deg2rad(lat2 - lat1)
    d_lon = np.deg2rad(lon2 - lon1)
    lat1_rads = np.deg2rad(lat1)
    lat2_rads = np.deg2rad(lat2)

    a = (np.sin(d_lat/2)**2
         + np.cos(lat1_rads)*np.cos(lat2_rads) * np.sin(d_lon/2)**2)

    return 2 * R * np.arcsin(np.sqrt(a))


def get_aircraft_distance(aircraft):
    lat2 = aircraft['lat']  # Aircraft latitude
    lon2 = aircraft['lon']  # Aircraft longitude

    return get_distance(lat2, lon2)


def in_area(lat, lon):
    if SETTINGS['selection_method'] == 'rect':
        return (lat > SETTINGS['lat_min'] and
                lat < SETTINGS['lat_max'] and
                lon > SETTINGS['lon_min'] and
                lon < SETTINGS['lon_max'])
    elif SETTINGS['selection_method'] == 'radius':
        dist = get_distance(lat, lon)
        print(f"Distance: {dist}km")
        return get_distance(lat, lon) < SETTINGS['radius']


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
        print(f"JSON Data: {aircraft}")
        return False

    return (alt < 5000 and in_area(lat, lon))


def get_overhead_aircraft():
    if TEST:
        json_path = HERE_DIR/"test.json"
    else:
        json_path = "/run/dump1090-fa/aircraft.json"

    with open(json_path, "r") as f:
        data = json.load(f)

    aircraft_list = []
    for aircraft in data['aircraft']:
        if is_overhead(aircraft):
            aircraft_list.append(aircraft)

    # Return only the closest aircraft
    if aircraft_list:
        if len(aircraft_list) > 1:
            return min(aircraft_list, key=get_aircraft_distance)
        else:
            return aircraft_list[0]
    else:
        return None


def get_aircraft_info(aircraft):
    if aircraft is None:
        return None
    return [aircraft['flight']]


def display_text(text_array=None):
    if text_array is None:
        matrix.Clear()
    else:
        img = Image.new('RGB', (64, 32), SETTINGS['bg_color'])
        draw = ImageDraw.Draw(img)
        ypos = 0

        for line in text_array:
            draw.text((0, ypos), line, fill=SETTINGS['fg_color'], font=font)
            ypos += 9

        matrix.SetImage(img)


def watch_flights():
    try:
        while True:
            aircraft = get_overhead_aircraft()
            lines = get_aircraft_info(aircraft)
            display_text(text_array=lines)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nCtrl-C received. Stopping...")


if __name__ == "__main__":
    watch_flights()
