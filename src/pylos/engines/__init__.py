"""Engines read each source file into memory and run the checks. Only ``pandas`` exists so far."""

from typing import Annotated

from pydantic import Field

from pylos.engines.base import BaseEngine
from pylos.engines.pandas import PandasEngine

Engine = Annotated[
    PandasEngine,
    Field(discriminator="engine"),
]
"""A whole config file. Its ``engine`` field picks the class, and only ``pandas`` exists so far."""

__all__ = ["PandasEngine", "BaseEngine"]
