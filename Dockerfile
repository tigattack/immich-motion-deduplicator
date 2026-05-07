FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY LICENSE README.md pyproject.toml ./
COPY immich_motion_deduplicator ./immich_motion_deduplicator

RUN pip install --no-cache-dir .

ENTRYPOINT ["immich-motion-deduplicator"]
