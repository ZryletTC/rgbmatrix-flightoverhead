#!/home/pi/rgbmatrix-flightoverhead/pyrgbmatrix/bin/python
"""
Display nearby flights on an RGB LED matrix using output from dump1090-fa.

Reads settings from settings.json, monitors aircraft data from dump1090,
filters for low-altitude aircraft near a receiver location, and shows info
about the closest overhead flight on the matrix.

Configuration should be provided by the settings.json file in the same directory as
this script. Function docstrings include a Settings section describing which
configuration settings they use.
"""

import logging
from logging.handlers import RotatingFileHandler
from pprint import pformat
import time
import json
import requests
import numpy as np
from pathlib import Path
from PIL import BdfFontFile, Image, ImageDraw
from rgbmatrix import RGBMatrix, RGBMatrixOptions

TEST = False
HERE_DIR = Path(__file__).resolve().parent

# Configure logging to stderr and rotating logfiles
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(funcName)s: %(message)s")

# Warning and above will be sent to stderr
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(formatter)

# All messages will be sent to log file
file_handler = RotatingFileHandler(
    "/var/log/rgbmatrix-flightoverhead.log",
    maxBytes=100 * 1024 * 1024,
    backupCount=5,
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


# Default settings, will be overwritten by values in settings.json
DEFAULT_SETTINGS = {
    "selection_method": "radius",
    "bg_color": "#000",
    "fg_color": "#fff",
    "fg_color_error": "#f00",
    "lat": 34.427746,
    "lon": -119.840742,
    "radius": 4,
    "rgb_hardware_mapping": "adafruit-hat",
    "rgb_gpio_slowdown": 2,
    "rgb_rows": 32,
    "rgb_cols": 64,
    "font_path": "/home/pi/adafruit-rgb-led-matrix/fonts/5x8.bdf",
    "cache_dir": "/tmp",
}


class FlightMonitor:
    """
    Monitor nearby aircraft and display flight information on an RGB LED matrix.

    This class integrates aircraft data from dump1090 with flight information from
    AeroAPI to display details about the nearest overhead flight on an RGB LED matrix
    display. It filters aircraft by altitude and geographic location, caches API
    responses, and continuously updates the display.

    Attributes
    ----------
    settings : dict
        Configuration dictionary containing receiver location, matrix settings,
        API keys, and display parameters.
    matrix : rgbmatrix.RGBMatrix
        RGB LED matrix instance used to display flight data.
    font : PIL.ImageFont.ImageFont
        Font used for rendering text on the matrix.
    """

    def __init__(self, *, settings_path=None, test=False):
        # Initialize settings
        self.settings = DEFAULT_SETTINGS.copy()
        self.load_settings(settings_path=settings_path)
        logger.debug("Settings after load:\n%s", pformat(self.settings))

        # Initialize matrix
        options = RGBMatrixOptions()
        options.hardware_mapping = self.settings["rgb_hardware_mapping"]
        options.gpio_slowdown = int(self.settings["rgb_gpio_slowdown"])
        options.rows = int(self.settings["rgb_rows"])
        options.cols = int(self.settings["rgb_cols"])
        self.matrix = RGBMatrix(options=options)
        logger.debug(
            "Initialized RGBMatrix rows=%d cols=%d mapping=%s gpio_slowdown=%d",
            options.rows,
            options.cols,
            options.hardware_mapping,
            options.gpio_slowdown,
        )

        # Setup font for text on rgb display
        self.set_font(self.settings["font_path"])
        logger.debug("Font loaded: %s", self.settings["font_path"])

        # Choose path of data feed depending on TEST
        if test:
            self.feed_path = HERE_DIR / "test.json"
        else:
            self.feed_path = "/run/dump1090-fa/aircraft.json"
        logger.debug("Reading aircraft data from %s", self.feed_path)

    def load_settings(self, settings_path=None):
        """
        Load settings from a JSON file.

        Updates the instance settings dictionary with values from the provided
        configuration file. If the file does not exist, settings will remain unchanged.

        Parameters
        ----------
        settings_path : str or Path, optional
            Path to settings.json file. If not provided, looks for settings.json
            in the same directory as this script.
        """

        if not settings_path:
            settings_path = HERE_DIR / "settings.json"

        if not settings_path.exists():
            logger.warning(
                "Settings file (%s) not found. Settings unchanged.", settings_path
            )
            return

        try:
            with open(settings_path, "r", encoding="utf-8") as settings_file:
                json_settings = json.load(settings_file)
                self.settings.update(json_settings)
                logger.debug(
                    "Loaded settings from %s:\n%s",
                    settings_path,
                    pformat(json_settings),
                )
        except (OSError, ValueError, TypeError):
            logger.exception(
                "Settings file (%s) could not be read. Settings unchanged.",
                settings_path,
            )

    def set_font(self, font_path):
        """
        Load a BDF font file for text rendering on the RGB matrix.

        Parameters
        ----------
        font_path : str or Path
            Path to the BDF font file to load.

        Notes
        -----
        Currently only supports BDF font files. Future enhancement should support
        additional font formats.
        """

        # TODO: Allow font extensions other than bdf
        logger.debug("Loading font from %s", font_path)
        try:
            with open(font_path, "rb") as ff:
                fontfile = BdfFontFile.BdfFontFile(ff)
                self.font = fontfile.to_imagefont()
        except Exception:
            logger.exception("Failed to load font %s", font_path)
            raise

    def get_distance(self, lat2, lon2):
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

        Settings
        --------
        lat : float
            Receiver latitude used as the reference point.
        lon : float
            Receiver longitude used as the reference point.

        Returns
        -------
        float
            Distance in kilometers.
        """

        earth_radius = 6373  # Earth radius in km
        lat1 = self.settings["lat"]  # Receiver latitude
        lon1 = self.settings["lon"]  # Receiver longitude

        logger.debug(
            "Computing distance from (%f,%f) to (%f,%f).", lat1, lon1, lat2, lon2
        )

        d_lat = np.deg2rad(lat2 - lat1)
        d_lon = np.deg2rad(lon2 - lon1)
        lat1_rads = np.deg2rad(lat1)
        lat2_rads = np.deg2rad(lat2)

        a = (
            np.sin(d_lat / 2) ** 2
            + np.cos(lat1_rads) * np.cos(lat2_rads) * np.sin(d_lon / 2) ** 2
        )

        return 2 * earth_radius * np.arcsin(np.sqrt(a))

    def get_aircraft_distance(self, aircraft):
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

        return self.get_distance(aircraft["lat"], aircraft["lon"])

    def in_area(self, lat, lon):
        """
        Check whether a coordinate falls within the configured selection area.

        Supports rectangular or radial selection based on settings.json.

        Parameters
        ----------
        lat : float
            Latitude to check.
        lon : float
            Longitude to check.

        Settings
        --------
        selection_method : {'rect', 'radius'}
            Choice of rectangular or radial selection.
        lat_min, lat_max : float
            Minimum and maximum latitude values used when selection_method is 'rect'.
        lon_min, lon_max : float
            Minimum and maximum longitude values used when selection_method is 'rect'.
        radius : float
            Radius in kilometers used when selection_method is 'radius'.

        Returns
        -------
        bool
            True if the location is inside the configured area.
        """

        if self.settings["selection_method"] == "rect":
            return (
                self.settings["lat_min"] < lat < self.settings["lat_max"]
                and self.settings["lon_min"] < lon < self.settings["lon_max"]
            )

        if self.settings["selection_method"] != "radius":
            logger.error(
                "Invalid selection method in settings.json. Defaulting to radius."
            )

        # Radius selection method
        dist = self.get_distance(lat, lon)
        return dist < self.settings["radius"]

    def is_overhead(self, aircraft):
        """
        Determine whether an aircraft is overhead and low enough to be interesting.

        Filters aircraft by available flight data, barometric altitude, and selection
        area. Only aircraft below 5000 feet that are inside the configured area
        qualify.

        Parameters
        ----------
        aircraft : dict
            ADS-B aircraft record.

        Settings
        --------
        alt_baro : int
            Threshold altitude, in feet, above which aircraft will be filtered out.

        Returns
        -------
        bool
            True if the aircraft is overhead and valid.
        """

        if "flight" not in aircraft:
            return False

        try:
            if aircraft['alt_baro'] == 'ground':
                return False
            alt = float(aircraft["alt_baro"])
            lat = float(aircraft["lat"])
            lon = float(aircraft["lon"])
        except KeyError as err:
            logger.debug("Key not found in json: %s", err)
            logger.debug("JSON Data:\n%s", pformat(aircraft))
            return False

        return alt < 5000 and self.in_area(lat, lon)

    def get_overhead_aircraft(self):
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

        with open(self.feed_path, "r", encoding="utf-8") as aircraft_file:
            data = json.load(aircraft_file)

        logger.debug(
            "Loaded %d aircraft from data feed.", len(data.get("aircraft", []))
        )

        aircraft_list = [a for a in data["aircraft"] if self.is_overhead(a)]
        logger.debug("Filtered to %d overhead aircraft.", len(aircraft_list))

        # Return only the closest aircraft
        if aircraft_list:
            if len(aircraft_list) > 1:
                return min(aircraft_list, key=self.get_aircraft_distance)
            return aircraft_list[0]
        return None

    def get_aeroapi_flight_info(self, ident):
        """
        Fetch flight details from AeroAPI for a given flight identifier.

        Parameters
        ----------
        ident : str
            Flight identifier to query.

        Returns
        -------
        dict or None
            Parsed AeroAPI JSON response, or None if the request fails.

        Settings
        --------
        aeroapi_key : str
            API key for AeroAPI, read from settings.json.
        """

        api_key = self.settings.get("aeroapi_key")
        if not api_key:
            logger.error("AeroAPI key is not configured in settings.json")
            return None

        cache_path = Path(self.settings["cache_dir"]) / f"aeroapi-{ident}.json"

        if cache_path.exists():
            try:
                with cache_path.open("r", encoding="utf-8") as cache_file:
                    logger.debug("Loaded cached AeroAPI response for %s", ident)
                    return json.load(cache_file)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Invalid AeroAPI cache %s: %s", cache_path, exc)

        logger.debug("AeroAPI cache miss for %s, will request live data.", ident)

        with open("failed.txt", "r", encoding="utf-8") as f:
            failed_idents = f.readlines()
        if ident in failed_idents:
            logger.info("Skipping previously failed ident (%s).", ident)
            return None

        url = f"https://aeroapi.flightaware.com/aeroapi/flights/{ident}"
        headers = {"x-apikey": api_key}

        try:
            logger.debug("Requesting AeroAPI for %s: %s", ident, url)
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()

            try:
                with cache_path.open("w", encoding="utf-8") as cache_file:
                    json.dump(result, cache_file)
                    logger.debug(
                        "AeroAPI response for %s written to file %s", ident, cache_path
                    )
            except OSError:
                logger.exception("Could not write AeroAPI cache %s", cache_path)

            return result
        except requests.RequestException:
            logger.exception("AeroAPI request failed!")
            with open("failed.txt", "a", encoding="utf-8") as f:
                f.write(ident)
            return None

    def show_airline_flight(self, flight_info):
        """
        Display information on the RGB display for the given commerical flight.

        Future work:
        - Add airline logo

        Parameters
        ----------
        text_array : list[str], optional
            Text lines to render. If None, the matrix is cleared.
        error : bool, optional
            Use the error foreground color when True.

        Settings
        --------
        fg_color : str
            Default foreground color (used when `error` is False).
        bg_color : str
            Background color shown on the RGB matrix display.
        font_path : str
            Font file to use when displaying text.
        """

        width = self.settings["rgb_cols"]
        height = self.settings["rgb_rows"]

        img = Image.new("RGB", (width, height), self.settings["bg_color"])
        draw = ImageDraw.Draw(img)

        # Display flight number
        ident = flight_info.get("ident_iata", flight_info["ident"])
        draw.text(
            (width / 2, 0),
            ident,
            fill=self.settings["fg_color"],
            font=self.font,
            anchor="ma",
        )

        # Display airline logo (if icao code in flight_info)
        if "operator_icao" in flight_info:
            operator = flight_info["operator_icao"]
            for logo_dir in ["flightaware_logos", "radarbox_logos", "custom_logos"]:
                logo_path = HERE_DIR / "airline-logos" / logo_dir / f"{operator}.png"
                if logo_path.exists():
                    with Image.open(logo_path) as logo_png:
                        logo = logo_png.convert("RGBA")
                        # TODO: This size should become dynamic to adjust with font size
                        logo.thumbnail((8, 8))
                        img.paste(logo, mask=logo.split()[3])

        self.matrix.SetImage(img)

    def show_general_flight(self, flight_info):
        """
        Display information on the RGB display for the given generic flight.

        Parameters
        ----------
        text_array : list[str], optional
            Text lines to render. If None, the matrix is cleared.
        error : bool, optional
            Use the error foreground color when True.

        Settings
        --------
        fg_color : str
            Default foreground color (used when `error` is False).
        bg_color : str
            Background color shown on the RGB matrix display.
        font_path : str
            Font file to use when displaying text.
        """

        width = self.settings["rgb_cols"]
        height = self.settings["rgb_rows"]

        img = Image.new("RGB", (width, height), self.settings["bg_color"])
        draw = ImageDraw.Draw(img)

        ident = flight_info["ident"]

        draw.text(
            (width / 2, 0),
            ident,
            fill=self.settings["fg_color"],
            font=self.font,
            anchor="ma",
        )

        self.matrix.SetImage(img)

    def get_aircraft_info(self, aircraft):
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
            logger.debug("No aircraft to display.")
            return None

        ident = aircraft["flight"].strip()
        aeroapi_json = self.get_aeroapi_flight_info(ident)
        if aeroapi_json is None:
            logger.debug("No flight info returned from AeroAPI for ident (%s).", ident)
            return None

        possible_flights = aeroapi_json["flights"]

        if len(possible_flights) == 0:
            logger.debug("No flight info returned for ident (%s).", ident)
            return None

        def status_is_current(status):
            return "En Route" in status

        current_flight_list = [
            flight for flight in possible_flights if status_is_current(flight["status"])
        ]

        if len(current_flight_list) == 0:
            logger.warning("None of returned flight info sets appear to be current!")
            logger.warning("All info sets:\n%s", possible_flights)
            return None
        if len(current_flight_list) != 1:
            logger.warning("Multiple flight info sets appear current. Using first.")
            logger.warning("Current info sets:\n%s", current_flight_list)
        flight_info = current_flight_list[0]

        return flight_info

    def display_text(self, text_array=None, error=False):
        """
        Render a message on the RGB matrix.

        If nothing to display, just clear the display.

        Parameters
        ----------
        text_array : list[str], optional
            Text lines to render. If None, the matrix is cleared.
        error : bool, optional
            Use the error foreground color when True.

        Settings
        --------
        fg_color : str
            Default foreground color (used when `error` is False).
        fg_color_error : str
            Foreground color used when `error` is True.
        bg_color : str
            Background color shown on the RGB matrix display.
        """

        if text_array is None:
            logger.debug("Clearing display.")
            self.matrix.Clear()
            return

        if error:
            fg_color = self.settings["fg_color_error"]
        else:
            fg_color = self.settings["fg_color"]

        logger.debug("Rendering text on matrix (error=%s):\n%s", error, text_array)

        width = self.settings["rgb_cols"]
        height = self.settings["rgb_rows"]

        img = Image.new("RGB", (width, height), self.settings["bg_color"])
        draw = ImageDraw.Draw(img)
        ypos = 0

        for line in text_array:
            draw.text((0, ypos), line, fill=fg_color, font=self.font)
            ypos += 8

        self.matrix.SetImage(img)

    def show_flight(self):
        """
        Check for overhead flights and update the matrix display.

        Polls the aircraft JSON feed at a fixed interval and displays info for the
        nearest qualifying aircraft.
        """

        aircraft = self.get_overhead_aircraft()
        if aircraft:
            logger.debug("Selected aircraft: %s", pformat(aircraft["flight"]))
        flight_info = self.get_aircraft_info(aircraft)

        if flight_info is None:
            logger.debug("No flight info to show. Clearing display.")
            self.matrix.Clear()

        # Format airline and general aviation flights differently
        if flight_info["type"] == "Airline":
            self.show_airline_flight(flight_info)
        else:
            self.show_general_flight(flight_info)

    def watch_flights(self):
        """
        Continuously monitor overhead flights and update the matrix display.

        Polls the aircraft JSON feed at a fixed interval and displays the flight
        identifier for the nearest qualifying aircraft. If the feed cannot be read,
        an error message is shown instead.
        """

        logger.info("Starting flight monitoring...")

        try:
            while True:
                try:
                    self.show_flight()
                    time.sleep(2)
                except OSError:
                    logger.exception("Dump1090 data json not found!")
                    lines = ["Data json", "not found"]
                    self.display_text(text_array=lines, error=True)
                    time.sleep(10)
        except KeyboardInterrupt:
            logger.info("\nCtrl-C received. Stopping...")
            self.matrix.Clear()


if __name__ == "__main__":
    monitor = FlightMonitor(test=TEST)
    monitor.watch_flights()
