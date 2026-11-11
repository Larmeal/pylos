"""Sources describe where the data comes from. ``SourceConfig`` picks one from the ``storage`` field."""

from typing import Annotated

from pydantic import Field

from pylos.sources.gcs import GCSSourceConfig
from pylos.sources.local import LocalSourceConfig

SourceConfig = Annotated[
    LocalSourceConfig | GCSSourceConfig,
    Field(discriminator="storage"),
]
"""The ``source`` section of a config. Its ``storage`` field picks the class: ``local`` or ``gcs``."""
