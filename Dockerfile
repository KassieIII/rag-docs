# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13

# ---- builder ----
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app

# Use PyTorch CPU-only wheel index — saves ~2 GB vs default CUDA build.
# We do all embedding/rerank on CPU (bge-small + cross-encoder MiniLM).
RUN pip install --upgrade pip \
 && pip install --prefix /install \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      .

# ---- runtime ----
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/models

RUN useradd --system --uid 1001 --create-home --home /home/app app \
 && mkdir -p /models /app \
 && chown -R app:app /models /app

COPY --from=builder /install /usr/local
COPY --chown=app:app app /app/app
COPY --chown=app:app alembic /app/alembic
COPY --chown=app:app alembic.ini /app/alembic.ini

WORKDIR /app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
