"""Report sinks, which are the places a run's result is written. ``SinkConfig`` picks one from the ``storage`` field."""

from typing import Annotated

from pydantic import Field

from pylos.sinks.base import BaseFileFormat, BaseTableFormat
from pylos.sinks.bigquery import BigQuerySink
from pylos.sinks.gcs import GCSSink
from pylos.sinks.local import LocalSink

SinkConfig = Annotated[
    GCSSink | BigQuerySink | LocalSink,
    Field(discriminator="storage"),
]
"""The ``report`` section of a config. Its ``storage`` field picks the class: ``gcs``, ``bigquery`` or ``local``."""

__all__ = ["SinkConfig", "BigQuerySink", "GCSSink", "LocalSink", "BaseFileFormat", "BaseTableFormat"]
