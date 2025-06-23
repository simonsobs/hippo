"""
Metadata for site camera timelapse videos.
"""

from datetime import datetime
from typing import ClassVar, Literal

from .base import BaseMetadata


class CameraMetadata(BaseMetadata):
    """
    Metadata for site camera timelapse videos.
    """

    metadata_type: Literal["camera"] = "camera"

    date: datetime
    "The date of the camera videos"

    valid_slugs: ClassVar[set[str]] = {
        "act_highbay",
        "busbar",
        "c1",
        "c2",
        "c2_front",
        "c3",
        "c3_front",
        "c4",
        "c4_front",
        "c5",
        "highbay_back",
        "highbay_cargo",
        "lat_g5",
        "lat_highbay",
        "lat_shutter",
        "latr",
        "mirror1_latr",
        "mirror2_latr",
        "pumphouse",
        "pumphouse_inside",
        "satp1",
        "satp2",
        "satp3",
        "site_entrance",
    }
