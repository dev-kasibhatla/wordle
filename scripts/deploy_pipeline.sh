#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <user@host> <base_url> [remote_dir] [host_port]"
  exit 1
fi

REMOTE="$1"
BASE_URL="$2"
REMOTE_DIR="${3:-/opt/wordle}"
HOST_PORT="${4:-8000}"
SCRIPTS="$(dirname "$0")"

bash "$SCRIPTS/predeploy_check.sh"
bash "$SCRIPTS/upload_image.sh" "$REMOTE" "$REMOTE_DIR"
bash "$SCRIPTS/deploy_remote.sh" "$REMOTE" "$REMOTE_DIR" "$HOST_PORT"
bash "$SCRIPTS/postdeploy_validate.sh" "$BASE_URL"