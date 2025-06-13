"""
A map set.
"""

from pathlib import Path
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

    @classmethod
    def from_fits(cls, filename: Path) -> "MapSet":
        """
        Load a MapSet from a FITS file.
        """
        from astropy.io import fits

        with fits.open(filename) as hdul:
            metadata = hdul[0].header
            pixelisation = metadata.get("PIXELIS", "healpix").lower()
            if pixelisation not in ["healpix", "cartesian"]:
                # Check if CAR in ctype
                if "CTYPE1" in metadata and any("CAR" in metadata["CTYPE1"].upper()):
                    pixelisation = "cartesian"
                else:
                    raise ValueError(f"Invalid pixelisation: {pixelisation}")

            return cls(
                filename=filename,
                pixelisation=pixelisation,
                telescope=metadata.get("TELESCOP"),
                instrument=metadata.get("INSTRUME"),
                release=metadata.get("RELEASE"),
                season=metadata.get("SEASON"),
                patch=metadata.get("PATCH"),
                frequency=metadata.get("FREQ", "").replace("f", ""),
                polarization_convention=metadata.get("POLCONV", ""),
                tags=metadata.get("ACTTAGS", "").split(",")
                if metadata.get("ACTTAGS")
                else None,
            )
