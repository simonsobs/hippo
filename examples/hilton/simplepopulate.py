"""
Populates the simple example server with a bunch of ACT maps.
"""

import os
from pathlib import Path

from hippoclient import Client
from hippoclient.collections import add as add_to_collection
from hippoclient.collections import create as create_collection
from hippoclient.core import ClientSettings
from hippoclient.product import create as create_product
from hippometa import CatalogMetadata, MapSet, MapSetMap

settings = ClientSettings()

API_KEY = os.getenv("HIPPO_API_KEY")
SERVER_LOCATION = os.getenv("HIPPO_HOST")

if API_KEY is None:
    API_KEY = "TEST_API_KEY"
    SERVER_LOCATION = "http://localhost:8000"

COLLECTION_NAME = "ACT DR5 SZ Cluster Catalog"

COLLECTION_DESCRIPTION = """
This collection corresponds to the NASA LAMBDA archive available at:
https://lambda.gsfc.nasa.gov/product/act/actpol_dr5_szcluster_catalog_info.html

v1.1 Fixes to erroneous opt_RADeg, opt_decDeg coordinates for the clusters
ACT-CL J1454.2+0434, ACT-CL J2317.1+0918 (thanks to Heinz Andernach for
reporting this). Fix for erroneous redshift for ACT-CL J1356.4+0339 (moves from
z = 0.354 to z = 0.282; thanks to Brandon Wolfe for reporting this). Otherwise,
identical to v1.0.
"""

catalogs = {
    "DR5_cluster-catalog_v1.1.fits": CatalogMetadata(
        file_type="fits",
        column_description={
            "name": "Cluster name in the format ACT-CL JHHMM.m±DDMM.",
            "RADeg": "Right Ascension in decimal degrees (J2000) of the SZ detection by ACT.",
            "decDeg": "Declination in decimal degrees (J2000) of the SZ detection by ACT.",
            "SNR": "Signal-to-noise ratio, optimized over all filter scales.",
            "y_c": "Central Comptonization parameter (× 10-4) measured using the optimal matched filter template (i.e., the one that maximizes SNR). Uncertainty column(s): err_y_c.",
            "fixed_SNR": "Signal-to-noise ratio at the reference 2.4′ filter scale.",
            "fixed_y_c": "Central Comptonization parameter (× 10-4) measured at the reference filter scale (2.4′). Uncertainty column(s): fixed_err_y_c.",
            "template": "Name of the matched filter template resulting in the highest SNR detection of this cluster.",
            "tileName": "Name of the ACT map tile (typically with dimensions 10 × 5 deg) in which the cluster was found.",
            "redshift": "Adopted redshift for the cluster. The uncertainty is only given for photometric redshifts. Uncertainty column(s): redshiftErr.",
            "redshiftType": "Redshift type (spec = spectroscopic, phot = photometric).",
            "redshiftSource": "Source of the adopted redshift.",
            "M500c": "M500c in units of 1014M⊙, assuming the UPP and Arnaud et al. (2010) scaling relation to convert SZ signal to mass. Uncertainty column(s): M500c_errPlus, M500c_errMinus.",
            "M500cCal": "M500c in units of 1014M⊙, rescaled using the richness-based weak-lensing mass calibration factor of 0.69 ± 0.07. Uncertainty column(s): M500cCal_errPlus, M500cCal_errMinus.",
            "M200m": "M200 with respect to the mean density, in units of 1014M⊙, converted from M500c using the Bhattacharya et al. (2013) c-M relation. Uncertainty column(s): M200m_errPlus, M200m_errMinus.",
            "M500cUncorr": "M500c in units of 1014M⊙, assuming the UPP and Arnaud et al. (2010) scaling relation to convert SZ signal to mass, uncorrected for bias due to the steepness of the cluster mass function. Uncertainty column(s): M500cUncorr_errPlus, M500cUncorr_errMinus.",
            "M200mUncorr": "M200 with respect to the mean density, in units of 1014M⊙, converted from M500c using the Bhattacharya et al. (2013) c-M relation, uncorrected for bias due to the steepness of the cluster mass function. Uncertainty column(s): M200mUncorr_errPlus, M200mUncorr_errMinus.",
            "footprint_DESY3": "Flag indicating if the cluster falls within the DES Y3 footprint.",
            "footprint_HSCs19a": "Flag indicating if the cluster falls within the HSC-SSP S19A footprint.",
            "footprint_KiDSDR4": "Flag indicating if the cluster falls within the KiDS DR4 footprint.",
            "zCluster_delta": "Density contrast statistic measured at the zCluster photometric redshift. Uncertainty column(s): zCluster_errDelta.",
            "zCluster_source": "Photometry used for zCluster measurements. One of: DECaLS (DR8), KiDS (DR4), SDSS (DR12).",
            "RM": "Flag indicating cross-match with a redMaPPer-detected cluster in the SDSS footprint (Rykoff et al. 2014).",
            "RM_LAMBDA": "Optical richness measurement for the redMaPPer algorithm in the SDSS footprint. Uncertainty column(s): RM_LAMBDA_ERR.",
            "RMDESY3": "Flag indicating cross-match with a redMaPPer-detected cluster in the DES Y3 footprint (Rykoff et al. 2016).",
            "RMDESY3_LAMBDA_CHISQ": "Optical richness measurement for the redMaPPer algorithm in the DES Y3 footprint. Uncertainty column(s): RMDESY3_LAMBDA_CHISQ_E.",
            "CAMIRA": "Flag indicating cross-match with a CAMIRA-detected cluster in the HSCSSP S19A footprint (Oguri et al. 2018).",
            "CAMIRA_N_mem": "Optical richness measurement for the CAMIRA algorithm in the HSCSSP S19A footprint.",
            "opt_RADeg": "Alternative optically-determined Right Ascension in decimal degrees (J2000), from a heterogeneous collection of measurements (see opt_positionSource).",
            "opt_decDeg": "Alternative optically-determined Declination in decimal degrees (J2000), from a heterogeneous collection of measurements (see opt_positionSource).",
            "opt_positionSource": "Indicates the source of the alternative optically-determined cluster position. One of: AMICO (position from the AMICO cluster finder; \citealt2019MNRAS.485..498M), CAMIRA (position from the CAMIRA cluster finder; \citealtOguri_2018), RM, RMDESY3, RMDESY3ACT (position from the redMaPPer cluster finder, in SDSS, DES Y3, or DES Y3 using the ACT position as a prior; \citealtRykoff_2014, Rykoff_2016), Vis-BCG (BCG position from visual inspection of available optical/IR imaging; this work), WHL2015 (position from \citealtWH_2015).",
            "notes": "If present, at least one of: AGN? (central galaxy may have color or spectrum indicating it may host an AGN); Lensing? (cluster may show strong gravitational lensing features); Merger? (cluster may be a merger); Star formation? (a galaxy near the center may have blue colors which might indicate star formation if it is not a line-of-sight projection). These notes are not comprehensive and merely indicate some systems that were identified as potentially interesting during visual inspection of the available optical/IR imaging.",
            "knownLens": "Names of known strong gravitational lenses within 2 Mpc projected distance of this cluster (comma delimited when there are multiple matches).",
            "knownLensRefCode": "Reference codes (comma delimited when there are multiple matches) corresponding to the entries in the knownLens field. See Table~\reftab:lensCodes to map between the codes used in this field and references to the corresponding lens catalog papers.",
            "warnings": "If present, a warning message related to the redshift measurement for this cluster.",
        },
        telescope="ACT",
        instrument="ACTPol",
        release="DR5",
    ),
    "DR5_multiple-systems_v1.0.fits": CatalogMetadata(
        file_type="fits",
        column_description={
            "name": "Name of the multiple system; constructed from the names of the individual clusters as given in the cluster catalog.",
            "meanRADeg": "Mean Right Ascension in decimal degrees (J2000) of the clusters forming the multiple system.",
            "meanDecDeg": "Mean Declination in decimal degrees (J2000) of the clusters forming the multiple system.",
            "meanRedshift": "Mean of the redshifts of the individual clusters that make up the multiple system.",
            "numClusters": "The number of clusters that make up the multiple system.",
            "maxSeparationMpc": "The projected distance in Mpc (at the median redshift) between the two most widely separated components of the multiple system.",
            "maxSeparationArcmin": "The angular separation in arcmin between the two most widely separated components of the multiple system.",
            "includesPhotoRedshift": "Flag indicating that the multiple system includes at least one cluster that has only a photometric redshift estimate.",
            "tileName": "Name(s) of the ACT map tile(s) (typically with dimensions 10 × 5 deg) in which each component of the multiple system was found.",
        },
        telescope="ACT",
        instrument="ACTPol",
        release="DR5",
    ),
}

