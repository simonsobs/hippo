from henry import Henry

client = Henry()

p = client.pull_product("685d3cd7b10788ebc5d699c5", False)

r = p.create_revision(patch=True)

r.description = """
This is a map of all available tubes and wafers for f090 of all CMB observations between April 17-19 2025.
The list of obs included is:

```
obs_1744865577_lati4_111
obs_1744865579_lati3_111
obs_1744865579_lati6_111
obs_1744865580_lati1_111
obs_1744869456_lati3_111
obs_1744869458_lati1_111
obs_1744869458_lati4_111
obs_1744869459_lati6_111
obs_1744877430_lati3_111
obs_1744877430_lati4_111
obs_1744877432_lati1_111
obs_1744877432_lati6_110
obs_1744878749_lati1_111
obs_1744878749_lati3_111
obs_1744878749_lati4_111
obs_1744878749_lati6_110
obs_1744880524_lati1_111
obs_1744880524_lati3_111
obs_1744880525_lati4_111
obs_1744880525_lati6_110
obs_1744883408_lati4_111
obs_1744883408_lati6_110
obs_1744883409_lati3_111
obs_1744883411_lati1_111
obs_1744886228_lati1_111
obs_1744886229_lati6_110
obs_1744886231_lati3_111
obs_1744886231_lati4_111
obs_1744955509_lati6_111
obs_1744955510_lati1_111
obs_1744955510_lati3_111
obs_1744955510_lati4_111
obs_1744963426_lati3_111
obs_1744963426_lati4_111
obs_1744963428_lati6_111
obs_1744963429_lati1_111
obs_1744969330_lati1_111
obs_1744969330_lati4_111
obs_1744969331_lati6_111
obs_1744969333_lati3_111
obs_1744972391_lati1_111
obs_1744972391_lati3_111
obs_1744972391_lati4_111
obs_1744972391_lati6_111
obs_1744978387_lati1_111
obs_1744978387_lati6_111
obs_1744978389_lati3_111
obs_1744978390_lati4_111
obs_1744979769_lati1_111
obs_1744979770_lati3_111
obs_1744979771_lati4_111
obs_1744979772_lati6_111
obs_1744981710_lati6_111
obs_1744981711_lati1_111
obs_1744981711_lati4_111
obs_1744981713_lati3_111
obs_1744983489_lati6_111
obs_1744983491_lati3_111
obs_1744983493_lati1_111
obs_1744983493_lati4_111
obs_1745041983_lati1_111
obs_1745041983_lati6_111
obs_1745041984_lati3_111
obs_1745041987_lati4_111
obs_1745055378_lati3_111
obs_1745055379_lati4_111
obs_1745055379_lati6_111
obs_1745055380_lati1_111
obs_1745058548_lati1_111
obs_1745058548_lati4_111
obs_1745058549_lati3_111
obs_1745058549_lati6_111
obs_1745101206_lati1_111
obs_1745101206_lati6_111
obs_1745101209_lati3_111
obs_1745101209_lati4_111
```
The reason for this date is that this is after mirrors were aligned and before the corotator started moving. 

These are the details:

+ This sotodlib PR is used.
+ This not-yet-official pointing by Saianeesh is used (see below for details).
+ This preprocessing config `preprocess_config_cmb.yaml`.
+ The maps is 2 passes, 400 CG steps, nearest interpolation, using the ACT mask (`/global/cfs/cdirs/cmb/data/act_dr6/dr6.02/maps/published/srcsamp_mask.fits`) for point sources.
+ The abscal is `lat_abscal_250602`.
+ The maps are here `/global/cfs/cdirs/sobs/users/chervias/LAT/maps`.

Pointing details:

```yaml
- db: '/global/cfs/cdirs/sobs/users/skh/data/pointing/lat/pointing_model_bk/db.sqlite'
  label: pointing_model
  unpack: pointing_model
```

Created by Carlos Hervias.
"""

print(r)

client.push(r)
