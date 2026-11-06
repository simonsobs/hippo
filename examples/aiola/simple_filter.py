# %% [markdown]
# This script shows off how we can filter collections down to flat lists of
# products using the tools in HIPPO. The main object of interest here is the
# `FilteredCollection` class.
#
# The hippo API is broken down into modules that you can use to interact wtih certain
# sub-sections of the API. Here, we're going to be interacting with three main concepts:
#
# 1. Collections: A collection is a group of products that are related in some way. For
#    our case here, the colleciton is the DR4/S13 150 GHz data.
# 2. Products: A product is a single piece of data. In this case, we're going to be
#    working with the "splits" in a particular patch.
# 3. Relationships: Products can be related to one another. In this case, we're going to
#    be creating a parent/child relationship between the splits and the co-added map.
#
# There are two main objects of interest that are accessed through the core
# `ClientSettings` singleton:
#
# 1. The `client`: this object is your HTTP link to the hippo server.
# 2. The `cache`: this is an on-disk cache of products in hippo. This is the only
#    way you should interact with the filesystem for existing products when using hippo.
# %%
from henry import Henry
from hippoclient.core import ClientSettings

settings = ClientSettings(
    host="http://localhost:8000",
    token_tag=None,
    caches=[
        {
            "type": "filesystem",
            "path": "/tmp",
        }
    ],
)

henry = Henry(settings=settings, slugify=True)

# %% [markdown]
# We can filter on three things:
#
# - Product type (based on its metadata class)
# - Metadata keys and values
# - Available slugs.
#

# %%
PATCH = "D6"
COLLECTION_ID = "6aee15399c65b086f7388bc4"

if COLLECTION_ID is None:
    raise ValueError(
        "Please set the COLLECTION variable to the ID of the collection you want to use."
    )

collection = henry.pull_collection(
    COLLECTION_ID, realize_sources=False, pull_children=True
)

filtered = collection.filter(
    metadata_filter={"patch": PATCH},
)

print("Found", len(filtered.products), "matching products")


# %% [markdown]
# We can further filter collections, using the same functionality. If we are _sure_
# that we want to have only a single (or no) product, we can realize this with the
# `one` method. The first cell below -- called on our filtered collection -- will raise
# an error:

# %%
match = filtered.one()

# %%
SPLIT = "set1"

second_filter = filtered.filter(
    metadata_filter={"split": SPLIT},
)

print("Found", len(second_filter.products), "matching products")
product = second_filter.one()

# %% [markdown]
# Now we have a single product that matches our query. There are two options here:
# we can realize this product, or check it out to the filesystem.

# %%
realized_product = henry.realize(product)
print(realized_product)
# %% [markdown]
# This realizes all of the 'slugs' and associated sources. If you wanted just a sub-set
# you could have pasesd the 'slugs' argument. To check out the product to the filesystem,
# you can also use the `checkout` method:

# %%
checked_out_product = henry.checkout(
    product, directory="/tmp/product_checkout", slugs=["xlink"]
)

# %%
print(checked_out_product)
for slug, source in checked_out_product.sources.items():
    print(f"Slug: {slug}, Source: {source}")
# %% [markdown]
# With both, we can now access the products directly:

# %%
print("Realized source_only map:", realized_product["source_only"])
print("Checked out xlink map:", checked_out_product["xlink"])

# %%
from astropy.io import fits

source_only_map = fits.open(realized_product["source_only"].path)
xlink_map = fits.open(checked_out_product["xlink"].path)
# %%
