import argparse

from .config import require_env
from .ui import error_console, print_stage


def build_parser():
    parser = argparse.ArgumentParser(description="Immich motion deduplicator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan the library for motion duplicates")
    scan_parser.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Print scan progress every N MP4 files, or 0 to disable",
    )

    scan_live_parser = subparsers.add_parser(
        "scan-live",
        help="Scan live photos for motion duplicates",
    )
    scan_live_parser.add_argument("--time-window", type=int, default=60, help="Time window in seconds")
    scan_live_parser.add_argument("--fps", type=float, default=5.0, help="Frame sampling rate")
    scan_live_parser.add_argument(
        "--hamming-threshold",
        type=int,
        default=8,
        help="Maximum Hamming distance for a match",
    )
    scan_live_parser.add_argument(
        "--skip-perceptual",
        action="store_true",
        help="Skip perceptual hashing",
    )
    scan_live_parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print scan progress every N MP4 files, or 0 to disable",
    )

    subparsers.add_parser("ids", help="Resolve Immich asset IDs for scan results")

    delete_parser = subparsers.add_parser("delete", help="Delete matched video assets")
    delete_parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform deletion instead of running in dry-run mode",
    )

    all_parser = subparsers.add_parser(
        "all",
        help="Run scan, ids, then delete matched assets",
    )
    all_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview matched deletions without deleting assets",
    )
    all_parser.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Print scan progress every N MP4 files, or 0 to disable",
    )

    all_live_parser = subparsers.add_parser(
        "all-live",
        help="Scan live photos and delete matched assets",
    )
    all_live_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview matched deletions without deleting assets",
    )
    all_live_parser.add_argument("--time-window", type=int, default=60, help="Time window in seconds")
    all_live_parser.add_argument("--fps", type=float, default=5.0, help="Frame sampling rate")
    all_live_parser.add_argument(
        "--hamming-threshold",
        type=int,
        default=8,
        help="Maximum Hamming distance for a match",
    )
    all_live_parser.add_argument(
        "--skip-perceptual",
        action="store_true",
        help="Skip perceptual hashing",
    )
    all_live_parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print scan progress every N MP4 files, or 0 to disable",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "scan":
            from . import scan_library
            scan_library.run(progress_every=args.progress_every)
            return

        if args.command == "scan-live":
            from . import scan_live
            scan_live.run(
                time_window=args.time_window,
                fps=args.fps,
                hamming_threshold=args.hamming_threshold,
                skip_perceptual=args.skip_perceptual,
                progress_every=args.progress_every,
            )
            return

        if args.command == "all-live":
            from . import delete_assets, scan_live
            print_stage(1, 2, "Scan live photos")
            scan_live.run(
                time_window=args.time_window,
                fps=args.fps,
                hamming_threshold=args.hamming_threshold,
                skip_perceptual=args.skip_perceptual,
                progress_every=args.progress_every,
            )
            print_stage(2, 2, "Delete matched assets")
            delete_assets.run(dry_run=args.dry_run, input_csv=require_env("LIVE_CANDIDATES_CSV"))
            return

        if args.command == "ids":
            from . import get_ids

            get_ids.main()
            return

        if args.command == "delete":
            from . import delete_assets

            delete_assets.run(dry_run=not args.execute)
            return

        if args.command == "all":
            from . import delete_assets, get_ids, scan_library

            print_stage(1, 3, "Scan library")
            scan_library.run(progress_every=args.progress_every)
            print_stage(2, 3, "Resolve asset IDs")
            get_ids.main()
            print_stage(3, 3, "Delete matched assets")
            delete_assets.run(dry_run=args.dry_run)
            return
    except (RuntimeError, FileNotFoundError, NotADirectoryError) as exc:
        error_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
