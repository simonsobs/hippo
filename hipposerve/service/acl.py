"""
Access control setup (changing access control levels, checking
for access to documents). Works with `ProtectedDocument`s.
"""

from typing import Iterable

from hipposerve.database import ProtectedDocument
from hipposerve.service import versioning
from hipposerve.service.auth import AuthenticationError


async def update_access_control(
    doc: ProtectedDocument,
    owner: str | None = None,
    add_readers: list[str] | None = None,
    remove_readers: list[str] | None = None,
    add_writers: list[str] | None = None,
    remove_writers: list[str] | None = None,
) -> ProtectedDocument:
    """
    Update the access control on this doc, either adding or removing
    readers or writers. Note that access control changes walk the entire
    tree and update all docs, and do not create a new version.
    """

    initial_doc_id = doc.id

    if not doc.current:
        raise versioning.VersioningError(
            "Attempting to update a non-current product. You must always "
            "make changes to the head of the list"
        )

    readers = (set(doc.readers) | set(add_readers or [])) - set(remove_readers or [])
    writers = (set(doc.writers) | set(add_writers or [])) - set(remove_writers or [])

    if owner:
        readers.add(owner)
        writers.add(owner)
    else:
        owner = doc.owner

    # Need to walk the tree; some protected resources have versions.

    while doc.replaces is not None:
        doc.readers = readers
        doc.writers = writers
        doc.owner = owner

        await doc.save()

        doc = doc.replaces

        if not hasattr(doc, "replaces"):
            link = doc
            doc = await link.fetch()

    # Base of tree that has no replacement
    doc.readers = readers
    doc.writers = writers
    doc.owner = owner

    await doc.save()

    # We use the classmethod on the _instance_ to get back the same
    # type that the doc is! Using ProtectedDocument.get() doesn't work.
    return await doc.get(initial_doc_id)


def check_user_access(
    user_groups: Iterable[str], document_groups: Iterable[str]
) -> bool:
    """
    Check whether a user (based on their groups) has access to a specific
    document based on its 'reader' or 'writer' group list (`document_groups`).

    Note that the group `admin` is always added to `allowed`.

    Raises
    ------
    AuthenticationError
        When there is no overlap between `user_groups` and `document_groups`
    """
    allowed = set(document_groups) | {"hippo:admin"}
    user_groups = set(user_groups)

    overlap = user_groups & allowed

    if overlap:
        return True

    raise AuthenticationError(
        "User does not have the required group access for this operation"
    )
