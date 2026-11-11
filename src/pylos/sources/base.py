"""The fields every source shares."""

from __future__ import annotations

from abc import ABC
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BaseConfig(BaseModel, ABC):
    """Base for every source configuration.

    Forbids unknown fields, so a typo in the ``source`` block fails at load
    instead of being silently dropped.
    """

    model_config = ConfigDict(extra="forbid")


class FileBaseConfig(BaseConfig):
    """Fields every file-based source shares, whatever storage backend it uses.

    Attributes:
        file_format: The format of the file (e.g., 'csv', 'parquet', 'json').
        file_path: The path or URI to the data.
        on_empty: Whether the glob matching no files is an error or a normal day.
        options: Additional engine-specific reading options (e.g., delimiter, header).
    """

    file_format: str = Field(description="The format of the source file (e.g., 'csv', 'parquet', 'json').")
    file_path: str = Field(description="The path or URI pointing to the source data file including file name.")
    on_empty: Literal["fail", "skip"] = Field(
        default="skip",
        description=(
            "What it means when the glob matches no files at all. Pylos cannot tell "
            "'nothing arrived today, which is normal' apart from 'the upstream job did not run', "
            "so the declaration has to say which one it is. A report is written either way. "
            "This is a run-level event and has nothing to do with a file that is found but holds "
            "zero rows: that is recorded on the source object as a warning."
        ),
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Additional engine-specific reading options, passed straight to the engine's reader. "
            "Any option the underlying reader supports works here. "
            "For CSV files in pandas this goes to ``pd.read_csv``, so ``{delimiter: ',', header: 0}`` is valid. "
            "See https://pandas.pydata.org/docs/reference/io.html for the pandas reader options."
        ),
    )
