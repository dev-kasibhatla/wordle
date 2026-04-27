#!/usr/bin/env bash
# Full release: bump version, refresh changelog, validate, commit, tag, build Docker, push to Harbor.
# Usage: ./scripts/release.sh [patch|minor|major]
#
# Harbor credentials must be in env (see push_harbor.sh for details).
# Will load .env if present.
set -euo pipefail

PART="${1:-patch}"
SCRIPTS="$(dirname "$0")"

# Load .env if present (never committed)
if [[ -f ".env" ]]; then
  set +u
  set -a
  source .env
  set +a
  set -u
fi

echo "=== Wordle Release ==="
echo

# 1. Bump version
echo "[1/7] Bumping $PART version..."
NEW_VERSION=$(bash "$SCRIPTS/bump_version.sh" "$PART")
echo "New version: $NEW_VERSION"
echo

# 2. Refresh changelog before commit/tag
echo "[2/7] Generating changelog..."
bash "$SCRIPTS/generate_changelog.sh" --version "$NEW_VERSION"
echo "Changelog refreshed"
echo

# 3. Reinstall package so importlib.metadata picks up new version
echo "[3/7] Reinstalling package..."
uv pip install -e . --quiet
echo "Installed wordle==$NEW_VERSION"
echo

# 3.5. Update lockfile after version bump
echo "[3.5/7] Updating lockfile..."
uv lock --quiet
echo "Lockfile updated"
echo

# 4. Validate release candidate
echo "[4/7] Running predeploy checks..."
bash "$SCRIPTS/predeploy_check.sh"
echo

# 5. Commit version bump and tag
echo "[5/7] Committing and tagging..."
git add pyproject.toml static/changelog.html
git commit -m "release: v$NEW_VERSION"
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"
echo "Tagged v$NEW_VERSION"
echo

# 6. Build Docker image
echo "[6/7] Building Docker image..."
bash "$SCRIPTS/build_docker.sh"
echo

# 7. Push to Harbor
echo "[7/7] Pushing to Harbor..."
bash "$SCRIPTS/push_harbor.sh"
echo

# Push git commits and tags
echo "[done] Pushing git..."
git push
git push --tags

echo
echo "Released v$NEW_VERSION"
