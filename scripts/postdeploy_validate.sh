#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <base_url>"
  exit 1
fi

BASE_URL="${1%/}"

curl --fail --silent --show-error "$BASE_URL/health" >/dev/null
curl --fail --silent --show-error "$BASE_URL/api/version" >/dev/null
curl --fail --silent --show-error "$BASE_URL/" >/dev/null

echo "Post-deploy validation passed for $BASE_URL"