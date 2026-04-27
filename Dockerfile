# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

WORKDIR /build

# Copy only what's needed to resolve deps first (layer cache)
COPY pyproject.toml ./
COPY src/ ./src/

# Install deps + the package itself (non-editable) into /build/.venv
RUN uv venv /build/.venv && \
    UV_PROJECT_ENVIRONMENT=/build/.venv uv pip install . --python /build/.venv/bin/python

# ── Stage 2: minimal runtime ──────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ARG VERSION=dev
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="Wordle" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/kasibhatla/wordle" \
      org.opencontainers.image.licenses="MIT"

# Non-root user
RUN addgroup --system wordle && adduser --system --ingroup wordle wordle

WORKDIR /app

# Copy venv from builder (no pip/uv in runtime)
COPY --from=builder /build/.venv /app/.venv
# Copy runtime assets
COPY static/ ./static/
COPY data/   ./data/


# Activate venv; WORDLE_ROOT tells constants.py where data/ lives
ENV PATH="/app/.venv/bin:$PATH" \
    WORDLE_ROOT="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Own files
RUN chown -R wordle:wordle /app

USER wordle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "uvicorn", "wordle.api.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
