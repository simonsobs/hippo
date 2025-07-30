Python Interface
================

In addition to the command-line interface, we provide a python interface
- also called `henry`. Similarly to the command-line case, all authentication
information is read from your `~/.hippo.conf` file [described in the getting
started section](getting_started.md).

Local Products
--------------

The `henry` python inferface is designed to provide seamless access to
user-defined local products in the same way as remote products. To create
a purely local product:
```python
from henry import Henry
from hippometa import BeamMetadata

client = Henry()

beam_file = "act_dr6.02_daytime_beams.tar.gz"

beam = client.new_product(
    name="Daynight Beam (DR6)",
    description="The beam for DR6 products",
    metadata=BeamMetadata(),
    sources={
        "data": {
            "path": beam_file,
            "description": "Beam"
        }
    },
)
```
Here, `beam` is a python object (`LocalProduct`) that behaves just like a
dictionary. The keys of `beam` are what we call 'slugs' - valid keys defined by
the metadata type that you provide as the `metadata` argument. `data` is always
valid for all metadata types, but sometimes there are more for multi-source
products (see [metadata](#metadata))
```python
print(beam.metadata.valid_slugs)
>>> {'data'}
```
To access the 'sources' for products, you index by slug, so:
```python
print(beam_product["data"])
>>> LocalSource data (act_dr6.02_daytime_beams.tar; Beam) representing act_dr6.02_daytime_beams.tar.gz
```
The `LocalProduct` class also supports the usual `dict` methods - like
`.keys()`, `.values()`, `.items()`, `.pop()`, and so forth.

The values in the product, as you've seen above, are of type `LocalSource`. These
are just wrappers around filenames, incluing a little extra metadata. Each `LocalSource`
stores its:

- Name (defaults to the filename of the path)
- Description (defaults to None)
- Path (the path to the file)

You can update local sources directly, or by re-assigning them like a dictionary.
Assigning a string to each slug will convert it to a `LocalSource`:
```python
beam["data"] = "test_beam.tar"
print(beam["data"])
>>> LocalSource data (test_beam; None) representing test_beam.tar
```
Note that should you wish to push this product up to HIPPO, you'll need to give
it a description:
```python
beam["data"].description = "Replacement beam"
```

Metadata
--------

Other types of product are more complex - they come along with interesting metadata, 
and may be made up of more than one file. One example of this is called a `MapSet`, which
can represent one or more map files. The `MapSet` stores information like the patch
the observations were taken in, the band, the telescope was used - basically everything
that would normally just be in the FITS header.

`MapSets` can represent more than one file, which is useful if you have, e.g. a cross-linking
map or a mask that you want to bundle alongside a source-free map. The valid slugs for the
`MapSet` can be found easily:
```python
print(MapSet.valid_slugs)
{'coadd', 'source_free', 'xlink_coadd', 'source_free_split', 'ivar_split',
'ivar_coadd', 'split', 'xlink_split', 'mask', 'data', 'source_only_split',
'source_only'}
```
Let's create a coadd map for ACTxPlanck:
```python
map_file = "act-planck_dr4dr6_coadd_AA_daynight_f090_map.fits"

map_set = client.new_product(
    name="ACTxPlanck DR6 f090 coadd map",
    description="One of the many coadd maps",
    metadata=MapSet.from_fits(filename=map_file),
    sources={"map": {"path": map_file, "description": "actxplanck coadd"}},
)
```
Note the use of the `from_fits` classmethod on the `MapSet` class - this allows
you to automatically construct the metadata object from the FITS header.
```python
print(map_set.metadata)
>>> metadata_type='mapset' pixelisation='healpix' telescope='act+planck'
instrument='mbac+actpol+advact' release='dr4dr6' season='s08s22' patch='AA'
frequency='090' polarization_convention='' tags=['daynight', 'prelim']
```
There are many more metadata types, and it's important to correctly describe your
data with them, especially if you want to push it up for others to use. The different
metadata types are available in `hippometa`.

Local Collections
-----------------

Creating collections is very similar to creating products!
```python
collection = client.new_collection(
    name="Some ACT DR6 Products",
    description="A beam and a map from DR6",
    products=[map_set, beam],
)
```
This `collection` is a `LocalCollection` object. `LocalCollection`s behave just
like lists, and they can contain both products and other collections - though
it's generally best to make them just contain products in the python interface
(collection hierarchies are helpful mainly for presenting things in an organised
way in the web UI).

The collection can be indexed and, importantly, iterated through:
```python
for product in collection:
    print(product.name)

>>> ACTxPlanck DR6 f090 coadd map
>>> Daynight Beam (DR6)
```
So, if you, for instance, had a large collection of these coadd maps, you could always
iterate through them all (ignoring, for example, cross-linking maps):
```python
for product in collection:
    with open(product["map"].path, "r") as handle:
        process(handle=handle)
```
Hopefully you can begin to see how idiomatic pipelines can be built with the
simple constructs: products as dictionaries with constrained keys, and collections
as lists of products.

Similarly to how `LocalProduct` supports the `dict` methods, `LocalCollection`
supports the `list` methods, like `append`, `pop`, and so on.

Serialization
-------------

Your `LocalProduct` and `LocalCollection`s also happen to be
[pydantic](https://pydantic.dev) models. This means they can be very esaily saved to disk
as JSON objects and recovered later. To convert a collection, with its products,
to JSON:
```python
print(collection.model_dump_json())
>>> {"name":"Some ACT DR6 Products","description":"A beam and a map from DR6","prod...
```

Pushing
-------

Local products and collections can easily be synchronized with the remote HIPPO server,
analogously to `git`. To send up a collection and all of its products, you simply need
to tell the client to `push` it:
```python
henry.push(collection)
```
Depending on your client verbosity, you may see progress bars for uploading individual
products like:
```
Uploading:  72%|███████▏  | 3.56G/4.98G [00:28<00:11, 130MB/s]
```

Before your collection and products get sent to the server, they are ran through
the `preflight` checks (which can be called in isolation using that method). If
they fail, they will raise a `henry.exceptions.PreflightFailedError`. Common
causes of preflight failures are:

- Missing source descriptions
- Missing files on disk

The preflight checks are designed to make sure that your data is correctly
rendered on the server when it gets there, and is usable by others.


Pulling
-------

To pull down a remote product, you can use the `pull_product` method:
```python
remote = henry.pull_product(
    product_id=map_set.product_id, realize_sources=False
)
```
Here, `remote` is a `RemoteProduct`. It's more restrictive than the
`LocalProduct` because it represents a frozen verison of the metadata that
is stored in HIPPO. We've also set `realize_sources=False` here, because
we don't want to download a copy of what we just uploaded. By default,
`realize_sources=True`, and when we `pull_product`, we also ensure that 
all of its data files are cached. That would allow us to do
`remote["map"].path` and have this automatically resolve to a local path
for a valid copy of the file!


Revisions
---------

Sometimes, we need to make changes to products we've already sent up. Henry and
HIPPO support [semantic versioning](https://semver.org), where we describe
changes to products as major, minor, or patch revisions. It's up to you to choose
the appropriate revision level.

To create a revision, simply call `create_revision` on a `RemoteProduct` with either
`minor=True`, `major=True`, or `patch=True`
```python
revision = remote.create_revision(major=True)
print(revision)
>>> A revision object with no changes relative to the parent product
```
Here, `revision` is a `RevisionProduct`, and is a hybrid between a `LocalProduct` and
a `RemoteProduct`. It contains a pointer, `.revision_of` to the `RemoteProduct`
that it is compared to. Assigning to any of the variables for a `RevisionProduct`
creates a 'diff' between it and the remote version. Let's say that we actually meant
to upload the f150 map:
```python
second_map = "act-planck_dr4dr6_coadd_AA_daynight_f150_map.fits"
revision.name = "ACTxPlanck DR6 f150 coadd map"
revision.metadata = MapSet.from_fits(second_map)
revision["map"] = second_map
revision["map"].description = "actxplanck coadd"
```
If we now print the revision:
```
Name: 'ACTxPlanck DR6 f090 coadd map' -> 'ACTxPlanck DR6 f150 coadd map'
Metadata diff: [frequency] 090 -> 150  
Replace sources: coadd
```
When we call `henry.push(revision)`, we'll upload the new `coadd` source (which
is now a different file), we'll change the metadata object to include the
different frequency information, and update the name.

With a verbose client, we can see all that happening:
```
Successfully validated file:
{
    'name': 'act-planck_dr4dr6_coadd_AA_daynight_f150_map.fits',
    'size': 5349890880,
    'checksum': 'xxh64:08afc3f88a8cbbe3',
    'description': 'actxplanck coadd'
}
Uploading file: 
act-planck_dr4dr6_coadd_AA_daynight_f150_map.fits
Uploading: 100%|██████████| 4.98G/4.98G [00:39<00:00, 134MB/s]
Successfully uploaded file: 
act-planck_dr4dr6_coadd_AA_daynight_f150_map.fits
Successfully updated product 6851dbddc9eb53e084db2234.
```

Realizing Sources
-----------------

If we now pull down our revised product, realizing its sources, we can see how
the caching works:
```python3
realized_product = henry.pull_product(product_id=revision.product_id)
```
In the background, we can see what's going on with a verbose client:
```
Successfully read product (ACTxPlanck DR6 f150 coadd map)
Successfully read product 6851de5cc9eb53e084db223d
File act-planck_dr4dr6_coadd_AA_daynight_f150_map.fits 
(84c9cc2d-f284-4e8b-b61c-c1b8e2c47083) not found in cache
Cached file act-planck_dr4dr6_coadd_AA_daynight_f150_map.fits 
(84c9cc2d-f284-4e8b-b61c-c1b8e2c47083)
```
The caching of the file occurred because we allowed `henry` to realize
our sources for us. If we now iterate through the sources:
```python
for slug, source in realized_product.items():
    print(slug, source.path)

>>> coadd /tmp/test_user/84c9cc2d-f284-4e8b-b61c-c1b8e2c47083/act-planck_dr4dr6_coadd_AA_daynight_f150_map.fits
```
which is a local path and can be loaded howver we wish.

Loading Downloaded Data
-----------------------

Downloaded products and collections can be read from disk using the `read_product`
and `read_collection` functions on the `Henry` client:
```python
downloaded_product = henry.read_product("./ACTxPlanck DR6 f150 coadd map")
```
By default, we allow partial loading of products and collections that are not
fully downloaded. To be more strict, you can use the `allow_incomplete=False`
argument in these read functions:
```python
henry.read_collection("./Unfinished Collection", False)
>>> CollectionIncompleteError(...)
```