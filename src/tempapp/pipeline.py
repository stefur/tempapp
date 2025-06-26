import json
from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl
from requests import get

from .utils import SETTINGS


def get_temps() -> None:
    """Ask the API for temps to update the db"""
    # Sensors
    entities = {
        # 1
        "temperature_10": {"floor": "", "temp": int},
        # 2
        "temperature_13": {"floor": "", "temp": int},
        # 3
        "temperature_16": {"floor": "", "temp": int},
    }

    time = datetime.now(tz=ZoneInfo("Europe/Stockholm"))

    for entity in entities.keys():
        url = f"""https://{SETTINGS["server"]}/api/states/sensor.{entity}"""

        response = get(url, headers=SETTINGS["headers"])
        json_data = json.loads(response.text)
        entities[entity].update({"floor": json_data["attributes"]["friendly_name"]})
        entities[entity].update({"temp": round(float(json_data["state"]), 1)})

    rows = [
        {
            "time": time,
            "floor": data["floor"],
            "temp": data["temp"],
        }
        for data in entities.values()
    ]

    (
        pl.DataFrame(rows)
        .with_columns(
            hour=pl.col("time").dt.truncate("1h").dt.strftime("%H:%M"),
            date_iso=pl.col("time").dt.strftime("%Y-%m-%d"),
            day=pl.col("time").dt.truncate("1d"),
            time_trunc=pl.col("time").dt.truncate("1h"),
        )
        .write_parquet(SETTINGS["data"])
    )
