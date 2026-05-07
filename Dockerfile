FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update &&\
    apt-get install -y --no-install-recommends ffmpeg

WORKDIR /app

COPY LICENSE README.md pyproject.toml ./
COPY immich_motion_deduplicator ./immich_motion_deduplicator

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install .

ENTRYPOINT ["immich-motion-deduplicator"]
