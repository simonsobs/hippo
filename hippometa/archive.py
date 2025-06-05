"""
An archive, for instance a zip or tar file, that contains
an arbritrary collection of files (e.g. model weights).
"""

from typing import Literal

from hippometa.base import BaseMetadata


class ArchiveMetadata(BaseMetadata):
    """
    Metadata for an archive object.
    """

    metadata_type: Literal["archive"] = "archive"

    # The type of archive, e.g. zip, tar, etc.
    archive_type: str
