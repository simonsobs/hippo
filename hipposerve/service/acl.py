"""
Access control setup (changing access control levels, checking
for access to documents). Works with `ProtectedDocument`s.
"""

from typing import Iterable, TypeVar

from beanie import BackLink, Link

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


def check_read_access(
    user_groups: Iterable[str],
    document: ProtectedDocument,
    scopes: Iterable[str],
) -> bool:
    """Allow reads of public documents and documents shared with the user's groups."""
    if "hippo:admin" in scopes or "public" in document.readers:
        return True

    groups = set(user_groups) - {"public"}
    if groups.intersection(document.readers) or groups.intersection(document.writers):
        return True

    raise AuthenticationError(
        "User does not have the required group access for this operation"
    )


DocumentT = TypeVar("DocumentT", bound=ProtectedDocument)


def filter_readable(
    documents: Iterable[DocumentT | Link[DocumentT] | BackLink[DocumentT]],
    groups: Iterable[str],
    scopes: Iterable[str],
) -> list[DocumentT]:
    """Filter hydrated relationships, omitting unresolved links."""
    readable = []
    for document in documents:
        if isinstance(document, (Link, BackLink)):
            continue
        try:
            check_read_access(groups, document, scopes)
        except AuthenticationError:
            continue
        readable.append(document)
    return readable


def check_write_access(
    user_groups: Iterable[str],
    document: ProtectedDocument,
    scopes: Iterable[str],
) -> bool:
    """Allow writes for members of writer groups and callers with admin scope."""
    if "hippo:admin" in scopes:
        return True

    groups = set(user_groups) - {"public"}
    if groups.intersection(document.writers):
        return True

    raise AuthenticationError(
        "User does not have the required group access for this operation"
    )


def build_access_query(
    user_groups: Iterable[str],
    scopes: Iterable[str],
) -> dict:
    """
    Build a MongoDB query to find documents that a user has access to
    based on their groups and scopes.

    Returns
    -------
    dict
        A MongoDB query dictionary that can be used to filter documents.
    """

    if "hippo:admin" in scopes:
        return {}

    groups = set(user_groups) - {"public"}
    return {
        "$or": [
            {"readers": {"$in": sorted(groups | {"public"})}},
            {"writers": {"$in": sorted(groups)}},
        ]
    }
