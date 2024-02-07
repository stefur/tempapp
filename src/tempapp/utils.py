from datetime import datetime
from typing import Tuple

import duckdb
import matplotlib
import plotly.graph_objects as go  # type: ignore
import polars as pl
from polars import DataFrame


def date_conversion(dates: datetime) -> str:
    """Take the date and return it in correct locale as expected"""
    return dates.strftime("%d %B %Y")


def dot_to_comma(num: float) -> str:
    """Take a float and turn it into a string with a comma for decimal"""
    return str(num).replace(".", ",")


def query_db(query: str) -> DataFrame:
    """Query the database and return a dataframe with the result"""
    # Connect to the db
    con = duckdb.connect("db/temps.db")

    # Query all the data and push it to a polars frame
    data = con.sql(query).pl()

    # Close the connection
    con.close()

    return data


def get_max_date() -> datetime:
    """Get the max date in the database"""

    return (
        query_db("SELECT MAX(time) AS max_date FROM temps")
        .with_columns(
            pl.col("max_date").dt.truncate("1d").alias("max_date"),
        )
        .select(pl.col("max_date"))
        .to_series()
        .to_list()[0]
    )


def set_plotly_config(fig: go.FigureWidget) -> go.FigureWidget:
    """Apply prefered config options"""
    # This is a workaround:
    # https://github.com/plotly/plotly.py/issues/1074#issuecomment-1471486307
    # https://github.com/posit-dev/py-shiny/issues/944

    fig._config = fig._config | {
        "displayModeBar": False,
        "scrollZoom": False,
        "displayLogo": False,
        "editable": False,
        "locale": "sv",
    }
    return fig


def split_floor_data(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Split any df for each floor. Useful for plotting stuff"""
    # The names of each floor in a list
    floors = df.select(pl.col("floor")).unique().to_series().sort().to_list()

    # Produce 3 different dataframes, 1 for each floor, so we can plot it easily
    return {floor: df.filter(pl.col("floor") == floor) for floor in floors}


def determine_bg_color(temp: int) -> str:
    temp_scale = determine_temp_scale(temp)

    # Map the value to a color using interpolate
    norm = matplotlib.colors.Normalize(vmin=temp_scale[0], vmax=temp_scale[1])

    cmap = matplotlib.colormaps["RdYlBu_r"]

    mapped_color = matplotlib.colors.to_hex(cmap(norm(temp)))

    return mapped_color


def determine_temp_scale(temp: int) -> Tuple[int, int]:
    tmin = 18 if temp > 18 else temp  # Set the minimum value for the color scale
    tmax = 25 if temp < 25 else temp  # Set the maximum value for the color scale

    return (tmin, tmax)


def last_reading() -> str:
    """Get the timestamp of the last entry in the database"""
    data = query_db("SELECT * FROM temps WHERE time = (SELECT MAX(time) FROM temps)")

    last_reading = (
        data.select("time").unique().to_series().dt.truncate("1h").to_list()[0]
    )

    return last_reading
