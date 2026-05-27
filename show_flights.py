#!/home/pi/rgbmatrix-flightoverhead/pyrgbmatrix/bin/python
"""
Display nearby flights on an RGB LED matrix using output from dump1090-fa.

Reads settings from settings.json, monitors aircraft data from dump1090,
filters for low-altitude aircraft near a receiver location, and shows info
about the closest overhead flight on the matrix.
"""

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
    "fg_color_error": "#f00",
    "lat": 34.427746,
    "lon": -119.840742,
    "radius": 4,
}

try:
    with open(HERE_DIR / "settings.json", "r", encoding="utf-8") as settings_file:
        json_settings = json.load(settings_file)
        for key, val in json_settings.items():
            SETTINGS[key] = val
except OSError:
    print("settings.json not found. Using default settings.")


with open("/home/pi/adafruit-rgb-led-matrix/fonts/5x8.bdf", "rb") as ff:
    fontfile = BdfFontFile.BdfFontFile(ff)
    font = fontfile.to_imagefont()


def get_distance(lat2, lon2):
    """
    Compute the great-circle distance from the receiver to a point.

    Uses the Haversine formula to calculate distance in kilometers between the
    configured receiver location and the provided latitude/longitude.

    Parameters
    ----------
    lat2 : float
        Target latitude.
    lon2 : float
        Target longitude.

    Returns
    -------
    float
        Distance in kilometers.
    """

    earth_radius = 6373  # Earth radius in km
    lat1 = SETTINGS["lat"]  # Receiver latitude
    lon1 = SETTINGS["lon"]  # Receiver longitude

    d_lat = np.deg2rad(lat2 - lat1)
    d_lon = np.deg2rad(lon2 - lon1)
    lat1_rads = np.deg2rad(lat1)
    lat2_rads = np.deg2rad(lat2)

    a = (
        np.sin(d_lat / 2) ** 2
        + np.cos(lat1_rads) * np.cos(lat2_rads) * np.sin(d_lon / 2) ** 2
    )

    return 2 * earth_radius * np.arcsin(np.sqrt(a))


def get_aircraft_distance(aircraft):
    """
    Return the distance from the receiver to an aircraft.

    Parameters
    ----------
    aircraft : dict
        ADS-B aircraft record containing "lat" and "lon".

    Returns
    -------
    float
        Distance in kilometers.
    """

    lat2 = aircraft["lat"]  # Aircraft latitude
    lon2 = aircraft["lon"]  # Aircraft longitude

    return get_distance(lat2, lon2)


def in_area(lat, lon):
    """
    Check whether a coordinate falls within the configured selection area.

    Supports rectangular or radial selection based on settings.json.

    Parameters
    ----------
    lat : float
        Latitude to check.
    lon : float
        Longitude to check.

    Returns
    -------
    bool
        True if the location is inside the configured area.
    """

    if SETTINGS["selection_method"] == "rect":
        return (
            SETTINGS["lat_min"] < lat < SETTINGS["lat_max"]
            and SETTINGS["lon_min"] < lon < SETTINGS["lon_max"]
        )

    if SETTINGS["selection_method"] == "radius":
        dist = get_distance(lat, lon)
        print(f"Distance: {dist}km")
        return get_distance(lat, lon) < SETTINGS["radius"]

    print("Invalid selection method in settings.json. Defaulting to radius.")
    dist = get_distance(lat, lon)
    print(f"Distance: {dist}km")
    return get_distance(lat, lon) < SETTINGS["radius"]


def is_overhead(aircraft):
    """
    Determine whether an aircraft is overhead and low enough to be interesting.

    Filters aircraft by available flight data, barometric altitude, and selection
    area. Only aircraft below 5000 feet that are inside the configured area
    qualify.

    Parameters
    ----------
    aircraft : dict
        ADS-B aircraft record.

    Returns
    -------
    bool
        True if the aircraft is overhead and valid.
    """

    keys = aircraft.keys()

    if "flight" not in keys:
        return False

    try:
        alt = aircraft["alt_baro"]
        lat = aircraft["lat"]
        lon = aircraft["lon"]
    except KeyError as e:
        print(f"Key not found in json. {e}", file=sys.stderr)
        print(f"JSON Data: {aircraft}")
        return False

    return alt < 5000 and in_area(lat, lon)


def get_overhead_aircraft():
    """
    Load aircraft data and return the closest overhead aircraft.

    Reads from test.json when TEST mode is enabled, otherwise from the dump1090
    JSON feed. Aircraft are filtered by the `is_overhead` function and the
    nearest matching aircraft is returned.

    Returns
    -------
    dict or None
        The closest overhead aircraft record, or None if none match filters.
    """

    if TEST:
        json_path = HERE_DIR / "test.json"
    else:
        json_path = "/run/dump1090-fa/aircraft.json"

    with open(json_path, "r", encoding="utf-8") as aircraft_file:
        data = json.load(aircraft_file)

    aircraft_list = []
    for aircraft in data["aircraft"]:
        if is_overhead(aircraft):
            aircraft_list.append(aircraft)

    # Return only the closest aircraft
    if aircraft_list:
        if len(aircraft_list) > 1:
            return min(aircraft_list, key=get_aircraft_distance)
        return aircraft_list[0]
    return None


def get_aircraft_info(aircraft):
    """
    Extract displayable text from an aircraft record.

    Parameters
    ----------
    aircraft : dict or None
        Aircraft record returned by `get_overhead_aircraft`.

    Returns
    -------
    list[str] or None
        Lines of text to render, or None if no aircraft is present.
    """

    if aircraft is None:
        return None
    return [aircraft["flight"]]


def display_text(text_array=None, error=False):
    """
    Render a message on the RGB matrix.

    If nothing to display, just clear the display.

    Parameters
    ----------
    text_array : list[str], optional
        Text lines to render. If None, the matrix is cleared.
    error : bool, optional
        Use the error foreground color when True.
    """

    if text_array is None:
        matrix.Clear()
    else:
        fg_color = SETTINGS["fg_color"] if not error else SETTINGS["fg_color_error"]
        img = Image.new("RGB", (64, 32), SETTINGS["bg_color"])
        draw = ImageDraw.Draw(img)
        ypos = 0

        for line in text_array:
            draw.text((0, ypos), line, fill=fg_color, font=font)
            ypos += 9

        matrix.SetImage(img)


def watch_flights():
    """
    Continuously monitor overhead flights and update the matrix display.

    Polls the aircraft JSON feed at a fixed interval and displays the flight
    identifier for the nearest qualifying aircraft. If the feed cannot be read,
    an error message is shown instead.
    """

    try:
        while True:
            try:
                aircraft = get_overhead_aircraft()
                lines = get_aircraft_info(aircraft)
                display_text(text_array=lines)
                time.sleep(2)
            except OSError:
                print("Data json not found!")
                lines = ["Data json", "not found"]
                display_text(text_array=lines, error=True)
                time.sleep(10)
    except KeyboardInterrupt:
        print("\nCtrl-C received. Stopping...")


if __name__ == "__main__":
    watch_flights()
