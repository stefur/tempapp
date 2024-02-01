#!/bin/bash
docker run --rm -p 8000:8000 --name tempapp -e ARGS="app:app --host 0.0.0.0 --port 8000 --reload" -v ./db/temps.db:/db/temps.db -v ./app:/app --detach tempapp:dev
