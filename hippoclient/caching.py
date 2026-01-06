"""
The caching layer for sources used by the hippo client.

A cache is:

a) A directory on your filesystem
b) A set of files in that directory
c) A SQLite database that stores metadata about the files
   that are being cached.

Because marshalling is so simple here we do not use
SQLAlchemy or any other ORM. We just use the built-in
Python sqlite3 module.
"""

import os
import shutil
import sqlite3
from pathlib import Path

from pydantic import BaseModel, PrivateAttr
from rich.console import Console

from hippoclient.downloads import downloader
from hipposerve.database import FileMetadata


class CacheNotWriteableError(Exception):
    """
    Raised when the cache is not writeable.
    """

    def __init__(self):
        super().__init__("The cache is not writeable")


class Cache(BaseModel):
    """
    A cache for sources used by the hippo client. All sources are labelled by their
    unique UUID, given by the main mongodb database (note this is not _id).

    The general execution flow when using a (set of) cache(s) is:

    1. Check if the file is in the cache with ``available``. If it is, you will be
       immediately given the on-disk path to the file. If not, we will raise a
       FileNotFoundError.
    2. Check the other caches if it is not available.
    3. Attain a pre-signed URL for your source.
    4. Fetch the source from the pre-signed URL with your preferred cache with ``get``.
       This will return you an on-disk path to the downloaded source within your cache
       area. You can check which caches are writeable with ``writeable``.

    So for a list of caches, you would do something like:

    .. code-block::python

        MY_FILE_ID = "123456789012345678901234"
        path: Path | None = None

        for cache in caches:
            try:
                path = cache.available(MY_FILE_ID)
                break
            except FileNotFoundError:
                continue

        if path is None:
            for cache in filter(lambda c: c.writeable, caches):
                try:
                    path = cache.get(
                        id=MY_FILE_ID,
                        path="path/to/file",
                        checksum="checksum",
                        size=1234,
                        presigned_url="https://example.com/presigned-url",
                    )
                    break
                except {SOME EXCEPTION}:
                    continue

        if path is None:
            raise FileNotFoundError

    There are a number of utilities implemented in the MultiCache object that perform
    these kind of duties for you.
    """

    path: Path
    database_name: str = "cache.db"

    _database: Path = PrivateAttr()
    _connection: sqlite3.Connection = PrivateAttr()

    def model_post_init(self, __context):
        self._database = self.path / self.database_name
        self._connection = self._initialize_database()

    def _initialize_database(self) -> sqlite3.Connection:
        """
        Initialize the cache database.
        """

        if self._database.exists():
            return sqlite3.connect(self._database)
        else:
            # Create the database
            connection = sqlite3.connect(self._database)

            cursor = connection.cursor()
            cursor.execute(
                "CREATE TABLE sources (id PRIMARY KEY, path, checksum, size, available)"
            )
            connection.commit()

            return connection

    @property
    def writeable(self) -> bool:
        """
        Check if the cache is writeable.
        """

        return os.access(self._database, os.W_OK)

    def _add(self, id: str, path: str, checksum: str, size: int):
        """
        Add a source to the cache. Initially marks it as unavailable. This should
        be called _before_ downloading the actual source.
        """

        cursor = self._connection.cursor()
        cursor.execute(
            "INSERT INTO sources (id, path, checksum, size, available) VALUES (?, ?, ?, ?, ?)",
            (str(id), str(path), str(checksum), int(size), False),
        )
        self._connection.commit()

    def _mark_available(self, id: str):
        """
        Mark a source as available.
        """

        cursor = self._connection.cursor()
        cursor.execute(
            "UPDATE sources SET available = ? WHERE id = ?",
            (True, str(id)),
        )
        self._connection.commit()

    def _mark_unavailable(self, id: str):
        """
        Mark a source as unavailable.
        """

        cursor = self._connection.cursor()
        cursor.execute(
            "UPDATE sources SET available = ? WHERE id = ?",
            (False, str(id)),
        )
        self._connection.commit()

    def _get(self, id: str) -> Path | None:
        """
        Get a source from the cache. Or, if it's not available, return None.
        If it is available we return the absolute path on the system to the file.
        """

        cursor = self._connection.cursor()

        cursor.execute(
            "SELECT path FROM sources WHERE id = ? AND available = ?",
            (str(id), True),
        )

        result = cursor.fetchone()

        if result is None:
            return None
        else:
            return self.path / Path(result[0])

    def _remove(self, id: str):
        """
        Remove a source from the cache.
        """

        # Get it first, if it's there then we need to delete it.
        path = self._get(id)

        if path is not None:
            path.unlink()

        cursor = self._connection.cursor()
        cursor.execute(
            "DELETE FROM sources WHERE id = ?",
            (str(id),),
        )
        self._connection.commit()

    def _fetch(
        self, id: str, path: str, checksum: str, size: int, presigned_url: str
    ) -> Path:
        """
        Fetch a source from the presigned URL we are provided, store it in
        the cache, and return the path to the file.

        Parameters
        ----------
        id : str
            The ID of the source
        path : str
            The path to the source
        checksum : str
            The checksum of the source
        size : int
            The size of the source
        presigned_url : str
            The presigned URL to fetch the source from

        Returns
        -------
        Path
            The path to the source in the cache

        Raises
        ------
        CacheNotWriteableError
            If the cache is not writeable
        """

        if not self.writeable:
            raise CacheNotWriteableError

        try:
            self._add(id=id, path=path, checksum=checksum, size=size)

            # Download the file
            destination_path = self.path / Path(path)
            destination_path.parent.mkdir(parents=True, exist_ok=True)

            downloader(
                presigned_url=presigned_url,
                output_destination=destination_path,
                console=Console(),
            )

            self._mark_available(id)
        except BaseException as e:
            # Atomic! Not super threadsafe but this is sqlite anyway. Usually when someone kills this
            # with a KeyboardInterrupt -- we don't wanna leave dangling db items. We could probably handle
            # this with an actual transaction...
            self._remove(id=id)
            try:
                shutil.rmtree(destination_path)
            except NotADirectoryError:
                os.remove(destination_path)
            except FileNotFoundError:
                pass
            raise e

        return destination_path

    def get(
        self, id: str, path: str, checksum: str, size: int, presigned_url: str
    ) -> Path:
        """
        Get a source from the cache. If it's not available, fetch it from the
        presigned URL and store it in the cache.

        Parameters
        ----------
        id : str
            The ID of the source
        path : str
            The path to the source
        checksum : str
            The checksum of the source
        size : int
            The size of the source
        presigned_url : str
            The presigned URL to fetch the source from, if it not in the cache.
        """

        cached = self._get(id)

        if cached is not None:
            return cached
        else:
            return self._fetch(
                id=id,
                path=path,
                checksum=checksum,
                size=size,
                presigned_url=presigned_url,
            )

    def available(self, id: str) -> Path:
        """
        Check if a source is available in the cache with id ``id``.
        If it is, we return the Path. If not, we raise a FileNotFoundError.

        Parameters
        ----------
        id : str
            The ID of the source

        Returns
        -------
        Path
            The path to the source in the cache

        Raises
        ------
        FileNotFoundError
            If the source is not available in the cache
        """

        path = self._get(id)

        if path is None:
            raise FileNotFoundError

        return path

    @property
    def complete_id_list(self) -> list[str]:
        """
        List all the IDs in the cache
        """

        cursor = self._connection.cursor()
        cursor.execute("SELECT id FROM sources")

        return [row[0] for row in cursor.fetchall()]


