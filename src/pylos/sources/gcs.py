"""The Google Cloud Storage source. Planned, not usable yet."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Literal

from pydantic import Field, field_validator

from pylos.sources.base import FileBaseConfig

if TYPE_CHECKING:
    from pylos.storages import StorageBackend


class GCSSourceConfig(FileBaseConfig):
    """Configuration for a Google Cloud Storage source.

    Attributes:
        storage: The storage backend type, fixed to 'gcs'.
        file_format: The format of the file (e.g., 'csv', 'parquet').
        file_path: The URI to the data in GCS (e.g., 'gs://bucket_name/path/to/file').
        options: Additional reading options (e.g., delimiter, header rules).
    """

    storage: Literal["gcs"] = Field(description="Storage backend type, fixed to 'gcs'.")

    @field_validator("file_path")
    @classmethod
    def validate_gcs_path(cls, value: str) -> str:
        """Check that the GCS file path starts with 'gs://'.

        Args:
            value (str): The GCS file path to validate.

        Returns:
            str: The validated GCS file path.

        Raises:
            ValueError: If the GCS file path does not start with 'gs://'.
        """
        if not value.startswith("gs://"):
            raise ValueError(f"The provided file path '{value}' is not a valid GCS path. It must start with 'gs://'.")
        return value

    @cached_property
    def backend(self) -> StorageBackend:
        """Not available yet: GCS storage lands in v0.2."""
        raise NotImplementedError("GCS storage is not implemented yet; it lands in v0.2.")
