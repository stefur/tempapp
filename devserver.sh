#!/bin/bash
podman run --rm -p 8000:8000 -v ./data:/data -v .:/app -v /app/.venv --name tempapp $(podman build -q -t tempapp:dev .) dev
