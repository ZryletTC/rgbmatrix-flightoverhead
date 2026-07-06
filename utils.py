"""
Set of utility functions for processing data.
"""

import json
import logging
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from settings import DEFAULT_SETTINGS

HERE_DIR = Path(__file__).resolve().parent

logger = logging.getLogger("rgbmatrix-flightoverhead")


def create_settings_json():
    """Create a default settings file."""
    with open("settings.json", "w", encoding="utf-8") as f:
        json.dump(DEFAULT_SETTINGS, f, indent=4)


def get_airline_logo(airline_icao, width, height):
    """
    Load an airline's logo given its ICAO identifier and scale it to fit inside the
    given width and height.

    If no logo is found for the airline, return None.
    """

    # TODO: Make black logos visible somehow

    # Directories listed in order of preference
    for logo_dir in [
        "flightaware_logos",
        "radarbox_logos",
        "custom_logos",
        "fr24_banners",
        "radarbox_banners",
        "avcodes_banners",
        "custom_banners",
    ]:
        logo_path = HERE_DIR / "assets/airline-logos" / logo_dir / f"{airline_icao}.png"
        logger.debug("Checking for path (%s)...", logo_path)
        if logo_path.exists():
            logger.debug("Showing airline logo: %s", logo_path)
            with Image.open(logo_path) as logo_png:
                logo_bbox = logo_png.getbbox()
                logo = logo_png.crop(logo_bbox).convert("RGBA")
                logo.thumbnail((width, height))
                return logo

    logger.warning("No logo found for airline (%s).", airline_icao)
    return None


def abbreviate(word, desired_length=4):
    """Abbreviate a given word to the desired length. Defaults to 4 letters."""

    if len(word) <= desired_length:
        return word

    def is_vowel(char):
        return char.lower() in "aeiouy"

    abbreviation = word[0]
    consonants = [c for c in list(word[1:]) if not is_vowel(c)]
    # print(f"Consonants: {consonants}")

    if len(consonants) >= desired_length - 1:
        if desired_length == 2:
            abbreviation += consonants[-1]
        elif desired_length > 2:
            abbreviation += "".join(consonants[0 : desired_length - 2]) + consonants[-1]
    else:
        if consonants:
            consonants_re = "[" + "".join(consonants) + "]"
            vowel_groups = re.split(consonants_re, word[1:])
        else:
            vowel_groups = [word[1:]]
        while vowel_groups[-1] == "":
            vowel_groups.pop(-1)
        vowels_needed = desired_length - len(consonants) - 1
        while vowels_needed > 0:
            # print(abbreviation)
            # print(f"Vowel groups: {vowel_groups}")
            if vowel_groups[0]:
                num_to_grab = 1 + max([vowels_needed - len(vowel_groups), 0])
                # print(f"Still need {vowels_needed} vowels.")
                # print(f"Grabbing: {num_to_grab}")
                abbreviation += vowel_groups.pop(0)[0:num_to_grab]
                vowels_needed -= num_to_grab
            else:
                vowel_groups.pop(0)
            if consonants:
                abbreviation += consonants.pop(0)
        abbreviation += "".join(consonants)
    return abbreviation


def format_to_fit(text, width, *, draw: ImageDraw, font: ImageFont.ImageFont):
    """
    Make a string fit into a certain width.

    Parameters
    ----------
    text : str
        Text to parse and fit into width.
    width : int
        The width in pixels to fit text into.
    draw : ImageDraw
        ImageDraw object used for determining width of text when displayed.
    font : ImageFont.ImageFont
        Font to display text with.
    """

    text_width = draw.textlength(text, font=font)
    if text_width <= width:
        return text, text_width

    # Start by removing things in parentheses
    logger.debug("Shortening string (%s) by removing parentheses.", text)
    text = re.sub(r"\(.*?\)", "", text).strip()

    text_width = draw.textlength(text, font=font)
    while text_width > width:
        longest_word = max(re.split(r"\W+", text), key=len)
        if len(longest_word) <= 4:
            logger.error("Can't shorten this string any further: (%s)", text)
            break

        text = re.sub(longest_word, abbreviate(longest_word), text)
        text_width = draw.textlength(text, font=font)

    return text, text_width
