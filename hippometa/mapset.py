"""
A map set.
"""

from typing import ClassVar, Literal

from hippometa.base import BaseMetadata


class MapSet(BaseMetadata):
    """
    A set of maps corresponding to the same observation. An easy way to package
    up e.g. a coadd mapp and its associated ivar map.
    """

    metadata_type: Literal["mapset"] = "mapset"
    valid_slugs: ClassVar[set[str]] = {
        "coadd",
        "split",
        "source_only",
        "source_only_split",
        "source_free",
        "source_free_split",
        "ivar_coadd",
        "ivar_split",
        "xlink_coadd",
        "xlink_split",
        "mask",
        "data",
    }

    pixelisation: Literal["healpix", "cartesian"]

    telescope: str | None = None
    instrument: str | None = None
    release: str | None = None
    season: str | None = None
    patch: str | None = None
    frequency: str | None = None
    polarization_convention: str | None = None

    tags: list[str] | None = None
