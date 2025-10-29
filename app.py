import marimo

__generated_with = "0.13.15"
app = marimo.App()


@app.cell
def _():
    from henry import Henry
    from hippometa import BeamMetadata, MapSet

    return BeamMetadata, Henry, MapSet


@app.cell
def _():
    beam_file = "act_dr6.02_daytime_beams.tar.gz"
    map_file = "act-planck_dr4dr6_coadd_AA_daynight_f090_map.fits"
    return beam_file, map_file


@app.cell
def _(Henry):
    henry = Henry()
    return (henry,)


@app.cell
def _(BeamMetadata, beam_file, henry):
    beam_product = henry.new_product(
        name="Daynight Beam (DR6)",
        description="The beam for DR6 products",
        metadata=BeamMetadata(),
        sources={"data": {"path": beam_file, "description": "Beam"}},
    )
    return (beam_product,)


@app.cell
def _(MapSet):
    MapSet.valid_slugs
    return


@app.cell
def _(MapSet, henry, map_file):
    map_product = henry.new_product(
        name="ACTxPlanck DR6 f090 coadd map",
        description="One of the many coadd maps",
        metadata=MapSet.from_fits(filename=map_file),
        sources={"map": {"path": map_file, "description": "actxplanck coadd"}},
    )
    return (map_product,)


@app.cell
def _(map_product):
    print(map_product.metadata)
    return


@app.cell
def _(map_product):
    print(map_product.metadata)
    return


@app.cell
def _(beam_product, henry, map_product):
    collection = henry.new_collection(
        name="Some ACT DR6 Products",
        description="A beam and a map from DR6",
        products=[map_product, beam_product],
    )
    return (collection,)


@app.cell
def _(collection):
    print(collection)
    return


@app.cell
def _(collection, henry):
    henry.push(collection)
    return


@app.cell
def _(henry, map_product):
    remote = henry.pull_product(
        product_id=map_product.product_id, realize_sources=False
    )
    return (remote,)


@app.cell
def _(remote):
    print(remote)
    return


@app.cell
def _(henry, map_product):
    revision = henry.pull_product(
        product_id=map_product.product_id, realize_sources=False
    ).create_revision(major=True)
    return (revision,)


@app.cell
def _(revision):
    print(revision.revision_of)
    return


@app.cell
def _(map_product, revision):
    second_map = "act-planck_dr4dr6_coadd_AA_daynight_f150_map.fits"
    revision.name = "ACTxPlanck DR6 f150 coadd map"
    revision.metadata = map_product.metadata.model_copy()
    revision.metadata.frequency = "150"
    revision["map"] = second_map
    revision["map"].description = "actxplanck coadd"
    return


@app.cell
def _(revision):
    print(revision)
    return


@app.cell
def _(henry, revision):
    henry.push(revision)
    return


@app.cell
def _(henry, revision):
    realized_product = henry.pull_product(product_id=revision.product_id)
    return (realized_product,)


@app.cell
def _(realized_product):
    for slug, source in realized_product.items():
        print(slug, source.path)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
