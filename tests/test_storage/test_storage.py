"""
Individual (fully synchronous) storage tests.
"""

import pytest
import requests

from hipposerve.storage import Storage


@pytest.fixture(scope="session")
def simple_uploaded_file(storage):
    # Ingest the file into the storage service.
    file_info = {
        "name": "test_file.txt",
        "uploader": "test_uploader",
        "uuid": "1234-1234-1234",
        "bucket": "testbucket",
    }

    uid, put = storage.put(**file_info, size=1234, batch=1234 * 2)

    # Put is a pre-signed URL. We've gotta HTTP upload it.

    headers = [requests.put(put[0], data=b"\x00" * 1234).headers]
    sizes = [1234]

    # Complete the upload.
    storage.complete(
        **file_info,
        headers=headers,
        sizes=sizes,
        upload_id=uid,
    )

    yield file_info

    # Remove it! Request a deletion.
    storage.delete(**file_info)


def test_simple_uploaded_file(simple_uploaded_file, storage):
    get = storage.get(**simple_uploaded_file)

    # Try to download it.
    response = requests.get(get)
    assert response.status_code == 200

    # Check the contents.
    assert response.content == b"\x00" * 1234


def test_existing_object(simple_uploaded_file, storage):
    assert storage.confirm(**simple_uploaded_file)


def test_non_existing_object(storage):
    assert not storage.confirm(
        name="non_existing_file.txt",
        uploader="test_uploader",
        uuid="1234-1234-1234",
        bucket="testbucket",
    )


def test_storage_url_replacement(simple_uploaded_file, storage):
    # Get a new Storage object, with a different presign_url.
    new_storage = Storage(
        url=storage.url,
        access_key=storage.access_key,
        secret_key=storage.secret_key,
        presign_url="example.com",
        upgrade_presign_url_to_https=True,
    )

    get = new_storage.get(**simple_uploaded_file)

    assert "example.com" in get
    assert "https://" in get
