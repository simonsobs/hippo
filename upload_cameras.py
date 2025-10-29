from datetime import datetime, timezone
from pathlib import Path

from henry import Henry
from hippometa import CameraMetadata

base = Path("/Users/borrow-adm")
dt = 17502

sources = {
    slug: {
        "path": base / f"{slug}_{dt}.mp4",
        "description": "Timelapse",
    }
    for slug in CameraMetadata.valid_slugs
}

client = Henry()

product = client.new_product(
    name=f"Security Cameras ({dt})",
    description="Security camera timelapses",
    sources=sources,
    metadata=CameraMetadata(date=datetime.now(timezone.utc)),
)

client.push(product)
