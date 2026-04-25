#!/usr/bin/env bash
# Bump the patch/minor/major version in pyproject.toml.
# Usage: ./scripts/bump_version.sh [patch|minor|major]
# Default: patch
set -euo pipefail

PART="${1:-patch}"
PYPROJECT="pyproject.toml"

current=$(grep '^version' "$PYPROJECT" | head -1 | sed 's/version = "\(.*\)"/\1/')
IFS='.' read -r major minor patch <<< "$current"

case "$PART" in
  major) major=$((major + 1)); minor=0; patch=0 ;;
  minor) minor=$((minor + 1)); patch=0 ;;
  patch) patch=$((patch + 1)) ;;
  *)     echo "usage: $0 [patch|minor|major]"; exit 1 ;;
esac

new="$major.$minor.$patch"

sed -i "s/^version = \"$current\"/version = \"$new\"/" "$PYPROJECT"

echo "$new"
