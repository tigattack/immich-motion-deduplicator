import bisect
import csv
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .config import get_immich_api_url, load_dotenv, require_directory_env, require_env, resolve_server_path
from .fingerprint import sha256_file, videos_match
from .immich_api import get_asset, search_assets
from .ui import console, error_console, print_summary


CSV_FIELDNAMES = [
    "asset_id",
    "live_photo_asset_id",
    "live_photo_video_asset_id",
    "match_method",
    "similarity_score",
    "video_path",
]


def _parse_local_datetime(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    # Python 3.9 fromisoformat does not accept "Z" as a UTC offset designator
    normalized = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).replace(tzinfo=None)
    except ValueError:
        return None


def run(
    time_window: int = 60,
    fps: float = 5.0,
    hamming_threshold: int = 8,
    skip_perceptual: bool = False,
    progress_every: int = 100,
) -> int:
    load_dotenv()
    api_url = get_immich_api_url()
    api_key = require_env("IMMICH_API_KEY")
    output_csv = require_env("LIVE_CANDIDATES_CSV")
    server_prefix = require_env("IMMICH_SERVER_PATH_PREFIX")
    local_root = require_directory_env("IMMICH_ROOT_DIR")

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    console.print("Fetching live photos from Immich API...")
    live_photos: List[Dict] = []
    live_photo_video_ids: set = set()

    for asset in search_assets(api_url, headers, {"type": "IMAGE", "isMotion": True}):
        live_photo_video_id = asset.get("livePhotoVideoId")
        live_photos.append({
            "id": asset["id"],
            "livePhotoVideoId": live_photo_video_id,
            "localDateTime": asset.get("localDateTime", ""),
        })
        if live_photo_video_id:
            live_photo_video_ids.add(live_photo_video_id)

    console.print(
        f"Found [bold]{len(live_photos)}[/bold] live photos, "
        f"[bold]{len(live_photo_video_ids)}[/bold] associated motion video IDs."
    )

    console.print("Fetching all video assets from Immich API...")
    video_assets_by_id: Dict[str, dict] = {}

    for asset in search_assets(api_url, headers, {"type": "VIDEO"}):
        video_assets_by_id[asset["id"]] = asset

    missing_motion_ids = live_photo_video_ids - video_assets_by_id.keys()
    if missing_motion_ids:
        console.print(
            f"Fetching [bold]{len(missing_motion_ids)}[/bold] motion video assets not returned by search..."
        )
        for motion_id in missing_motion_ids:
            asset = get_asset(api_url, headers, motion_id)
            if asset is not None:
                video_assets_by_id[motion_id] = asset

    standalone_candidates = [
        asset
        for asset_id, asset in video_assets_by_id.items()
        if asset_id not in live_photo_video_ids
    ]

    console.print(
        f"Found [bold]{len(video_assets_by_id)}[/bold] total video assets, "
        f"[bold]{len(standalone_candidates)}[/bold] standalone candidates."
    )

    live_photo_index: List[Tuple[datetime, Dict]] = []
    for lp in live_photos:
        dt = _parse_local_datetime(lp["localDateTime"])
        if dt is not None:
            live_photo_index.append((dt, lp))

    console.print(f"Built time index with [bold]{len(live_photo_index)}[/bold] live photos with parseable timestamps.")

    live_photo_index: List[Tuple[datetime, Dict]] = []
    for lp in live_photos:
        dt = _parse_local_datetime(lp["localDateTime"])
        if dt is not None:
            live_photo_index.append((dt, lp))

    live_photo_index.sort(key=lambda x: x[0])
    live_photo_datetimes: List[datetime] = [entry[0] for entry in live_photo_index]

    results: List[dict] = []
    checked = 0
    skipped_no_dt = 0
    skipped_no_window = 0
    exact_matches = 0
    perceptual_matches = 0

    for asset in standalone_candidates:
        checked += 1

        if progress_every > 0 and checked % progress_every == 0:
            console.log(f"Checked {checked}/{len(standalone_candidates)} candidates, {len(results)} matches so far.")

        standalone_dt = _parse_local_datetime(asset.get("localDateTime", ""))
        if standalone_dt is None:
            skipped_no_dt += 1
            if skipped_no_dt <= 3:
                error_console.print(
                    f"[dim]Debug:[/dim] asset {asset['id']} localDateTime={asset.get('localDateTime')!r} → unparseable"
                )
            continue

        window_start = standalone_dt - timedelta(seconds=time_window)
        window_end = standalone_dt + timedelta(seconds=time_window)

        lo = bisect.bisect_left(live_photo_datetimes, window_start)
        hi = bisect.bisect_right(live_photo_datetimes, window_end)

        if lo >= hi:
            skipped_no_window += 1
            continue

        original_path = asset.get("originalPath")
        if not original_path:
            error_console.print(
                f"[yellow]Warning:[/yellow] asset {asset['id']} missing originalPath, skipping"
            )
            continue

        try:
            standalone_path = resolve_server_path(original_path, server_prefix, local_root)
        except ValueError as exc:
            error_console.print(f"[yellow]Warning:[/yellow] {exc}")
            continue

        best_match: Optional[dict] = None
        match_count = 0

        for _lp_dt, live_photo in live_photo_index[lo:hi]:
            motion_video_id = live_photo.get("livePhotoVideoId")
            if not motion_video_id:
                continue

            motion_asset = video_assets_by_id.get(motion_video_id)
            if motion_asset is None:
                error_console.print(
                    f"[yellow]Warning:[/yellow] motion video asset {motion_video_id} "
                    f"not found in VIDEO assets, skipping"
                )
                continue

            motion_original_path = motion_asset.get("originalPath")
            if not motion_original_path:
                error_console.print(
                    f"[yellow]Warning:[/yellow] motion video asset {motion_video_id} "
                    f"missing originalPath, skipping"
                )
                continue

            try:
                motion_path = resolve_server_path(motion_original_path, server_prefix, local_root)
            except ValueError as exc:
                error_console.print(f"[yellow]Warning:[/yellow] {exc}")
                continue

            is_match = False
            method = "none"
            score = 0.0

            if skip_perceptual:
                try:
                    if sha256_file(standalone_path) == sha256_file(motion_path):
                        is_match = True
                        method = "checksum"
                        score = 1.0
                except OSError:
                    continue
            else:
                try:
                    is_match, method, score = videos_match(
                        standalone_path,
                        motion_path,
                        hamming_threshold=hamming_threshold,
                        fps=fps,
                    )
                except OSError:
                    continue
                except RuntimeError as exc:
                    error_console.print(
                        f"[yellow]Warning:[/yellow] {exc} for {standalone_path}, skipping"
                    )
                    continue

            if not is_match:
                continue

            match_count += 1
            candidate_result = {
                "asset_id": asset["id"],
                "live_photo_asset_id": live_photo["id"],
                "live_photo_video_asset_id": motion_video_id,
                "match_method": method,
                "similarity_score": score,
                "video_path": standalone_path,
            }

            if best_match is None or score > best_match["similarity_score"]:
                best_match = candidate_result

        if match_count > 1 and best_match is not None:
            error_console.print(
                f"[yellow]Warning:[/yellow] standalone video {asset['id']} matched "
                f"{match_count} live photos; keeping best (score={best_match['similarity_score']:.4f})"
            )

        if best_match is not None:
            results.append(best_match)
            if best_match["match_method"] == "checksum":
                exact_matches += 1
            elif best_match["match_method"] == "perceptual":
                perceptual_matches += 1

    console.print(
        f"Loop complete: {checked} checked, "
        f"{skipped_no_dt} skipped (no timestamp), "
        f"{skipped_no_window} skipped (outside time window), "
        f"{len(results)} matched."
    )
    console.print(f"Writing {len(results)} matches to [bold]{output_csv}[/bold]...")
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print_summary(
        "Scan-live complete",
        [
            ("Live photos found", len(live_photos)),
            ("Total video assets", len(video_assets_by_id)),
            ("Standalone candidates checked", checked),
            ("Exact (checksum) matches", exact_matches),
            ("Perceptual matches", perceptual_matches),
            ("Total written to CSV", len(results)),
            ("Output file", output_csv),
        ],
    )

    return len(results)


def main():
    run()


if __name__ == "__main__":
    main()
