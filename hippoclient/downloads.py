from pathlib import Path
from typing import Optional

import httpx
import xxhash
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)


def downloader(
    presigned_url: str,
    output_destination: Path,
    console: Optional[Console] = None,
):
    with httpx.Client() as client:
        with client.stream("GET", presigned_url) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", 0))

            if console:
                progress = Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                )

                task_id = progress.add_task("Downloading", total=total)

            with progress, open(output_destination, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    if console:
                        progress.update(task_id, advance=len(chunk))


def file_info(filename: Path, description: str | None = None) -> dict:
    with open(filename, "rb") as handle:
        return {
            "name": filename.name,
            "size": filename.stat().st_size,
            "checksum": f"xxh64:{xxhash.xxh64(handle.read()).hexdigest()}",
            "description": description,
        }
