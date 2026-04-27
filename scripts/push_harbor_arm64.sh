#!/usr/bin/env bash
# Build and push arm64 image variants to Harbor
# Requires: .env with Harbor credentials
# Usage: ./scripts/push_harbor_arm64.sh

set -euo pipefail

required=(HARBOR_REGISTRY HARBOR_PROJECT HARBOR_USERNAME HARBOR_PASSWORD)
for var in "${required[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "error: $var is not set"
    echo "required env vars: ${required[*]}"
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required"
  exit 1
fi

VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
REGISTRY_URL="$HARBOR_REGISTRY/$HARBOR_PROJECT"
IMAGE_NAME="wordle"
PLATFORM="linux/arm64"

# Architecture-specific tags for easy Harbor segregation/filtering
TAG_VERSION="$REGISTRY_URL/$IMAGE_NAME:${VERSION}-arm64"
TAG_LATEST="$REGISTRY_URL/$IMAGE_NAME:latest-arm64"
TAG_SHA="$REGISTRY_URL/$IMAGE_NAME:sha-${SHORT_SHA}-arm64"

echo "Harbor arm64 publish setup:"
echo "  Registry: $HARBOR_REGISTRY"
echo "  Project: $HARBOR_PROJECT"
echo "  Platform: $PLATFORM"
echo "  Tags:"
echo "    - $TAG_VERSION"
echo "    - $TAG_LATEST"
echo "    - $TAG_SHA"
echo

echo "Testing Harbor authentication..."
if ! echo "$HARBOR_PASSWORD" | docker login "$HARBOR_REGISTRY" --username "$HARBOR_USERNAME" --password-stdin &>/dev/null; then
  echo "❌ Login failed"
  echo "  Verify robot account credentials and push permissions for '$HARBOR_PROJECT'"
  exit 1
fi
echo "✓ Authenticated to Harbor"

# Create/use a dedicated buildx builder for cross-platform consistency
BUILDER_NAME="wordle-buildx"
if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
  docker buildx create --name "$BUILDER_NAME" --use >/dev/null
else
  docker buildx use "$BUILDER_NAME"
fi

docker buildx inspect --bootstrap >/dev/null

echo
echo "Building and pushing arm64 image..."
docker buildx build \
  --pull \
  --platform "$PLATFORM" \
  --build-arg VERSION="$VERSION" \
  --build-arg VCS_REF="$SHORT_SHA" \
  --build-arg BUILD_DATE="$BUILD_DATE" \
  --label "org.opencontainers.image.architecture=arm64" \
  --label "io.wordle.arch=arm64" \
  --tag "$TAG_VERSION" \
  --tag "$TAG_LATEST" \
  --tag "$TAG_SHA" \
  --push \
  .

echo
echo "✓ Successfully pushed arm64 image variants"
echo "  Version tag: $TAG_VERSION"
echo "  Latest tag:  $TAG_LATEST"
echo "  SHA tag:     $TAG_SHA"
