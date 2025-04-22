"""
Populates the simple example server with a bunch of ACT maps.
"""

import os
from pathlib import Path

import astropy.io.fits as fits

from hippoclient import Client
from hippoclient.collections import add as add_to_collection
from hippoclient.collections import create as create_collection
from hippoclient.product import create as create_product
from hippometa import MapSet, MapSetMap

API_KEY = os.getenv("HIPPO_API_KEY")
SERVER_LOCATION = os.getenv("HIPPO_HOST")

if API_KEY is None:
    API_KEY = "TEST_API_KEY"
    SERVER_LOCATION = "http://127.0.0.1:8000"

COLLECTION_NAME = (
    "ACT DR4 Frequency Maps at 98 and 150 GHz presented in Aiola et al. 2020"
)

COLLECTION_DESCRIPTION = """
These FITS files are the maps made with the nighttime 2013(s13) to 2016(s16) data from the ACTPol camera on the ACT telescope at 98(f090) and 150(f150) GHz.

These maps and their properties are described in Aiola et al. (2020) and Choi et al. (2020)

#### Naming and products

The maps are released both as 2- or 4-way independet splits, used to compute the power spectra, and as inverse-variance map-space co-added.

##### Naming convention 

`act_{release}_{season}_{patch}_{array}_{freq}_nohwp_night_3pass_{nway}_{set}_{product}.fits`

- "release": these maps are part of the DR4 data release, and versioning allows for future modifications of thise relase [possible tags: dr4.xy]
- "season": observation season [possible tags: s13, s14, s15, s16]
- "patch": survey patch [possible tags: D1, D5, D6, D56, D8, BN, AA]
- "array": telescope optic module on ACTPol camera [possible tags: pa1, pa2, pa3]
- "freq": frequency tag [possible tags: f090, f150]
- "nway": number of independet splits [possible tags: 2way, 4way]
- "set": split identifier or co-add version [possible tags: set0, set1, set2, set3, coadd]
- "product": see below for list of released products

#### Available products

More detailes availble in Sec. 5 of Aiola et al (2020)

- "map_srcfree": observed I,Q,U Stokes components with signal from point sources subtracted [uK]
- "srcs": I,Q,U Stokes components of the point sources signal [uK]
- NOTE: "map_srcfree"+"srcs" is the observed sky
- "ivar": inverse-variance pixel weight [uK^-2]
- "xlink": cross-linking information encoded as I,Q,U Stokes components [uK^-2]

#### Post-processing

The "map_srcfree", "srcs", and "ivar" maps are calibrated with a single coefficient, which is measured for each field and reported in Choi et al (2020). An extra polarization efficiency parameter is included (and let to vary) in the likelihood analysis and NOT considered here.

#### Remarks

- These maps are released following the IAU polarization convention (POLCCONV='IAU' in FITS header).
- Baseline software to handle these maps is Pixell (https://github.com/simonsobs/pixell).
"""


def get_patch(path: Path) -> str:
    patches = ["D1", "D5", "D6", "D56", "D8", "BN", "AA"]

    for patch in patches:
        if patch in path.name:
            return patch


def get_set(path: Path) -> str:
    sets = ["set0", "set1", "set2", "set3", "coadd"]

    for set_ in sets:
        if set_ in path.name:
            return set_


def get_map_type(path: Path) -> str:
    map_types = {
        "coadd_srcs": "source_only",
        "coadd_map_srcfree": "source_free",
        "coadd_ivar": "ivar_coadd",
        "coadd_xlink": "xlink_coadd",
        # Coadd is primary, fallback is splits
        "map_srcfree": "source_free_split",
        "srcs": "source_only_split",
        "ivar": "ivar_split",
        "xlink": "xlink_split",
    }

    for map_type, return_value in map_types.items():
        if map_type in path.name:
            return return_value


def get_description(path: Path) -> str:
    sub_set_main_descriptions = {
        "set0": "ACT DR4 4-way Split 0. Includes all the maps from the 4-way split 0, see the collection for more details",
        "set1": "ACT DR4 4-way Split 1. Includes all the maps from the 4-way split 1, see the collection for more details",
        "set2": "ACT DR4 4-way Split 2. Includes all the maps from the 4-way split 2, see the collection for more details",
        "set3": "ACT DR4 4-way Split 3. Includes all the maps from the 4-way split 3, see the collection for more details",
        "coadd": "ACT DR4 4-way Co-added Maps. Includes all the maps from the co-added maps, see the collection for more details",
    }

    patch = get_patch(path)

    set_ = get_set(path)

    return f"{sub_set_main_descriptions[set_]} (Patch {patch})."


def find_primary_map(list: list[Path]) -> Path:
    for path in list:
        if "map_srcfree" in path.name:
            return path


def get_name(path: Path) -> str:
    patch = get_patch(path)
    set_ = get_set(path)

    return f"ACT DR4 (Patch {patch}) 4-way ({set_})"


def get_units(path: Path) -> str:
    with fits.open(path) as hdul:
        return hdul[0].header.get("BUNIT", "Unknown")


if __name__ == "__main__":
    sub_sets = {}

    for fits_file in Path(".").glob("*.fits"):
        name = get_name(fits_file)

        if name not in sub_sets:
            sub_sets[name] = [fits_file]
        else:
            sub_sets[name].append(fits_file)

    sub_sets_descriptions_linker = {
        "map_srcfree": "I, Q, U source-free map",
        "srcs": "I, Q, U point source map",
        "ivar": "Inverse-variance map",
        "xlink": "Cross-linking map",
    }

    def link_to_path(path: Path) -> str:
        for name, description in sub_sets_descriptions_linker.items():
            if name in path.name:
                return description

    sub_sets_descriptions = {
        x: [link_to_path(y) for y in sub_sets[x]] for x in sub_sets.keys()
    }

    client = Client(api_key=API_KEY, host=SERVER_LOCATION, verbose=True)

    collection_id = create_collection(
        client=client,
        name=COLLECTION_NAME,
        description=COLLECTION_DESCRIPTION,
    )

    for sub_set in sub_sets.keys():
        metadata = MapSet(
            maps={
                get_map_type(fits_file): MapSetMap(
                    map_type=get_map_type(fits_file),
                    filename=fits_file.name,
                    units=get_units(fits_file),
                )
                for fits_file in sub_sets[sub_set]
            },
            pixelisation="healpix",
            telescope="ACT",
            instrument="ACTPol",
            release="DR4",
            season="s13",
            patch=get_patch(sub_sets[sub_set][0]),
            frequency="150",
            polarization_convention="IAU",
        )
        primary_map = find_primary_map(sub_sets[sub_set])

        product_id = create_product(
            client=client,
            name=sub_set,
            description=get_description(primary_map),
            metadata=metadata,
            sources=sub_sets[sub_set],
            source_descriptions=sub_sets_descriptions[sub_set],
        )

        add_to_collection(
            client=client,
            id=collection_id,
            product=product_id,
        )
