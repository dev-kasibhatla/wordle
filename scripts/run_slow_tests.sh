#!/usr/bin/env bash
set -euo pipefail

# Run only the @pytest.mark.slow tests (full batch evaluations)
uv run pytest -m slow -v
