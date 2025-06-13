import sys

from henry import Henry

henry = Henry()

prod = henry.pull_product(sys.argv[1])
revision = prod.create_revision(major=True)
revision.name = "New name"
revision.description = "Haha"
newmeta = revision.revision_of.metadata.model_copy()
newmeta.pixelisation = "cartesian"
newmeta.patch = "D4"
revision.metadata = newmeta

print(revision)

henry.push(revision)
