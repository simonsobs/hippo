from henry import Henry
from hippometa import BeamMetadata

client = Henry()

c = client.pull_collection("68fae3046f8eaf0797249625", False, True)

for p in c.products:
    if p.version != "1.0.0":
        continue

    platform, frequency, wafer, coadd, beam, map = p.name.split("_")

    metadata = BeamMetadata(
        telescope=platform, instrument=platform, wafer=wafer, frequency=frequency
    )

    formatted_platform = platform.replace("sat", "SAT")

    new_name = f"{formatted_platform} {frequency} ({wafer}) coadd beam map"
    new_description = f"{formatted_platform} beam map (jupiter) for frequency {frequency} and wafer {wafer}, made 2025-07-21"

    r = p.create_revision(patch=True)

    r.name = new_name
    r.description = new_description
    r.metadata = metadata

    client.push(r)
