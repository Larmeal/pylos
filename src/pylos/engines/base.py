"""The shape every config file shares: ``id``, ``source``, ``validation``, ``on_failure`` and ``report``. Each engine subclasses ``BaseEngine``."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pylos.actions import DeleteFailureAction, IgnoreFailureAction, OnFailureActionConfig, RelocateFailureAction
from pylos.exceptions.data_error import SourceEmptyError
from pylos.gx.models import GXConfig
from pylos.sinks import SinkConfig
from pylos.sources import SourceConfig

if TYPE_CHECKING:
    pass


class BaseEngine(BaseModel, ABC):
    """Base class for every engine.

    Holds the fields all engines share (``source``, ``validation``, ``report``,
    ``on_failure``) and declares the methods each engine implements to load and
    inspect its data.

    Attributes:
        engine: The type of engine (e.g., 'pandas', 'spark', 'sql').
    """

    # arbitrary_types_allowed: `dataframe` holds a pd.DataFrame / SparkDataFrame,
    # neither of which pydantic knows how to build a schema for on its own.
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    id: str = Field(description="A unique identifier for the engine instance.")
    source: SourceConfig = Field(description="Configuration for the input data source.")
    validation: GXConfig = Field(
        description="Configuration for the Great Expectations validation workflow.",
    )
    report: SinkConfig = Field(
        description="Configuration for the output sink.",
    )
    on_failure: OnFailureActionConfig = Field(
        default_factory=IgnoreFailureAction,
        description="What to do with the source file when validation fails. Defaults to leaving it in place.",
    )
    dataframe: Any | None = Field(
        default=None,
        description="Holds the loaded data after calling the load_data method.",
    )

    @model_validator(mode="after")
    def _inherit_storage_for_action(self) -> Self:
        """Give a delete, move or copy action the source's storage backend when it has none.

        These actions need a backend to perform the file operation, but the YAML
        normally leaves ``on_failure.backend`` unset. This fills it with
        ``source.backend``, so the action works on the same storage the file was
        read from. A backend already set on the action is kept, and ``ignore``
        needs no backend, so it is left alone.
        """
        if (
            isinstance(self.on_failure, DeleteFailureAction) or isinstance(self.on_failure, RelocateFailureAction)
        ) and self.on_failure.backend is None:
            self.on_failure.backend = self.source.backend
        return self

    @abstractmethod
    def is_empty(self) -> bool:
        """Check if ``self.dataframe`` is empty. Only meaningful after ``load_data`` has run."""

    def _validate_on_empty(self, row_count: int | None = None, column_count: int | None = None) -> None:
        """Raise ``SourceEmptyError`` when ``self.dataframe`` has no rows to validate.

        Always raises on empty data, without deciding what that means. Whether an
        empty object is skipped or treated as a failure is a run-level setting
        (``source.on_empty``) that the runner applies the same way to every empty
        object, whether the emptiness was detected here (a header with no rows) or
        earlier, while reading (zero bytes, no header at all).
        ``row_count``/``column_count`` are passed to the exception so the report can
        still state the shape, even though raising stops ``load_data`` before it
        returns.
        """
        if self.is_empty():
            raise SourceEmptyError(f"{self.source.file_path} is empty", row_count=row_count, column_count=column_count)

    @abstractmethod
    def statistics(self) -> dict[str, Any]:
        """Return engine-specific statistics about ``self.dataframe``."""

    @abstractmethod
    def load_data(self, file_path: str) -> Self:
        """Load the source object at ``file_path`` into ``self.dataframe``.

        Each engine implements its own reading.

        Returns:
            ``self``, so the caller can chain ``is_empty()`` / ``statistics()``
            against the data this call just loaded, builder-style.
        """
