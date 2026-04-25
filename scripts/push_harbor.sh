#!/usr/bin/env bash
# Push the Wordle Docker image to Harbor.
# Harbor credentials must be supplied as environment variables:
#   HARBOR_REGISTRY, HARBOR_PROJECT, HARBOR_USERNAME, HARBOR_PASSWORD
#
# Usage:
#   HARBOR_REGISTRY=... HARBOR_PROJECT=... HARBOR_USERNAME=... HARBOR_PASSWORD=... \
#     ./scripts/push_harbor.sh
#
# Or source a local .env first (never commit .env):
#   source .env && ./scripts/push_harbor.sh
set -euo pipefail

required=(HARBOR_REGISTRY HARBOR_PROJECT HARBOR_USERNAME HARBOR_PASSWORD)
for var in "${required[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "error: $var is not set"
    echo "required env vars: ${required[*]}"
    exit 1
  fi
done

VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOCAL_IMAGE="wordle:$VERSION"
REGISTRY_PREFIX="$HARBOR_REGISTRY/$HARBOR_PROJECT/wordle"

TAG_VERSION="$REGISTRY_PREFIX:$VERSION"
TAG_LATEST="$REGISTRY_PREFIX:latest"
TAG_SHA="$REGISTRY_PREFIX:sha-$SHORT_SHA"

echo "Harbor push:"
echo "  Registry : $HARBOR_REGISTRY"
echo "  Project  : $HARBOR_PROJECT"
echo "  Version  : $VERSION"
echo "  SHA      : $SHORT_SHA"
echo

echo "Authenticating..."
echo "$HARBOR_PASSWORD" | docker login "$HARBOR_REGISTRY" \
  --username "$HARBOR_USERNAME" \
  --password-stdin
echo "Authenticated."
echo

# Build if local image doesn't already exist
if ! docker image inspect "$LOCAL_IMAGE" &>/dev/null; then
  echo "Local image $LOCAL_IMAGE not found. Building first..."
  bash "$(dirname "$0")/build_docker.sh"
fi

echo "Tagging..."
docker tag "$LOCAL_IMAGE" "$TAG_VERSION"
docker tag "$LOCAL_IMAGE" "$TAG_LATEST"
docker tag "$LOCAL_IMAGE" "$TAG_SHA"

echo "Pushing..."
docker push "$TAG_VERSION"
docker push "$TAG_LATEST"
docker push "$TAG_SHA"

echo
echo "Pushed:"
echo "  $TAG_VERSION"
echo "  $TAG_LATEST"
echo "  $TAG_SHA"

docker logout "$HARBOR_REGISTRY" &>/dev/null || true
