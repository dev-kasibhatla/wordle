#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <user@host> [remote_dir]"
  exit 1
fi

REMOTE="$1"
REMOTE_DIR="${2:-/opt/wordle}"
IMAGE_TAR="${WORDLE_IMAGE_TAR:-dev/wordle.tar}"

if [[ ! -f "$IMAGE_TAR" ]]; then
  echo "error: image archive not found: $IMAGE_TAR"
  exit 1
fi

ssh "$REMOTE" "mkdir -p '$REMOTE_DIR'"
scp "$IMAGE_TAR" "$REMOTE:$REMOTE_DIR/wordle.tar"