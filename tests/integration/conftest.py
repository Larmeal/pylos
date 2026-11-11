import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pylos.engines.pandas import PandasEngine
from pylos.results import ActionName, Severity
from pylos.runner import Runner
from pylos.utils.config_management import dict_replace_by_key

ENGINE_ID = "test-end-to-end-local"
CONTRACT_NAME = "orders"
MOCKED_CSV_NAME = "test-file.csv"

# Just define the types for clarity and reuse in fixtures.
Workspace = dict[str, Path]
MakeRunner = Callable[..., Runner]
ReadReport = Callable[[], dict[str, Any]]


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Directories the run reads from and writes to, all under ``tmp_path``."""
    paths = {
        "source": tmp_path / "source",
        "reports": tmp_path / "reports",
        "dead_letter": tmp_path / "dead_letter",
    }
    paths["source"].mkdir()
    return paths


@pytest.fixture
def make_runner(workspace: Workspace) -> MakeRunner:
    """Factory: build a Runner wired to ``workspace``. Pass overrides for the parts a test cares about."""

    def _make(**engine_overrides: Any) -> Runner:
        config: dict[str, Any] = {
            "id": ENGINE_ID,
            "engine": "pandas",
            "source": {
                "storage": "local",
                "file_format": "csv",
                "file_path": str(workspace["source"] / "*.csv"),
                "on_empty": "skip",
            },
            "validation": {
                "contract": {
                    "name": CONTRACT_NAME,
                    "expectations": [
                        {
                            "expectation_type": "expect_column_values_to_not_be_null",
                            "kwargs": {"column": "id"},
                            "severity": Severity.CRITICAL,
                        }
                    ],
                },
            },
            "report": {
                "format": "file",
                "storage": "local",
                "path": str(workspace["reports"]),
            },
            "on_failure": {
                "mode": "decision",
                "action": ActionName.MOVE,
                "dead_letter": str(workspace["dead_letter"]),
            },
        }
        config = dict_replace_by_key(config, engine_overrides)
        return Runner(engine=PandasEngine.model_validate(config))

    return _make


@pytest.fixture
def read_report(workspace: Workspace) -> ReadReport:
    """Read the single report the run wrote: what a downstream consumer would actually see."""

    def _read() -> dict[str, Any]:
        report = workspace["reports"] / f"{CONTRACT_NAME}-{ENGINE_ID}.json"
        assert report.is_file(), f"no report written under {workspace['reports']}"
        return json.loads(report.read_text(encoding="utf-8"))

    return _read
