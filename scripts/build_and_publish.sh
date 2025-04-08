#!/bin/bash

set -eu

nix build .#packages.x86_64-linux.image -o x86_64
nix build .#packages.aarch64-linux.image -o arm64

REPOSITORY="docker://ghcr.io/stefur/tempapp"
USERNAME="stefur"

skopeo --insecure-policy copy --dest-creds="$USERNAME:$REGISTRY_ACCESS_TOKEN" "docker-archive:./x86_64" "$REPOSITORY"
skopeo --insecure-policy copy --dest-creds="$USERNAME:$REGISTRY_ACCESS_TOKEN" "docker-archive:./arm64" "$REPOSITORY"
