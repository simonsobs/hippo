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
