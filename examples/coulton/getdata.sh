# Script, written as a bash script, to provide curl commands for all associated data products.


#        ACT DR6 Compton-y Map
curl -s --retry 5 -k -o ilc_actplanck_ymap.fits https://lambda.gsfc.nasa.gov/data/suborbital/ACT/ACT_adv/Compton_y_maps/ilc_actplanck_ymap.fits
curl -s --retry 5 -k -o wide_mask_GAL070_apod_1.50_deg_wExtended.fits https://lambda.gsfc.nasa.gov/data/suborbital/ACT/ACT_adv/Compton_y_maps/wide_mask_GAL070_apod_1.50_deg_wExtended.fits
curl -s --retry 5 -k -o ilc_beam.txt https://lambda.gsfc.nasa.gov/data/suborbital/ACT/ACT_adv/Compton_y_maps/ilc_beam.txt