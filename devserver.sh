#!/bin/bash
uv run -- uvicorn tempapp.app:app --host 0.0.0.0 --port 8000 --reload