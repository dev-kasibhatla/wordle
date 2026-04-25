#!/usr/bin/env bash
# Full release: bump version, reinstall, commit, tag, build Docker, push to Harbor.
# Usage: ./scripts/release.sh [patch|minor|major]
#
# Harbor credentials must be in env (see push_harbor.sh for details).
set -euo pipefail

PART="${1:-patch}"
SCRIPTS="$(dirname "$0")"

echo "=== Wordle Release ==="
echo

# 1. Bump version
echo "[1/5] Bumping $PART version..."
NEW_VERSION=$(bash "$SCRIPTS/bump_version.sh" "$PART")
echo "New version: $NEW_VERSION"
echo

# 2. Reinstall package so importlib.metadata picks up new version
echo "[2/5] Reinstalling package..."
uv pip install -e . --quiet
echo "Installed wordle==$NEW_VERSION"
echo

# 3. Commit version bump and tag
echo "[3/5] Committing and tagging..."
git add pyproject.toml
git commit -m "release: v$NEW_VERSION"
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"
echo "Tagged v$NEW_VERSION"
echo

# 4. Build Docker image
echo "[4/5] Building Docker image..."
bash "$SCRIPTS/build_docker.sh"
echo

# 5. Push to Harbor
echo "[5/5] Pushing to Harbor..."
bash "$SCRIPTS/push_harbor.sh"
echo

# 6. Push git commits and tags
echo "[done] Pushing git..."
git push
git push --tags

echo
echo "Released v$NEW_VERSION"
