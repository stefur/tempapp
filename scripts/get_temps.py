import json
from datetime import datetime

import duckdb
from requests import get

with open("scripts/settings.json", "r") as file:
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

time = datetime.now()

for entity in entities.keys():
    url = f"""http://{settings["server"]["ip"]}:{settings["server"]["port"]}/api/states/sensor.{entity}"""

    response = get(url, headers=settings["headers"])
    json_data = json.loads(response.text)
    entities[entity].update({"floor": json_data["attributes"]["friendly_name"]})
    entities[entity].update({"temp": float(json_data["state"])})

con = duckdb.connect("db/temps.db")

for sensor, data in entities.items():
    con.sql(
        f"""INSERT INTO temps (time, floor, temp)
                VALUES ('{time}', 
                '{data["floor"]}', 
                '{data["temp"]}')"""
    )

con.close()
