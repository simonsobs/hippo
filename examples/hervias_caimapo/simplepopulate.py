"""
Populates the simple example server with a bunch of ACT maps.
"""

import os
from pathlib import Path

from hippoclient import Client
from hippoclient.collections import add as add_to_collection
from hippoclient.collections import create as create_collection
from hippoclient.product import create as create_product
from hippometa import CatalogMetadata

API_KEY = os.getenv("HIPPO_API_KEY")
SERVER_LOCATION = os.getenv("HIPPO_HOST")

if API_KEY is None:
    API_KEY = "TEST_API_KEY"
    SERVER_LOCATION = "http://127.0.0.1:8000"

COLLECTION_NAME = "ACT Targeted Transient Flux Constraints"

COLLECTION_DESCRIPTION = """
This collection corresponds to the NASA LAMBDA archive available at:
https://lambda.gsfc.nasa.gov/product/act/actadv_targeted_transient_constraints_2023_info.html

ACT Targeted Transient Flux Constraints from Hervías-Caimapo et al. 2023

This data release provides full tables of flux density upper limits for
individual targeted transients as observed by ACT, presented in Hervías-Caimapo
et al. (2023). The tables include multiple time ranges before and after the
discovery of the transient, in the f090, f150, f220 frequency channels of ACT
when available. Samples of the content of the tables are shown in the paper,
while this release includes all the individual transients.

During the peer review process, we discovered two mistakes that impact the flux
calculation: we did not deconvolve the pixel window function from maps and the
spectral correction for beams was executed with the wrong procedure. However,
the effect is minimal, of only a few percent in the flux estimation. In February
2024 the tables were updated correcting for these.

### Tables

There are three tables: table_SNe.txt corresponds to SNe and Astronomical
Transients (ATs), table_TDEs.txt corresponds to TDEs, and table_GRBs corresponds
to GRBs. All the flux density upper limits are in units of mJy.
"""

catalogs = {
    "table_SNe.txt": CatalogMetadata(
        file_type="txt",
        column_description={
            "Name": "SN/AT name",
            "RAdeg": "Right Ascension in degrees",
            "DECdeg": "Declination in degrees",
            "Discovery": "Discovery date of the transient",
            "freq": "ACT frequency channel where the measurement is made",
            "Flux_upper_limit_-28,0": "Flux upper limit in the range -28,0 days",
            "Flux_upper_limit_0,18": "Flux upper limit in the range 0,18 days",
            "Flux_upper_limit_28,56": "Flux upper limit in the range 28,56 days",
            "Flux_upper_limit_56,84": "Flux upper limit in the range 56,84 days",
            "Flux_upper_limit_0,56": "Flux upper limit in the range 0,56 days",
            "Flux_upper_limit_0,84": "Flux upper limit in the range 0,84 days",
        },
        telescope="ACT",
        instrument="advACT",
        release="DR6",
    ),
    "table_TDEs.txt": CatalogMetadata(
        file_type="txt",
        column_description={
            "Name": "TDE name",
            "RAdeg": "Right Ascension in degrees",
            "DECdeg": "Declination in degrees",
            "Discovery": "Discovery date of the transient",
            "freq": "ACT frequency channel where the measurement is made",
            "Flux_upper_limit_-28,0": "Flux upper limit in the range -28,0 days",
            "Flux_upper_limit_0,18": "Flux upper limit in the range 0,18 days",
            "Flux_upper_limit_28,56": "Flux upper limit in the range 28,56 days",
            "Flux_upper_limit_56,84": "Flux upper limit in the range 56,84 days",
            "Flux_upper_limit_0,56": "Flux upper limit in the range 0,56 days",
            "Flux_upper_limit_0,84": "Flux upper limit in the range 0,84 days",
        },
        telescope="ACT",
        instrument="advACT",
        release="DR6",
    ),
    "table_GRBs.txt": CatalogMetadata(
        file_type="txt",
        column_description={
            "Name": "GRB name",
            "RAdeg": "Right Ascension in degrees",
            "DECdeg": "Declination in degrees",
            "Discovery": "Discovery date of the transient",
            "freq": "ACT frequency channel where the measurement is made",
            "Flux_upper_limit_-3,0": "Flux upper limit in the range -3,0 days",
            "Flux_upper_limit_0,3": "Flux upper limit in the range 0,3 days",
            "Flux_upper_limit_3,6": "Flux upper limit in the range 3,6 days",
            "Flux_upper_limit_6,9": "Flux upper limit in the range 6,9 days",
            "Flux_upper_limit_9,12": "Flux upper limit in the range 9,12 days",
            "Flux_upper_limit_12,15": "Flux upper limit in the range 12,15 days",
            "Flux_upper_limit_-7,0": "Flux upper limit in the range -7,0 days",
            "Flux_upper_limit_0,7": "Flux upper limit in the range 0,7 days",
            "Flux_upper_limit_7,14": "Flux upper limit in the range 7,14 days",
            "Flux_upper_limit_14,21": "Flux upper limit in the range 14,21 days",
            "Flux_upper_limit_21,28": "Flux upper limit in the range 21,28 days",
            "Flux_upper_limit_0,28": "Flux upper limit in the range 0,28 days",
        },
        telescope="ACT",
        instrument="advACT",
        release="DR6",
    ),
}

catalog_descriptions = {
    "table_SNe.txt": "The names of the transients (SNe or ATs) were taken from the Open Supernova Catalog (https://github.com/astrocatalogs/supernovae), so the names follow the convention in that catalog. Some SNe have multiple names, but in our table we list whatever name is first in the Open Supernova Catalog.",
    "table_TDEs.txt": "The names of TDEs were taken either from the Open TDE Catalog (https://tde.space), from the Gezari 2021 review (https://www.annualreviews.org/doi/10.1146/annurev-astro-111720-030029) or the two TDEs from Sazonov et al. (2021) (https://academic.oup.com/mnras/article/508/3/3820/6381721). Some TDEs can have multiple names, but in our table we list whatever name is first in these sources.",
    "table_GRBs.txt": "The names of GRBs are standard, named after the day they were detected. They were taken from the Neil Gehrels Swift Observatory site (https://swift.gsfc.nasa.gov/archive/grb_table/).",
}

catalog_names = {
    "table_SNe.txt": "ACT DR6 Supernova and Astronomical Transient Catalog",
    "table_TDEs.txt": "ACT DR6 Tidal Disruption Event Catalog",
    "table_GRBs.txt": "ACT DR6 Gamma-Ray Burst Catalog",
}

if __name__ == "__main__":
    client = Client(api_key=API_KEY, host=SERVER_LOCATION, verbose=True)

    collection_id = create_collection(
        client=client,
        name=COLLECTION_NAME,
        description=COLLECTION_DESCRIPTION,
    )

    for catalog in catalogs.keys():
        product_id = create_product(
            client=client,
            name=catalog_names[catalog],
            description=catalog_descriptions[catalog],
            metadata=catalogs[catalog],
            sources=[Path(catalog)],
            source_descriptions=["Catalog file"],
        )

        add_to_collection(
            client=client,
            id=collection_id,
            product=product_id,
        )
