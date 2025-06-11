"""
Henry is the high-level client for hippo. Lower-level functions are available
in `hippoclient`.
"""

"""
Henry is the high-level interface to HIPPO in the python client. There is also
henry the cli tool, performing similar (but more limited) functions.
"""

# from pydantic import Field, BaseModel
# import io
# from abc import ABC


# prod = h.new_product(
#     name="haha fave prod",
#     desc="the best prod evah",
#     metadata=MapSet(...),
#     #...
#     #kwargs only
#     coadd=Path(...),
# )

# #coadd is then cooerced into LocalProduct which contains the path and optional description
# #so you can then do
# prod.coadd.description = "The coadd map"

# #You can assign all valid slugs
# prod.xlink = Path(...)
# prod.xlink.description = "Xlink map"

# # Can also do
# prod.mask = LocalProduct(
#     path=Path(...),
#     description=...
# )

# # This reduces verbosity....
# # Sould have a pre-flight check that you can run that loops through everything and checks...
# # name is set
# # description is set
# # path is set
# # path is valid
# # metadata is set

# prod.upload()
# #or
# h.upload(product=prod)


# # You can access the files with
# with open(prod.mask.path, "r") as handle:
#     pass

# #or
# with prod.mask.handle() as handle:
#     pass