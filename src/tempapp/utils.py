import json
import os
from datetime import datetime
from typing import Tuple
from zoneinfo import ZoneInfo

import polars as pl
from coloraide import Color
from coloraide.interpolate import Interpolator
from polars import DataFrame


def load_settings() -> dict:
    settings_path = os.environ.get("APP_SETTINGS", "./settings.json")
    with open(settings_path) as f:
        settings = json.load(f)
    return settings


SETTINGS = load_settings()

palette = [
    "#313695",
    "#4575B4",
    "#74ADD1",
    "#ABD9E9",
    "#E0F3F8",
    "#FFFFBF",
    "#FEE090",
    "#FDAE61",
    "#F46D43",
    "#D73027",
    "#A50026",
]

interpolator = Color.interpolate(palette, space="srgb")


def dot_to_comma(num: float) -> str:
    """Take a float and turn it into a string with a comma for decimal"""
    return str(num).replace(".", ",")


def load_data() -> DataFrame:
    """Loads data for use in the app"""
    return pl.read_parquet(SETTINGS["data"])


def split_floor_data(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Split any df for each floor. Useful for plotting stuff"""
    # The names of each floor in a list
    floors = df.select(pl.col("floor")).unique().to_series().sort()

    # Produce 3 different dataframes, 1 for each floor, so we can plot it easily
    return {floor: df.filter(pl.col("floor") == floor) for floor in floors}


def brightness(r, g, b) -> int:
    """Calculate brightness"""
    return (r * 299 + g * 587 + b * 114) / 1000


def color_difference(color1, color2) -> int:
    """Calculate color difference"""
    return sum(abs(c1 - c2) for c1, c2 in zip(color1, color2))


def determine_colors(
    temp: int, interpolator: Interpolator = interpolator
) -> Tuple[str, str]:
    """Sets the background and foreground color according to temperature"""
    tmin, tmax = (
        18 if temp > 18 else temp,
        # Set the minimum value for the color scale
        25 if temp < 25 else temp,
    )  # Set the maximum value for the color scale

    normalized_value = min(max((temp - tmin) / (tmax - tmin), 0), 1)

    # Map the value to a color using the interpolator
    bg_color = interpolator(normalized_value).to_string(hex=True)

    # Get RGB from the hex
    r_bg, g_bg, b_bg = (
        int(bg_color[1:3], 16),
        int(bg_color[3:5], 16),
        int(bg_color[5:7], 16),
    )

    # Default text colors to use depending on the background
    text_colors = {
        "#FFFFFF": (255, 255, 255),
        "#000000": (0, 0, 0),
    }

    # Check which text color to use based on the W3C algorithm

    # Calculate brightness and color difference for each text color
    bg_brightness = brightness(r_bg, g_bg, b_bg)
    best_fg_color = "#FFFFFF"  # default to white fg_color

    # Check which color is best given the background
    for r_fg, g_fg, b_fg in text_colors.values():
        fg_brightness = brightness(r_fg, g_fg, b_fg)
        brightness_diff = abs(bg_brightness - fg_brightness)
        color_diff = color_difference((r_bg, g_bg, b_bg), (r_fg, g_fg, b_fg))

        # If both brightness and color difference criteria are met, select this text color
        if brightness_diff >= 125 and color_diff >= 500:
            best_fg_color = "#000000"
            break

    return bg_color, best_fg_color


def fix_timezone(dt: datetime) -> datetime:
    """A helper function to set the correct timezone on Shiny input filter"""
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Stockholm"))
