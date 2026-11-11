"""The storage backend for the local filesystem."""

from __future__ import annotations

import datetime
import logging
import shutil
import sys
from collections.abc import Iterable
from glob import glob as _fs_glob
from pathlib import Path
from typing import Literal

from pydantic import Field

from pylos.results import SourceObjectMetadata
from pylos.storages.base import BaseStorage

logger = logging.getLogger(__name__)


class LocalStorage(BaseStorage):
    """Files on the machine Pylos runs on. The OS performs every operation.

    It knows nothing about failure actions. It is given a source and a
    destination and moves the bytes; which file to move, where to, and what the
    outcome means are decided in ``actions.py``.
    """

    storage: Literal["local"] = Field(description="The storage backend type, such as 'local'")

    @staticmethod
    def _prepare(src: str, dst_dir: str) -> Path:
        """Create the destination directory and work out the target path.

        The moved file keeps its own name, so two source objects sharing a basename
        resolve to the same target. See ``move_obj`` for what that costs.

        Args:
            src: Path of the file about to be relocated.
            dst_dir: Directory to relocate it into. Created, parents included,
                if it does not already exist.

        Returns:
            The full destination path, which does not exist yet.

        Raises:
            OSError: If the directory cannot be created, most often
                ``PermissionError``, or ``NotADirectoryError`` when a file
                already occupies the path.
        """
        directory = Path(dst_dir)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / Path(src).name

    def _list_files(self, pattern: str) -> Iterable[Path]:
        """Expand a local glob, keeping only files.

        Relative and absolute patterns are both accepted, as is a recursive
        ``**``. A matching directory is skipped, so it never becomes a source
        object that cannot be read. Every path is resolved to an absolute one.

        Args:
            pattern: A local glob, e.g. ``data/test_*.csv``. A path with no
                wildcard matches only itself.

        Raises:
            FileNotFoundError: No file matches ``pattern``.
        """

        all_objects = _fs_glob(pattern, recursive=True)
        files = list(object.resolve() for object in map(Path, all_objects) if object.is_file())
        logger.debug("found %d file(s):\n%s", len(files), "\n".join(f"  - {file}" for file in files))

        if not files:
            raise FileNotFoundError(f"No files matched the pattern: {pattern}")
        return files

    def _to_metadata(self, entry: Path) -> SourceObjectMetadata:
        """Read size, creation time and mtime from a single ``os.stat`` call.

        The path is stored as an absolute, resolved path, which is the
        ``source_object`` key the report is written under.

        ``created_at`` is exact where the OS records a creation time:
        ``st_birthtime`` (macOS, BSD, and Windows on Python 3.12+), or ``st_ctime``
        on Windows, where it is the creation time. Elsewhere (Linux) ``st_ctime``
        means "last metadata change" and moves when the file is renamed or chmod'ed,
        so it is not used; ``created_at`` falls back to the modification time.

        Raises:
            OSError: If the file cannot be stat'd, most often because it vanished
                between the listing and this call.
        """
        stat = entry.stat()
        birth = getattr(stat, "st_birthtime", None)
        if birth is None and sys.platform == "win32":
            birth = stat.st_ctime
        modified_at = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC)
        return SourceObjectMetadata(
            path=str(Path(entry).resolve()),
            size_bytes=stat.st_size,
            created_at=datetime.datetime.fromtimestamp(birth, tz=datetime.UTC) if birth is not None else modified_at,
            modified_at=modified_at,
        )

    def move_obj(self, src: str, dst_dir: str) -> str:
        """Move a file into a directory, letting the OS perform the move.

        Within one filesystem this is a rename and therefore atomic; across
        devices ``shutil`` degrades to copy-then-delete, which can leave the file
        in both places if the delete fails.

        Note:
            The destination keeps the source's file name, so moving
            ``2026-08-15/orders.csv`` and ``2026-08-16/orders.csv`` into the same
            directory leaves only the second, silently, on both Windows and
            POSIX. Callers that dead-letter files from more than one directory
            should pass a distinct ``dst_dir`` per run.

        Args:
            src: Path of the file to move.
            dst_dir: Directory to move it into. Created if absent.

        Returns:
            The full path of the moved file, for the report to record beside the
            original.

        Raises:
            OSError: If the source cannot be read or the destination written.
        """
        dest = self._prepare(src, dst_dir)
        shutil.move(src, dest)
        logger.info("moved %s -> %s", src, dest)
        return str(dest)

    def copy_obj(self, src: str, dst_dir: str) -> str:
        """Copy a file into a directory, leaving the original in place.

        Metadata is preserved (``shutil.copy2``), so the copy keeps the
        modification time the pipeline may have selected the file by.

        Note:
            Overwrites an existing file of the same name, as ``move_obj``
            does.

        Args:
            src: Path of the file to copy.
            dst_dir: Directory to copy it into. Created if absent.

        Returns:
            The full path of the copy.

        Raises:
            OSError: If the source cannot be read or the destination written.
        """
        dest = self._prepare(src, dst_dir)
        shutil.copy2(src, dest)
        logger.info("copied %s -> %s", src, dest)
        return str(dest)

    def delete_obj(self, src: str) -> None:
        """Delete a file, treating one that is already gone as success.

        A re-run after a crash mid-action can find the file already deleted by
        the previous attempt. Raising there would abort a run over a file that is
        already in the requested state, so a missing file is logged and accepted.
        The report records whether the first attempt got this far.

        Args:
            src: Path of the file to delete.

        Raises:
            OSError: If the file exists but cannot be removed, such as
                ``PermissionError`` when another process holds it open.
        """
        path = Path(src)
        if not path.exists():
            logger.warning("nothing to delete at %s; it may already be gone", src)
            return
        path.unlink()
        logger.info("deleted %s", src)
