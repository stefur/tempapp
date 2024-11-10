#!/bin/bash
podman run --rm -p 8000:8000 -v ./db/temps.db:/data/temps.db -v .:/app -v /app/.venv --name tempapp $(podman build -q -t tempapp:dev .) dev
