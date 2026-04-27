#!/usr/bin/env bash
set -euo pipefail

CURRENT_VERSION=""
SINCE_TAG=""
OUTPUT_FILE="static/changelog.html"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      CURRENT_VERSION="${2:-}"
      shift 2
      ;;
    --since-tag)
      SINCE_TAG="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="${2:-}"
      shift 2
      ;;
    *)
      echo "error: unknown argument: $1"
      exit 1
      ;;
  esac
done

if [[ -z "$CURRENT_VERSION" ]]; then
  CURRENT_VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
fi

if [[ -z "$SINCE_TAG" ]]; then
  SINCE_TAG=$(git tag -l 'v*' --sort=-v:refname | grep -Fxv "v$CURRENT_VERSION" | head -1 || true)
fi

html_escape() {
  local input_value="$1"
  input_value="${input_value//&/&amp;}"
  input_value="${input_value//</&lt;}"
  input_value="${input_value//>/&gt;}"
  input_value="${input_value//\"/&quot;}"
  input_value="${input_value//\'/&#39;}"
  printf '%s' "$input_value"
}

render_commit_list() {
  local range="$1"
  local commits
  commits=$(git log "$range" --oneline --reverse 2>/dev/null || true)

  if [[ -z "$commits" ]]; then
    printf '%s\n' '      <article class="timeline-item"><p class="timeline-copy">No commits recorded for this release.</p></article>'
    return
  fi

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    local commit_hash commit_msg escaped_hash escaped_msg
    commit_hash=$(printf '%s' "$line" | awk '{print $1}')
    commit_msg=$(printf '%s' "$line" | sed 's/^[^ ]* //')
    escaped_hash=$(html_escape "$commit_hash")
    escaped_msg=$(html_escape "$commit_msg")

    cat <<EOF
      <article class="timeline-item">
        <p class="timeline-meta">$escaped_hash</p>
        <h2 class="timeline-title">$escaped_msg</h2>
      </article>
EOF
  done <<< "$commits"
}

render_release_section() {
  local title="$1"
  local range="$2"

  cat <<EOF
    <section class="page-grid">
      <article class="page-card">
        <h2>$title</h2>
        <p class="page-copy">$(git rev-list --count "$range" 2>/dev/null || echo 0) commits shipped in this slice.</p>
      </article>
    </section>
    <section class="timeline-list">
EOF

  render_commit_list "$range"

  cat <<'EOF'
    </section>
EOF
}

mapfile -t TAGS < <(git tag -l 'v*' --sort=-v:refname)

CURRENT_RANGE="HEAD"
if [[ -n "$SINCE_TAG" ]] && git rev-parse --verify --quiet "$SINCE_TAG" >/dev/null; then
  CURRENT_RANGE="$SINCE_TAG..HEAD"
fi

cat > "$OUTPUT_FILE" <<EOF
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Wordle Changelog</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/assets/app.css" />
</head>
<body>
  <main class="page-shell">
    <header class="page-header">
      <div class="logo">WORDLE</div>
      <a class="back-link" href="/">Back to app</a>
    </header>

    <section class="page-hero">
      <p class="page-kicker">Release Notes</p>
      <h1 class="page-title">Changelog</h1>
      <p class="page-subtitle">Generated from git history for each release and deploy.</p>
    </section>
EOF

render_release_section "v${CURRENT_VERSION}" "$CURRENT_RANGE" >> "$OUTPUT_FILE"

if [[ ${#TAGS[@]} -gt 0 ]]; then
  for index in "${!TAGS[@]}"; do
    tag="${TAGS[$index]}"
    if [[ "$tag" == "v${CURRENT_VERSION}" ]]; then
      continue
    fi

    older_tag="${TAGS[$((index + 1))]:-}"
    if [[ -n "$older_tag" ]]; then
      range="$older_tag..$tag"
    else
      range="$tag"
    fi

    render_release_section "$tag" "$range" >> "$OUTPUT_FILE"
  done
fi

cat >> "$OUTPUT_FILE" <<'EOF'
    <footer class="site-footer" data-site-footer></footer>
  </main>

  <script type="module" src="/assets/site.js"></script>
</body>
</html>
EOF

echo "Generated changelog at $OUTPUT_FILE"