# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS runtime_deps

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps for CV/video processing (used by attendance/video flows).
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    build-essential \
    zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/requirements.txt

# "runtime_deps" intentionally does not COPY app code: docker-compose mounts the
# working tree for dev and tests. This keeps rebuilds fast when code changes.

FROM runtime_deps AS test_deps

COPY requirements-dev.txt /app/requirements-dev.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/requirements-dev.txt

FROM runtime_deps AS runtime

COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY app /app/app
COPY scripts /app/scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
