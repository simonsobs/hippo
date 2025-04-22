"""
An extremely simple example that creates two collections, one which is a child
collection of the other.
"""

import random

from hippoclient import Client
from hippoclient.collections import create as create_collection
from hippoclient.relationships import add_child_collection

API_KEY = "TEST_API_KEY"
SERVER_LOCATION = "http://127.0.0.1:8000"


def parent_child_collection_generator(
    parent_id, parent_name, number_of_children, generate_grandchildren
):
    for n in range(1, number_of_children + 1):
        child_id = create_collection(
            client=client,
            name=f"Child {n} of {parent_name}",
            description=f"This is child {n} of {parent_name}",
        )

        if generate_grandchildren:
            # randomly generate grandchildren at a 50% rate per collection
            if random.randint(0, 1) == 0:
                # randomly generate a number of grandchildren between 1 and 3
                num_grandchildren = random.randint(1, 3)
                for ng in range(num_grandchildren):
                    grandchild_id = create_collection(
                        client=client,
                        name=f"Grandchild {ng + 1} of Child {n}",
                        description="",
                    )
                    add_child_collection(
                        client=client, parent=child_id, child=grandchild_id
                    )

        add_child_collection(client=client, parent=parent_id, child=child_id)


if __name__ == "__main__":
    client = Client(api_key=API_KEY, host=SERVER_LOCATION, verbose=True)

    parent_id_1 = create_collection(
        client=client,
        name="Parent Collection with One Child",
        description="This is a parent collection with one child",
    )
    parent_child_collection_generator(
        parent_id=parent_id_1,
        parent_name="Parent Collection with One Child",
        number_of_children=1,
        generate_grandchildren=True,
    )

    parent_id_2 = create_collection(
        client=client,
        name="Parent Collection with Five Child",
        description="This is a parent collection with five child",
    )
    parent_child_collection_generator(
        parent_id=parent_id_2,
        parent_name="Parent Collection with Five Children",
        number_of_children=5,
        generate_grandchildren=True,
    )

    parent_id_3 = create_collection(
        client=client,
        name="Parent Collection with Seven Child",
        description="This is a parent collection with seven child",
    )
    parent_child_collection_generator(
        parent_id=parent_id_3,
        parent_name="Parent Collection with Seven Children",
        number_of_children=7,
        generate_grandchildren=False,
    )
