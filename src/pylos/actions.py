"""What happens to a source file whose data failed: ignore, move, copy or delete. There is one config class per action, and ``OnFailureActionConfig`` picks one from the ``action`` field."""

from abc import ABC, abstractmethod
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pylos.results import ActionName
from pylos.storages import StorageBackend


class BaseFailureAction(BaseModel, ABC):
    """Base configuration for every failure action.

    Holds the setting all actions share: the ``mode`` that decides which
    outcomes make the action fire.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["decision", "any_failure"] = Field(
        default="decision",
        description=(
            "Which outcomes make this action fire. "
            "'decision' (default, safe): only when Pylos read the file and judged the data to have "
            "failed (Decision.FAILED, a critical expectation did not pass). A file Pylos could not "
            "read or validate (RunObjectStatus.ABORTED) is never acted on: it stays where it is and "
            "the problem is reported instead, as status 'aborted' with its error_type and "
            "error_message on that object, and run_status 'partial' or 'aborted' for the run. "
            "'any_failure': fires for Decision.FAILED and also for an ABORTED file. This can act on "
            "a file that never had a chance to be judged, for example a transient read error on an "
            "otherwise good file; choosing it means accepting that risk. "
            "In both modes a file that passed or only warned (Decision.PASSED, Decision.WARNED) is "
            "left alone."
        ),
    )

    @abstractmethod
    def handle(self, src: str) -> None:
        """Perform the action on the source file."""


class IgnoreFailureAction(BaseFailureAction):
    """Leave the source file where it is.

    The default. Ignoring applies to the file alone: a report is still written,
    naming the file and what failed in it. No destination path is required.
    """

    action: Literal[ActionName.IGNORE] = Field(
        default=ActionName.IGNORE,
        description="Action identifier, fixed to 'ignore'. The file is left untouched; the report is still written.",
    )

    def handle(self, src: str | None = None) -> None:
        """Do nothing to the source file."""
        return None


class DeleteFailureAction(BaseFailureAction):
    """Configuration for deleting the raw source file in-place."""

    action: Literal[ActionName.DELETE] = Field(description="Action identifier, fixed to 'delete'.")
    backend: StorageBackend | None = Field(
        default=None,
        description="The storage backend to use for the action. If not provided, the storage backend will be inferred from the source configuration.",
    )

    def handle(self, src: str) -> None:
        """Delete the source file in place through the storage backend.

        Raises:
            ValueError: No storage backend is set.
        """

        if self.backend is not None:
            self.backend.delete_obj(src=src)
        else:
            raise ValueError(
                "No storage backend available to handle the `delete` action. Please provide a storage backend either in the `source` or `on_failure` configuration."
            )


class RelocateFailureAction(BaseFailureAction):
    """Configuration for actions that require a destination path."""

    dead_letter: str = Field(
        description=(
            "The directory path where the file should be moved/copied or where metadata should be saved. "
            "Supports both relative and absolute paths for local storage, "
            "and should be a valid URI for cloud storage (e.g., 'gs://bucket_name/path/to/directory')."
        ),
        examples=[
            "./data/dead-letters",
            "./data/dead-letters/",
            "gs://my-bucket/dead-letters",
            "gs://my-bucket/dead-letters/",
        ],
    )
    backend: StorageBackend | None = Field(
        default=None,
        description="The storage backend to use for the action. If not provided, the storage backend will be inferred from the source configuration.",
    )

    @field_validator("dead_letter", mode="after")
    @classmethod
    def validate_local_dead_letter_path(cls, value: str) -> str:
        """Strip trailing slashes from ``dead_letter``, rejecting an empty path or the root directory."""

        cleaned_path = value.rstrip("/")
        if not cleaned_path or cleaned_path == "/":
            raise ValueError("dead_letter cannot be empty or root directory ('/')")

        return cleaned_path


class MoveFailureAction(RelocateFailureAction):
    """Configuration for moving the raw source file to a dead-letter directory."""

    action: Literal[ActionName.MOVE] = Field(description="Action identifier, fixed to 'move'.")

    def handle(self, src: str) -> None:
        """Move the source file into ``dead_letter`` through the storage backend.

        Raises:
            ValueError: No storage backend is set.
        """
        if self.backend is not None:
            self.backend.move_obj(src=src, dst_dir=self.dead_letter)
        else:
            raise ValueError(
                "No storage backend available to handle the `move` action. Please provide a storage backend either in the `source` or `on_failure` configuration."
            )


class CopyFailureAction(RelocateFailureAction):
    """Configuration for copying the raw source file to a dead-letter directory."""

    action: Literal[ActionName.COPY] = Field(description="Action identifier, fixed to 'copy'.")

    def handle(self, src: str) -> None:
        """Copy the source file into ``dead_letter`` through the storage backend, leaving the original.

        Raises:
            ValueError: No storage backend is set.
        """
        if self.backend is not None:
            self.backend.copy_obj(src=src, dst_dir=self.dead_letter)
        else:
            raise ValueError(
                "No storage backend available to handle the `copy` action. Please provide a storage backend either in the `source` or `on_failure` configuration."
            )


OnFailureActionConfig = Annotated[
    IgnoreFailureAction | DeleteFailureAction | MoveFailureAction | CopyFailureAction,
    Field(discriminator="action"),
]
"""The ``on_failure`` section of a config. Its ``action`` field picks the class: ``ignore``, ``delete``, ``move`` or ``copy``."""
