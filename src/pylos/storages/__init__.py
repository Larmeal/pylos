"""Storage backends list, move, copy and delete files in the place that holds them."""

from typing import Annotated

from pydantic import Field

from pylos.storages.local import LocalStorage

StorageBackend = Annotated[
    LocalStorage,
    Field(discriminator="storage"),
]
"""Any storage backend. Its ``storage`` field picks the class, and only ``local`` exists so far."""

__all__ = ["StorageBackend", "LocalStorage"]
