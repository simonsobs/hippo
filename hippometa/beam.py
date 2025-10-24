"""
A beam.
"""

from typing import Literal

from hippometa.base import BaseMetadata


class BeamMetadata(BaseMetadata):
    """
    Metadata for a beam object.
    """

    metadata_type: Literal["beam"] = "beam"

    telescope: str | None = None
    "Telescope that this beam is for"
    instrument: str | None = None
    "Instrument this beam is for (e.g. optics tube)"
    wafer: str | None = None
    "Wafer that this beam is for"
    frequency: str | None = None
    "Frequency that this beam is for"
