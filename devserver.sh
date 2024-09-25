#!/bin/bash
docker build -t tempapp:dev .
docker run --rm -p 8000:8000 -v ./db/temps.db:/data/temps.db --name tempapp tempapp:dev
