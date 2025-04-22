"""
The storage access layer for hippo. Assumes that you have an S3-compatible backend,
and uses the MinIO tools.
"""

import datetime
import os
from math import ceil

from loguru import logger
from minio import Minio
from minio.api import Part, genheaders
from minio.error import S3Error
from pydantic import BaseModel, ConfigDict


def replace_host(url: str, old: str, new: str | None, upgrade: bool) -> str:
    """
    Replaces the host in a URL.
    """

    if new is not None:
        url = url.replace(old, new)

    if upgrade:
        url = url.replace("http://", "https://")

    return url


class Storage(BaseModel):
    url: str
    access_key: str
    secret_key: str
    presign_url: str | None = None

    upgrade_presign_url_to_https: bool = False
    secure: bool = False
    cert_check: bool = False

    client: Minio | None = None
    expires: datetime.timedelta = datetime.timedelta(days=1)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_post_init(self, __context):
        self.client = Minio(
            self.url,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
            cert_check=self.cert_check,
        )

    def object_name(self, filename: str, uploader: str, uuid: str) -> str:
        # Filename may contain some kind of path, and this
        # breaks the download side of things, but for some
        # reason this is a valid object name for uploads?
        return f"{uploader}/{uuid}/{os.path.basename(filename)}"

    def bucket(self, name: str):
        if not self.client.bucket_exists(name):
            self.client.make_bucket(name)

        return

    def put(
        self, name: str, uploader: str, uuid: str, bucket: str, size: int, batch: int
    ) -> tuple[str, list[str]]:
        """
        Initiates a multipart upload. Returns a list of pre-signed URLs and the
        upload ID. Each one of these URLs should have ``batch`` data uploaded to
        it.

        Returns
        -------
        upload_id : str
            The upload ID for the multipart upload.
        urls : list[str]
            A list of pre-signed URLs to upload data to.
        """

        self.bucket(name=bucket)

        object_name = self.object_name(
            filename=name,
            uploader=uploader,
            uuid=uuid,
        )

        # First - initiate the multipart upload to get the UploadID.
        upload_id = self.client._create_multipart_upload(
            bucket_name=bucket,
            object_name=object_name,
            headers=genheaders(None, None, None, None, None),
        )

        # Second - generate n pre-signed URLs for each part.
        urls = [
            replace_host(
                url=self.client.get_presigned_url(
                    method="PUT",
                    bucket_name=bucket,
                    object_name=object_name,
                    expires=self.expires,
                    # Parts must use one-based indexing (s3 requirement)
                    extra_query_params={
                        "partNumber": str(i + 1),
                        "uploadId": upload_id,
                    },
                ),
                old=self.url,
                new=self.presign_url,
                upgrade=self.upgrade_presign_url_to_https,
            )
            for i in range(int(ceil(size / batch)))
        ]

        return upload_id, urls

    def complete(
        self,
        name: str,
        uploader: str,
        uuid: str,
        bucket: str,
        upload_id: str,
        headers: list[dict[str, str]],
        sizes: list[int],
    ) -> None:
        """
        Completion after a multipart upload. If this doesn't occur, a multipart upload will not
        succeed. Requires information from the client (list[Part]) that uploaded the data.
        """

        self.bucket(bucket)

        self.client._complete_multipart_upload(
            bucket_name=bucket,
            object_name=self.object_name(
                filename=name,
                uploader=uploader,
                uuid=uuid,
            ),
            upload_id=upload_id,
            parts=[
                # Sometimes the s3 server responds with ETag, sometimes etag. Lol.
                Part(
                    part_number=i + 1,
                    etag={x.lower(): y for x, y in headers[i].items()}["etag"],
                    size=sizes[i],
                )
                for i in range(len(headers))
            ],
        )

    def confirm(self, name: str, uploader: str, uuid: str, bucket: str) -> bool:
        """
        Checks whether an object exists.
        """

        self.bucket(name=bucket)

        try:
            self.client.get_object_tags(
                bucket_name=bucket,
                object_name=self.object_name(
                    filename=name,
                    uploader=uploader,
                    uuid=uuid,
                ),
            )

            logger.debug(
                f"Object {self.object_name(filename=name, uploader=uploader, uuid=uuid)} exists."
            )

            return True
        except S3Error as e:
            logger.info(e)
            return False

    def get(self, name: str, uploader: str, uuid: str, bucket: str) -> str:
        """
        Returns a specific URL for HTTP GET requests.
        """

        self.bucket(name=bucket)

        base_url = self.client.presigned_get_object(
            bucket_name=bucket,
            object_name=self.object_name(
                filename=name,
                uploader=uploader,
                uuid=uuid,
            ),
            expires=self.expires,
        )

        return replace_host(
            base_url,
            old=self.url,
            new=self.presign_url,
            upgrade=self.upgrade_presign_url_to_https,
        )

    def delete(self, name: str, uploader: str, uuid: str, bucket: str) -> str:
        """
        Deletes an object from the bucket.
        """

        self.client.remove_object(
            bucket_name=bucket,
            object_name=self.object_name(
                filename=name,
                uploader=uploader,
                uuid=uuid,
            ),
        )
