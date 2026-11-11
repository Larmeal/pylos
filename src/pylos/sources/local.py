"""The local filesystem source."""

from __future__ import annotations

import logging
from functools import cached_property
from typing import Literal

from pydantic import Field, field_validator

from pylos.sources.base import FileBaseConfig
from pylos.storages.local import LocalStorage

logger = logging.getLogger(__name__)


class LocalSourceConfig(FileBaseConfig):
    """Configuration for a local file source.

    Attributes:
        storage: The storage backend type, fixed to 'local'.
        file_format: The format of the file (e.g., 'csv', 'parquet').
        file_path: The local path to the data.
        options: Additional reading options (e.g., delimiter, header rules).
    """

    storage: Literal["local"] = Field(description="Storage backend type, fixed to 'local'.")

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        """Reject a path that contains a URI scheme (``://``), such as ``gs://...``.

        Whether the path matches any files is not checked here; that happens
        when the glob is resolved.

        Args:
            value (str): The local file path to validate.

        Raises:
            ValueError: The path contains ``://``.
        """

        if "://" in value:
            raise ValueError(f"The provided file path '{value}' is not a valid local path.")
        return value

    @cached_property
    def backend(self) -> LocalStorage:
        """The local filesystem backend, built once per source."""

        return LocalStorage(storage=self.storage)
