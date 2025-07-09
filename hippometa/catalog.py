from typing import Literal

from hippometa.base import BaseMetadata


class CatalogMetadata(BaseMetadata):
    """
    A catalog (potentially of resolved sources).
    """

    metadata_type: Literal["catalog"] = "catalog"

    file_type: Literal["csv", "fits", "hdf5", "txt"]
    column_description: dict[str, str] | None = None

    telescope: str | None = None
    instrument: str | None = None
    release: str | None = None
