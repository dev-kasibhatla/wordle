#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <user@host> [remote_dir] [host_port]"
  exit 1
fi

REMOTE="$1"
REMOTE_DIR="${2:-/opt/wordle}"
HOST_PORT="${3:-8000}"

ssh "$REMOTE" "REMOTE_DIR='$REMOTE_DIR' HOST_PORT='$HOST_PORT' bash -s" <<'EOF'
set -euo pipefail

ENV_ARGS=()
if [[ -f "$REMOTE_DIR/.env.production" ]]; then
  ENV_ARGS=(--env-file "$REMOTE_DIR/.env.production")
fi

docker load < "$REMOTE_DIR/wordle.tar"
docker stop wordle || true
docker rm wordle || true
docker run -d \
  --name wordle \
  -p "$HOST_PORT:8000" \
  --restart always \
  --read-only \
  --tmpfs /tmp \
  --security-opt no-new-privileges:true \
  "${ENV_ARGS[@]}" \
  wordle:latest
EOF