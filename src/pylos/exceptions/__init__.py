"""The errors Pylos raises. Catch ``PylosError`` to handle anything Pylos is responsible for."""

from .base import ConfigurationError, DataError, PylosError
from .data_error import SourceEmptyError

__all__ = ["PylosError", "ConfigurationError", "DataError", "SourceEmptyError"]
