"""
Populates the simple example server with a bunch of ACT maps.
"""

from henry import Henry, LocalSource
from hippometa import BeamMetadata, MapSet

COLLECTION_NAME = "ACT (AdvACT) Compton-y"

COLLECTION_DESCRIPTION = """
### Summary

This repository contains the Compton-y map obtained from combining Planck and ACT DR6 data. These maps cover ~1/3 of the sky. The maps are provided in Plate Carreé projection with ~0.5 arcmin resolution. We also provide a mask and a file characterizing the beam that is applied to the map. The map is lowpass filtered to contain modes up to ell=17000. Contacts: William Coulton, Mathew S. Madhavacheril, Adriaan J. Duivenvoorden, J. Colin Hill

More extensive products are available on NERSC at /global/cfs/projectdirs/act/www/dr6_nilc/ymaps_20230220 or this url. These products include simulations, a range of masks and Compton-y maps with methods to mitigate CIB contamination.

More details about these products can be found in 2307.01258, which details the methods used to create the maps and simulations. Please cite 2307.01258 if you use these products.

### Notebooks

Two notebooks demonstrating two possible uses of the Compton-y maps are provided on GitHub here. The first notebook shows how to extract cutouts around objects of interest and perform a stacking analysis. The second example demonstrate a cross correlation and how to mitigate the CIB. The pixell package is used in these notebooks to read and manipulate Plate Carreé maps. Further examples can be found here. Contacts: Martine Lokken and Ola Kusiak.
"""

henry = Henry()

map_set = henry.new_product(
    name="Compton-y Map (ACT DR6)",
    description="Compton-y map and mask from ACT DR6.",
    metadata=MapSet(
        pixelisation="equirectangular",
        telescope="ACT",
        instrument="AdvACT",
        release="DR6",
        season=None,
        patch=None,
        frequency=None,
        polarization_convention=None,
        tags=["ymap"],
    ),
    sources=dict(
        coadd=LocalSource(
            path="ilc_actplanck_ymap.fits",
            description="Compton-y map from ACT DR6, lowpass filtered to ell=17000",
        ),
        mask=LocalSource(
            path="wide_mask_GAL070_apod_1.50_deg_wExtended.fits",
            description="Mask for the Compton-y map from ACT DR6",
        ),
    ),
)

beam = henry.new_product(
    name="Compton-y Beam (ACT DR6)",
    description="Beam used for the Compton-y map for ACT DR6",
    metadata=BeamMetadata(),
    sources=dict(
        data=LocalSource(path="ilc_beam.txt", description="Beam file"),
    ),
)

collection = henry.new_collection(
    name=COLLECTION_NAME, description=COLLECTION_DESCRIPTION, products=[map_set, beam]
)

if __name__ == "__main__":
    henry.push(collection)
