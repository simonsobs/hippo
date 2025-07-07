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
        "map", # A regular, source and sky, and whatever else, map
        "source_only", # A source-only map
        "source_free", # A source-free map
        "ivar", # Inverse-variance map
        "xlink", # Cross-linking map
        "mask", # Sky apodization mask
        "hits", # Hit map (pixels that were hit by detectors)
        "weights", # A weights map (?)
        "time", # A time map, showing when individual detectors were hit
        "file_names", # The file names of atomic maps or TODs used to create this map
        "data", # Generic
    }

    pixelisation: Literal["healpix", "cartesian"]

    telescope: str | None = None
    "Telescope that this map is created from"
    instrument: str | None = None
    "The instrument on that telescope that was used for this map"
    release: str | None = None
    "The data release this map is part of"
    season: str | None = None
    "The observing season(s) that are included in the map"
    patch: str | None = None
    "Sky patch observed in this map"
    frequency: str | None = None
    "On-sky frequency of the map (GHz), stored as a string to avoid round-off etc."
    polarization_convention: str | None = None
    "Polarization convention of the map (e.g. IAU)"

    split: str | int | None = None
    "The split that this map is of, or 'coadd' if it is a full map"

    tags: list[str] | None = None
    "Tags used to categorizet his map, including scan split strategies and so forth"

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
                polarization_convention=metadata.get("POLCCONV", ""),
                tags=metadata.get("ACTTAGS", "").split(",")
                if metadata.get("ACTTAGS")
                else None,
            )
