#!/usr/bin/env bash
set -euo pipefail

uv sync --locked
bash "$(dirname "$0")/run_tests.sh"
bash "$(dirname "$0")/build_docker.sh"