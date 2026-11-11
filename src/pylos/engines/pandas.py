"""The pandas engine, which reads each CSV file into a DataFrame."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal, Self

import pandas as pd
from pydantic import Field

from pylos.engines.base import BaseEngine
from pylos.exceptions.data_error import SourceEmptyError

logger = logging.getLogger(__name__)


class PandasEngine(BaseEngine):
    """Engine that reads each source object into a pandas DataFrame."""

    engine: Literal["pandas"] = Field(
        description="Engine identifier, fixed to 'pandas'. Reads each source object with pandas."
    )
    dataframe: pd.DataFrame | None = None

    def is_empty(self) -> bool:
        """Whether there is no data to validate.

        Returns:
            True when the dataframe has no rows or no columns
            (``DataFrame.empty``), or when nothing has been loaded yet.
        """
        return self.dataframe.empty if self.dataframe is not None else True

    def statistics(self) -> dict[str, Any]:
        """The loaded dataframe's shape and column names, for the report.

        Returns:
            ``row_count``, ``column_count``, and ``columns`` (the column names,
            in file order).

        Raises:
            AssertionError: Called before ``load_data``.
        """
        assert self.dataframe is not None
        return {
            "row_count": self.dataframe.shape[0],
            "column_count": self.dataframe.shape[1],
            "columns": self.dataframe.columns.tolist(),
        }

    def load_data(self, file_path: str | Path) -> Self:
        """Read one source object into ``self.dataframe`` with pandas.

        Only CSV is supported so far. ``source.options`` is passed straight to
        ``pd.read_csv``, so any pandas reader option works there. After reading,
        the frame is checked for emptiness.

        Args:
            file_path: Path or URI of the object to read, usually one entry from
                the storage glob.

        Returns:
            ``self``, so the caller can chain ``statistics()`` on the loaded data.

        Raises:
            SourceEmptyError: The file has no content at all (zero bytes, no
                header), or it parsed but has no rows. Only the second case
                carries the row and column counts.
            ValueError: ``source.file_format`` is not ``csv``.
        """
        logger.debug("loading %s as %s with options %s", file_path, self.source.file_format, self.source.options)

        match self.source.file_format:
            case "csv":
                try:
                    self.dataframe = pd.read_csv(file_path, **self.source.options)
                except pd.errors.EmptyDataError as e:
                    raise SourceEmptyError(f"{file_path} has no content to read") from e
            case _:
                raise ValueError(f"Unsupported source type: {self.source.file_format}")

        assert self.dataframe is not None
        logger.info("loaded %s: %d row(s), %d column(s)", file_path, self.dataframe.shape[0], self.dataframe.shape[1])

        self._validate_on_empty(row_count=self.dataframe.shape[0], column_count=self.dataframe.shape[1])
        return self
