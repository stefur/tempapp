import json
from datetime import datetime
from zoneinfo import ZoneInfo

from duckdb import connect
from requests import get


def get_temps() -> None:
    """Load the server settings and ask the API for temps to update the db"""
    with open("/app/settings.json", "r") as file:
        settings = json.load(file)

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
        url = f"""https://{settings["server"]}/api/states/sensor.{entity}"""

        response = get(url, headers=settings["headers"])
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

    with connect(":memory:") as connection:
        connection.execute("CREATE TABLE temps AS SELECT * FROM '/data/temps.parquet'")
        connection.executemany(
            """INSERT INTO temps (time, floor, temp, hour, date_iso, day, time_trunc)
                        VALUES ($time,
                        $floor,
                        $temp,
                        strftime(datetrunc('hour', CAST($time AS TIMESTAMPTZ)), '%H:%M'),
                        strftime(CAST($time AS TIMESTAMPTZ), '%Y-%m-%d'),
                        datetrunc('day', CAST($time AS TIMESTAMPTZ)),
                        datetrunc('hour', CAST($time AS TIMESTAMPTZ)))""",
            rows,
        )

        connection.execute("COPY temps TO '/data/temps.parquet' (FORMAT PARQUET)")
