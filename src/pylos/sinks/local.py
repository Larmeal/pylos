"""The local report sink, which writes one JSON file per run."""

import logging
from pathlib import Path
from typing import Literal

from pydantic import Field

from pylos.results import PylosResult
from pylos.sinks.base import BaseFileFormat

logger = logging.getLogger(__name__)


class LocalSink(BaseFileFormat):
    """Writes the report as one JSON file on the local filesystem.

    Examples:
        In the pipeline YAML:

            report:
              storage: local
              format: file
              path: output/reports/
    """

    storage: Literal["local"] = Field(description="Storage backend type, fixed to 'local'.")

    def _handle(self, result: PylosResult) -> str:
        """Serialize the whole result to JSON with ``model_dump_json()``.

        Fields marked ``exclude`` (such as ``raw_gx_result``) are left out.
        """
        return result.model_dump_json()

    def write_sink(self, result: PylosResult) -> None:
        """Write the result to ``path`` as JSON.

        If ``path`` is an existing file, that file is overwritten. Otherwise
        ``path`` is treated as a directory and the report goes to
        ``<path>/<run_id>.json``, replacing any earlier report with the same
        ``run_id``. Missing directories are created, and a relative ``path`` is
        resolved against the current directory.

        Args:
            result: The run's result.
        """

        if not isinstance(self.path, Path):
            directory = Path(self.path).resolve()

        if not directory.is_file():
            file_path = directory.joinpath(f"{result.run_id}.json")
        else:
            file_path = directory

        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("w", encoding="utf-8") as f:
            f.write(self._handle(result))
        logger.info("wrote report for run %s to %s", result.run_id, file_path)
