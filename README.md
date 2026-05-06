# Immich Motion Deduplicator

`immich-motion-deduplicator` finds MP4 motion-video duplicates created by Google Takeout style exports and removes the standalone video assets from Immich.

It is designed as a one-off CLI tool:
- `scan` finds photo/video pairs with the same basename
- `ids` resolves matching Immich asset IDs through the API
- `delete` removes the matched video assets in batches
- `all` runs the full workflow end-to-end

## Why This Exists

Some exports contain both:
- a photo file such as `.jpg` or `.heic`
- a separate `.mp4` file containing only the motion portion

After import, Immich can show both as separate assets. This tool helps clean up the duplicate motion videos while keeping the still image.

## Requirements

- Python 3.9+
- network access to your Immich API
- an Immich API key with permission to delete assets

## Install

### pipx

```bash
pipx install immich-motion-deduplicator
```

### uv

```bash
uv tool install immich-motion-deduplicator
```

### pip

```bash
pip install immich-motion-deduplicator
```

### From Source

```bash
git clone https://github.com/itsWavs/Immich-motion-deduplicator.git
cd Immich-motion-deduplicator
pip install .
```

## Configuration

The app reads configuration from environment variables. If a `.env` file exists in the current working directory, it is loaded automatically.

Copy `.env.example` to `.env` and fill in your values:

```env
IMMICH_ROOT_DIR=/path/to/your/immich/library
IMMICH_API_URL=http://your-immich-host:2283/api
IMMICH_API_KEY=your_api_key
MOTION_CANDIDATES_CSV=motion_candidates.csv
MOTION_CANDIDATES_WITH_IDS_CSV=motion_candidates_with_ids.csv
```

Notes:
- `IMMICH_API_URL` may include `/api` or omit it
- CSV paths may be relative to the current working directory
- for Docker, `IMMICH_ROOT_DIR` must use the container-mounted path, not the host path

## Usage

Installed command:

```bash
immich-motion-deduplicator scan
immich-motion-deduplicator ids
immich-motion-deduplicator delete
immich-motion-deduplicator all --dry-run
immich-motion-deduplicator all
```

Module form:

```bash
python -m immich_motion_deduplicator scan
python -m immich_motion_deduplicator ids
python -m immich_motion_deduplicator delete
python -m immich_motion_deduplicator all --dry-run
python -m immich_motion_deduplicator all
```

Behavior:
- `delete` is safe by default and only deletes when you add `--execute`
- `all` deletes by default so it works cleanly in automation
- `all --dry-run` previews the full workflow without deleting anything

Recommended flow:

```bash
immich-motion-deduplicator all --dry-run
immich-motion-deduplicator all
```

## Docker

Docker is useful as an optional distribution path for one-off runs and automation. The repository includes a `Dockerfile` and `docker-compose.example.yml`.

To run with Docker:

```bash
docker run --rm \
  --env-file .env \
  -v /path/to/your/immich/library:/library:ro \
  -v "$PWD":/work \
  -w /work \
  ghcr.io/itswavs/immich-motion-deduplicator:latest \
  all --dry-run
```

When running in Docker, set `IMMICH_ROOT_DIR=/library` inside `.env` or pass it explicitly as an environment variable.

You can optionally also build your own copy of the image:

```bash
docker build -t immich-motion-deduplicator .
```

## Development

Install the project with test dependencies:

```bash
pip install -e ".[dev]"
pytest
python -m build
```

## Safety

- review the dry-run output before deleting
- keep backups of your library and database before bulk deletion tools
- this tool deletes Immich assets through the API and does not modify files directly on disk
