"""The base classes every report sink builds on."""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

from pylos.results import PylosResult


class BaseSink(ABC, BaseModel):
    """Base for every report sink: a place a run's ``PylosResult`` is written.

    The ``report.storage`` field picks the concrete class (see ``SinkConfig``).
    Subclasses implement ``_handle``, which turns the result into the sink's
    payload, and ``write_sink``, which writes that payload.
    """

    @abstractmethod
    def _handle(self) -> None:
        """Turn the result into the payload this sink writes."""
        pass

    @abstractmethod
    def write_sink(self, result: PylosResult) -> None:
        """Write the run's result to this sink."""
        pass


class BaseFileFormat(BaseSink):
    """Base for sinks that write the report as a file at ``path``. ``format`` must be ``"file"``."""

    format: Literal["file"] = Field(
        description="Report format, fixed to 'file': the report is written as one file at ``path``."
    )
    path: str = Field(description="Path to store the report file.")


class BaseTableFormat(BaseSink):
    """Base for sinks that write the report as rows in a table. ``format`` must be ``"table"``."""

    format: Literal["table"] = Field(
        description="Report format, fixed to 'table': the report is written as rows in a table."
    )
