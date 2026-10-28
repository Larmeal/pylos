"""The interface every storage backend implements."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable

from pydantic import BaseModel

from pylos.results import SourceObjectMetadata

_DIGITS = re.compile(r"(\d+)")


def _natural_key(path: str) -> tuple[list[str | int], str]:
    """Sort key that orders paths a-z, ignoring case, with runs of digits compared as numbers.

    ``test_2.csv`` sorts before ``test_10.csv``. ``re.split`` with a capturing group always
    returns text and number pieces in alternating positions, so two keys never compare a
    ``str`` with an ``int``. The raw path is the tie-breaker, so ``test_01`` and ``test_1``
    (equal as numbers) still sort the same way every run.
    """
    pieces = _DIGITS.split(path.casefold())
    return [int(piece) if index % 2 else piece for index, piece in enumerate(pieces)], path


class BaseStorage(BaseModel, ABC):
    """Interface for file operations on a storage backend.

    One subclass per backend (local disk, GCS, S3), each implemented with that
    backend's own SDK. ``glob`` resolves a source pattern into the files a run
    will process, each with the size and mtime the planner renders.
    ``move_obj``, ``copy_obj`` and ``delete_obj`` relocate or remove a file after
    validation fails.

    Reading is not part of this interface: engines read by URI with their own
    readers.

    Paths are URIs in whatever form the backend uses: filesystem paths for local
    storage, ``gs://bucket/key`` for GCS.
    """

    def glob(self, pattern: str) -> list[SourceObjectMetadata]:
        """Resolve a pattern into the objects it matches, metadata included.

        A template method. The shape of the result is fixed here so every backend
        agrees on it: sorted by ``path`` for a reproducible processing order, with
        no directories. The order is a-z ignoring case, with numbers compared by
        value (``test_2`` before ``test_10``). Backends supply the two halves:
        ``_list_files`` walks the backend, and ``_to_metadata`` turns one native
        entry into a ``SourceObjectMetadata``.

        Args:
            pattern: A glob in the backend's syntax, such as ``data/test_*.csv``.
                A pattern containing no wildcard matches only itself.

        Returns:
            The matching objects, sorted by ``path`` in natural order. Empty when
            nothing matches, which ``source.on_empty`` assigns meaning to.
        """
        return sorted(
            (self._to_metadata(entry) for entry in self._list_files(pattern)),
            key=lambda meta: _natural_key(meta.path),
        )

    @abstractmethod
    def _list_files(self, pattern: str) -> Iterable[object]:
        """Yield one backend-native entry per matching file.

        Directories are excluded here, not downstream. The entry type is the
        backend's own (a ``Path`` for local disk, a ``Blob`` for GCS) and is
        only ever consumed by this backend's ``_to_metadata``, which narrows it.
        """

    @abstractmethod
    def _to_metadata(self, entry: object) -> SourceObjectMetadata:
        """Map one entry from ``_list_files`` to a ``SourceObjectMetadata``.

        Must populate ``path``, ``size_bytes``, ``created_at`` and ``modified_at``.
        A backend that cannot report a creation time uses the modification time
        instead of leaving ``created_at`` empty. The entry already carries what is
        needed (a GCS ``Blob`` from a listing has ``size``, ``time_created`` and
        ``updated`` on it), so this never makes another request.
        """

    @abstractmethod
    def move_obj(self, src: str, dst_dir: str) -> str:
        """Move a file into a directory.

        The file keeps its own name at the destination, and the directory is
        created if it does not exist.

        Args:
            src: URI of the file to move.
            dst_dir: URI of the directory to move it into.

        Returns:
            The full URI of the moved file.
        """

    @abstractmethod
    def copy_obj(self, src: str, dst_dir: str) -> str:
        """Copy a file into a directory, leaving the original in place.

        The copy keeps the source's name, and the directory is created if it does
        not exist.

        Args:
            src: URI of the file to copy.
            dst_dir: URI of the directory to copy it into.

        Returns:
            The full URI of the copy.
        """

    @abstractmethod
    def delete_obj(self, uri: str) -> None:
        """Delete a file.

        A file that is already absent is not an error.

        Args:
            uri: URI of the file to delete.
        """
