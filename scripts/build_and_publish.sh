#!/bin/bash

set -eu

TAG=$(git rev-parse --short "$GITHUB_SHA")
REPOSITORY="ghcr.io/stefur/tempapp"
USERNAME="stefur"

nix build .#packages.x86_64-linux.image -o x86_64
nix build .#packages.aarch64-linux.image -o arm64

docker load < x86_64
docker load < arm64

docker push $REPOSITORY:$TAG-amd64
docker push $REPOSITORY:$TAG-arm64

docker manifest create $REPOSITORY:$TAG $REPOSITORY:$TAG-amd64 $REPOSITORY:$TAG-arm64
docker manifest annotate $REPOSITORY:$TAG $REPOSITORY:$TAG-amd64 --arch amd64
docker manifest annotate $REPOSITORY:$TAG $REPOSITORY:$TAG-arm64 --arch arm64

docker manifest push $REPOSITORY:$TAG