"""
Service drivers for interacting with the storage layer.
"""

import os
import uuid
from math import ceil

from asyncer import asyncify

from hipposerve.database import File
from hipposerve.storage import Storage


# TODO: Settings
def UUID():
    return str(uuid.uuid4())


GLOBAL_BUCKET_NAME = "global"


async def create(
    name: str,
    description: str | None,
    uploader: str,
    size: int,
    checksum: str,
    storage: Storage,
    multipart_size: int = 50 * 1024 * 1024,
) -> tuple[File, str]:
    # All uploads are now multipart.
    multipart = True
    number_of_parts = int(ceil(size / multipart_size))
    uuid = UUID()

    upload_id, put = await asyncify(storage.put)(
        name=name,
        uploader=uploader,
        uuid=uuid,
        bucket=GLOBAL_BUCKET_NAME,
        size=size,
        batch=multipart_size,
    )

    file = File(
        # Strip any paths that were passed to us through
        # the layers, just in case.
        name=os.path.basename(name),
        description=description,
        uploader=uploader,
        uuid=uuid,
        bucket=GLOBAL_BUCKET_NAME,
        size=size,
        checksum=checksum,
        multipart=multipart,
        number_of_parts=number_of_parts,
        upload_id=upload_id,
        multipart_batch_size=multipart_size,
        multipart_closed=not multipart,
    )

    return file, put


async def complete(
    file: File,
    storage: Storage,
    response_headers: list[dict[str, str]],
    sizes: list[int],
):
    """
    Multipart uploads must come with a complete step, including responses from
    the storage server along the way.
    """

    await asyncify(storage.complete)(
        name=file.name,
        uploader=file.uploader,
        uuid=file.uuid,
        bucket=file.bucket,
        upload_id=file.upload_id,
        headers=response_headers,
        sizes=sizes,
    )

    return


async def confirm(file: File, storage: Storage) -> bool:
    return await asyncify(storage.confirm)(
        name=file.name, uploader=file.uploader, uuid=file.uuid, bucket=file.bucket
    )


async def read(
    file: File,
    storage: Storage,
) -> str:
    return await asyncify(storage.get)(
        name=file.name, uploader=file.uploader, uuid=file.uuid, bucket=file.bucket
    )


async def delete(
    file: File,
    storage: Storage,
):
    await asyncify(storage.delete)(
        name=file.name, uploader=file.uploader, uuid=file.uuid, bucket=file.bucket
    )
    return
