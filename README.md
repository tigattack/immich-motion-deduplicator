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

## Android Live Photos

Some Android phones export live photos as two separate files: a still image and a standalone `.mp4` motion video. After import, Immich stores the motion video as a `livePhotoVideoId` asset linked to the image. If the standalone `.mp4` was also imported separately, it appears as a duplicate video asset.

`scan-live` finds these duplicates by:
1. Fetching all live photo image assets from the Immich API to collect their associated motion video IDs
2. Fetching all video assets and excluding those already linked as motion videos
3. Pairing remaining standalone videos with live photo motion videos by capture time (±`--time-window` seconds)
4. Fingerprinting matched pairs: SHA256 exact match first, then ffmpeg + perceptual hash fallback

### New Environment Variables

| Variable | Description |
|---|---|
| `LIVE_CANDIDATES_CSV` | Output path for `scan-live` results; used as input to `delete` in the `all-live` flow |
| `IMMICH_SERVER_PATH_PREFIX` | Server-side path prefix to strip from Immich `originalPath` before resolving against `IMMICH_ROOT_DIR`. Example: `/usr/src/app/upload` |

### Commands

```bash
# Scan only — writes matches to LIVE_CANDIDATES_CSV
immich-motion-deduplicator scan-live

# Full workflow — scan then delete (dry-run preview)
immich-motion-deduplicator all-live --dry-run

# Full workflow — scan then delete
immich-motion-deduplicator all-live
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--time-window N` | `60` | Seconds around capture time to search for matching live photo |
| `--fps F` | `5.0` | Frame sampling rate for perceptual hashing |
| `--hamming-threshold N` | `8` | Maximum average Hamming distance to count as a perceptual match |
| `--skip-perceptual` | off | Skip ffmpeg/imagehash; use SHA256 exact match only |
| `--progress-every N` | `100` | Print progress every N candidates checked (0 = disable) |

### Requirements

- `ffmpeg` must be on `PATH` for perceptual hashing (use `--skip-perceptual` to disable)
- `imagehash` and `Pillow` Python packages (included in package dependencies)

## Docker

Docker is useful as an optional distribution path for one-off runs and automation. The repository includes a `Dockerfile` and `docker-compose.example.yml`.

To run with Docker:

```bash
docker run --rm \
  --env-file .env \
  -v /path/to/your/immich/data:/data:ro \
  -v "$PWD":/work \
  -w /work \
  ghcr.io/itswavs/immich-motion-deduplicator:latest \
  all --dry-run
```

Mount the entire Immich data directory (the parent of `library`, `upload`, `encoded-video`, etc.), not just the `library` subdirectory. Immich stores assets across multiple subdirectories and `scan-live` needs access to all of them.

Set in `.env`:

```env
IMMICH_ROOT_DIR=/data
IMMICH_SERVER_PATH_PREFIX=/data
```

`ffmpeg` is included in the Docker image. To use `--skip-perceptual` (SHA256 only, no ffmpeg), no extra setup is needed.

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
