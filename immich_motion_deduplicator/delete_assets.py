import csv
import math
import time
from typing import Optional

import requests
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from .config import get_immich_api_url, load_dotenv, require_env
from .ui import console, print_summary


BATCH_SIZE = 25
DRY_RUN = True
SLEEP_BETWEEN_BATCHES = 3.5


def chunk_list(values, size):
    """Split a list into sublists of size 'size'."""
    for index in range(0, len(values), size):
        yield values[index:index + size]


def delete_batch(ids, api_url, headers):
    """Delete a batch of assets via the DELETE /assets API."""
    response = requests.delete(
        f"{api_url}/assets",
        json={"ids": ids, "force": False},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "message": "No content returned"}


def run(batch_size=BATCH_SIZE, dry_run=DRY_RUN, input_csv: Optional[str] = None):
    load_dotenv()
    api_url = get_immich_api_url()
    api_key = require_env("IMMICH_API_KEY")
    if input_csv is None:
        input_csv = require_env("MOTION_CANDIDATES_WITH_IDS_CSV")
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    asset_ids = []
    with open(input_csv, newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            if row.get("asset_id"):
                asset_ids.append(row["asset_id"])

    console.print(f"{len(asset_ids)} assets ready for deletion.")

    if not asset_ids:
        print_summary("Deletion complete", [("Assets deleted", 0), ("Failed batches", 0)])
        return 0

    if dry_run:
        print_summary(
            "Dry run",
            [
                ("Assets queued", len(asset_ids)),
                ("Batch size", batch_size),
                ("Deletion executed", "no"),
            ],
        )
        return len(asset_ids)

    total_batches = math.ceil(len(asset_ids) / batch_size)
    deleted_assets = 0
    failed_batches = 0

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        task_id = progress.add_task("Deleting assets", total=total_batches)

        for batch_num, batch in enumerate(chunk_list(asset_ids, batch_size), start=1):
            progress.update(task_id, description=f"Deleting batch {batch_num}/{total_batches}")
            try:
                delete_batch(batch, api_url, headers)
                deleted_assets += len(batch)
            except requests.RequestException as exc:
                failed_batches += 1
                console.log(f"Batch {batch_num} failed: {exc}")

            progress.advance(task_id)

            if batch_num < total_batches:
                time.sleep(SLEEP_BETWEEN_BATCHES)

    print_summary(
        "Deletion complete",
        [
            ("Assets requested", len(asset_ids)),
            ("Assets deleted", deleted_assets),
            ("Failed batches", failed_batches),
            ("Batch size", batch_size),
        ],
    )
    return deleted_assets


def main():
    run()


if __name__ == "__main__":
    main()
