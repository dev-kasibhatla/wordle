#!/usr/bin/env bash
# Build the Wordle Docker image.
# Usage: ./scripts/build_docker.sh [IMAGE_NAME] [OUTPUT_TAR]
# Default image name: wordle
set -euo pipefail

IMAGE_NAME="${1:-wordle}"
OUTPUT_TAR="${2:-dev/${IMAGE_NAME}.tar}"
VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Building $IMAGE_NAME:$VERSION (sha=$SHORT_SHA)"

mkdir -p "$(dirname "$OUTPUT_TAR")"

docker build \
  --pull \
  --build-arg VERSION="$VERSION" \
  --build-arg VCS_REF="$SHORT_SHA" \
  --build-arg BUILD_DATE="$BUILD_DATE" \
  --tag "$IMAGE_NAME:$VERSION" \
  --tag "$IMAGE_NAME:latest" \
  .

echo "Built: $IMAGE_NAME:$VERSION"
echo "Built: $IMAGE_NAME:latest"

docker image inspect "$IMAGE_NAME:latest" --format 'image size: {{.Size}} bytes'
docker save "$IMAGE_NAME:latest" > "$OUTPUT_TAR"
echo "Exported: $OUTPUT_TAR"
