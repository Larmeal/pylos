"""The Google Cloud Storage report sink. Planned, not usable yet."""

from typing import Literal

from pydantic import Field

from pylos.sinks.base import BaseFileFormat


class GCSSink(BaseFileFormat):
    """Report sink for a file in a GCS bucket. Not implemented yet.

    It does not implement ``_handle`` or ``write_sink`` yet, so a config with
    ``report.storage: gcs`` fails at load with ``TypeError: Can't instantiate
    abstract class``.
    """

    storage: Literal["gcs"] = Field(description="Storage backend type, fixed to 'gcs'.")

    def handle(self) -> None:
        """Placeholder that always raises ``NotImplementedError``. Not part of the ``BaseSink`` interface."""
        raise NotImplementedError("Handle method must be implemented by the subclass.")
