from henry import Henry

client = Henry()

p = client.pull_product("685d3cd7b10788ebc5d699c5", False)

c = client.new_collection(
    name="LAT Proto-ISO",
    description="LAT Proto-ISO products, including test maps and analyses. See [this Confluence page](https://simonsobs.atlassian.net/wiki/spaces/PRO/pages/1132462348/LAT+proto+ISO) for more information.",
    products=[p],
)

client.push(c)
