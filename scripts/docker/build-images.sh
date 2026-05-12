#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${REGISTRY:-ghcr.io/REVIEW_OWNER}"
TAG="${TAG:-latest}"

docker build -f docker/Dockerfile.web -t "$REGISTRY/argus-web:$TAG" .
docker build -f docker/Dockerfile.scanner -t "$REGISTRY/argus-scanner:$TAG" .
docker push "$REGISTRY/argus-web:$TAG"
docker push "$REGISTRY/argus-scanner:$TAG"
echo "OK: imagenes publicadas en $REGISTRY"