class MultiCache(BaseModel):
    """
    An interface to multiple caches. There is one main rule:

    Caches are ordered by priority. We will always try the first caches in
    the list first, and files will be ingested on a first-cache-first-served
    basis.
    """

    caches: list[Cache]

    def available(self, id: str) -> Path:
        """
        Check if a source is available in any cache with id ``id``.
        If it is, we return the Path. If not, we raise a FileNotFoundError.

        Parameters
        ----------
        id : str
            The ID of the source

        Returns
        -------
        Path
            The path to the source in the cache

        Raises
        ------
        FileNotFoundError
            If the source is not available in the cache
        """

        for cache in self.caches:
            try:
                return cache.available(id)
            except FileNotFoundError:
                continue

        raise FileNotFoundError

    def get(self, id: str, path: str, checksum: str, size: int, presigned_url: str):
        """
        Get and store an item in the cache. You should likely use this only after
        ``available`` has raised a FileNotFoundError.

        Parameters
        ----------
        id : str
            The ID of the source
        path : str
            The path to the source
        checksum : str
            The checksum of the source
        size : int
            The size of the source
        presigned_url : str
            The presigned URL to fetch the source from, if it not in the cache.

        Returns
        -------
        Path
            The path to the source in the cache

        Raises
        ------
        CacheNotWriteableError
            If no caches are writeable
        """

        for cache in self.caches:
            if cache.writeable:
                return cache.get(
                    id=id,
                    path=path,
                    checksum=checksum,
                    size=size,
                    presigned_url=presigned_url,
                )

        raise CacheNotWriteableError

    def remove(self, id: str):
        """
        Remove a source from all caches.
        """

        for cache in self.caches:
            cache._remove(id)

    def names_to_paths(self, file_metadata: list[FileMetadata]) -> dict[str, Path]:
        """
        Convert a list of FileMetadata objects to a dictionary of names to paths.
        """

        paths = {}

        for cache in self.caches:
            for file in file_metadata:
                path = cache.available(file.uuid)
                paths[file.name] = path

        return paths

    def uuids_to_paths(self, file_metadata: list[FileMetadata]) -> dict[str, Path]:
        """
        Convert a list of FileMetadata objects to a dictionary of UUIDs to paths.
        """

        paths = {}

        for cache in self.caches:
            for file in file_metadata:
                path = cache.available(file.uuid)
                paths[file.uuid] = path

        return paths


def clear_all(cache: Cache):
    """
    Clear all the caches.
    """

    for file in cache.complete_id_list:
        cache._remove(file)


def clear_single(cache: Cache, id: str):
    """
    Clear a single cached item.
    """

    cache._remove(id)