catalog_descriptions = {
    "DR5_cluster-catalog_v1.1.fits": "The file DR5_cluster-catalog_v1.1.fits is a FITS table that contains the ACT DR5 cluster catalog as described in Hilton et al. (2020). It can be viewed with any compatible viewer, e.g., TopCat, or read into Python using the astropy.table module.",
    "DR5_multiple-systems_v1.0.fits": "The file DR5_multiple-systems_v1.0.fits is a FITS table that contains the catalog of multiple systems and potential superclusters, assembled as described in Hilton et al. (2020). It can be viewed with any compatible viewer, e.g., TopCat, or read into Python using the astropy.table module.",
}

catalog_names = {
    "DR5_cluster-catalog_v1.1.fits": "ACT DR5 SZ Cluster Catalog",
    "DR5_multiple-systems_v1.0.fits": "ACT DR5 SZ Cluster Catalog (Multiple Systems)",
}

mask = MapSet(
    maps={
        "mask": MapSetMap(
            map_type="mask",
            filename="mask.fits",
            units="",
        )
    },
    pixelisation="cartesian",
    telescope="ACT",
    instrument="ACTPol",
    release="DR5",
)


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

    mask_id = create_product(
        client=client,
        name="ACT DR5 SZ Cluster Catalog Sky Mask",
        description="The file DR5_cluster-search-area-mask_v1.0.fits is a compressed FITS image that contains the cluster search area (pixels with value = 1) as described in Hilton et al. (2020).",
        metadata=mask,
        sources=[Path("DR5_cluster-search-area-mask_v1.0.fits")],
        source_descriptions=["Mask file"],
    )

    add_to_collection(
        client=client,
        id=collection_id,
        product=mask_id,
    )
