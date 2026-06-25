"""
All settings used by show_flights.py

These are meant to be customized and overriden by values in a settings.json file.
A default JSON with these settings can be automatically created using
`utils.create_settings_json`.
"""

DEFAULT_SETTINGS = {
    "aeroapi_key": "",
    "selection_method": "radius",
    "bg_color": "#000",
    "fg_color": "#fff",
    "fg_color_error": "#f00",
    "lat": 34.427746,
    "lon": -119.840742,
    "lat_min": 0,
    "lat_max": 0,
    "lon_min": 0,
    "lon_max": 0,
    "radius": 4,
    "rgb_hardware_mapping": "adafruit-hat",
    "rgb_gpio_slowdown": 2,
    "rgb_rows": 32,
    "rgb_cols": 64,
    "font_path": "/home/pi/adafruit-rgb-led-matrix/fonts/5x8.bdf",
    "cache_dir": "/tmp",
}
