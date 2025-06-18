"""
An extremely simple example that creates two collections, one which is a child
collection of the other.
"""

import random

from henry import Henry

henry = Henry()


def parent_child_collection_generator(
    parent, number_of_children, generate_grandchildren
):
    for n in range(1, number_of_children + 1):
        child = henry.new_collection(
            name=f"Child {n} of {parent.name}",
            description=f"This is child {n} of {parent.name}",
        )

        parent.append(child)

        if generate_grandchildren:
            # randomly generate grandchildren at a 50% rate per collection
            if random.randint(0, 1) == 0:
                # randomly generate a number of grandchildren between 1 and 3
                num_grandchildren = random.randint(1, 3)
                for ng in range(num_grandchildren):
                    child.append(
                        henry.new_collection(
                            name=f"Grandchild {ng + 1} of Child {n}",
                            description=f"This is grandchild {ng + 1} of {parent.name}",
                        )
                    )

    return child


if __name__ == "__main__":
    parent = henry.new_collection(
        name="Parent Collection with One Child",
        description="This is a parent collection with one child",
    )

    parent_child_collection_generator(
        parent=parent, number_of_children=1, generate_grandchildren=True
    )

    henry.push(parent)

    parent_2 = henry.new_collection(
        name="Parent Collection with Five Children",
        description="This is a parent collection with five children",
    )

    parent_child_collection_generator(
        parent=parent_2,
        number_of_children=5,
        generate_grandchildren=True,
    )

    henry.push(parent_2)

    parent_3 = henry.new_collection(
        name="Parent Collection with Seven Children",
        description="This is a parent collection with seven children",
    )

    parent_child_collection_generator(
        parent=parent_3,
        number_of_children=7,
        generate_grandchildren=False,
    )

    henry.push(parent_3)
