import json
import os
from datetime import datetime
from typing import Any, Tuple
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
import polars as pl
from matplotlib import colormaps, colors
from polars import DataFrame


def load_settings() -> dict:
    settings_path = os.environ.get("APP_SETTINGS", "./settings.json")
    with open(settings_path) as f:
        settings = json.load(f)
    return settings


SETTINGS = load_settings()


def dot_to_comma(num: float) -> str:
    """Take a float and turn it into a string with a comma for decimal"""
    return str(num).replace(".", ",")


def load_data() -> DataFrame:
    """Loads data for use in the app"""
    return pl.read_parquet(SETTINGS["data"]).with_columns(
        [
            pl.col("time_trunc")
            .dt.replace_time_zone("UTC")
            .dt.convert_time_zone("Europe/Stockholm"),
            pl.col("time")
            .dt.replace_time_zone("UTC")
            .dt.convert_time_zone("Europe/Stockholm"),
        ]
    )


def set_plotly_config(
    fig: go.FigureWidget, **kwargs: dict[str, Any]
) -> go.FigureWidget:
    """Apply default config options as well as any optionals"""
    # This is a workaround:
    # https://github.com/plotly/plotly.py/issues/1074#issuecomment-1471486307
    # https://github.com/posit-dev/py-shiny/issues/944

    config_defaults = {
        "displayModeBar": False,
        "scrollZoom": False,
        "displayLogo": False,
        "editable": False,
        "locale": "sv",
    }
    config_defaults.update(kwargs)
    fig._config = fig._config | config_defaults

    return fig


def add_threshold_lines(plt: go.FigureWidget, xmin: Any, xmax: Any) -> go.FigureWidget:
    """Add two horizontal lines to as temperature thresholds"""

    return plt.add_shape(
        type="line",
        x0=xmin,
        x1=xmax,
        y0=24,
        y1=24,
        line=dict(color="Red", width=1, dash="dash"),
    ).add_shape(
        type="line",
        x0=xmin,
        x1=xmax,
        y0=21,
        y1=21,
        line=dict(color="Blue", width=1, dash="dash"),
    )


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


def determine_colors(temp: int) -> Tuple[str, str]:
    """Sets the background and foreground color according to temperature"""
    tmin, tmax = (
        18 if temp > 18 else temp,
        # Set the minimum value for the color scale
        25 if temp < 25 else temp,
    )  # Set the maximum value for the color scale

    # Map the value to a color using interpolate
    norm = colors.Normalize(vmin=tmin, vmax=tmax)

    cmap = colormaps["RdYlBu_r"]

    bg_color = colors.to_hex(cmap(norm(temp)))

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
