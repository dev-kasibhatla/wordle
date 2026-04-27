#!/usr/bin/env bash
set -euo pipefail

# Skip @pytest.mark.slow tests by default; they run separately via run_slow_tests.sh
uv run pytest -m "not slow"