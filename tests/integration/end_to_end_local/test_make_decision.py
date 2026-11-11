"""End-to-end: the data verdict (``decision``) the report carries, per object and for the whole run.

Local storage, pandas engine, local file sink.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pylos.runner import Runner

pytestmark = pytest.mark.integration

MOCKED_CSV_NAME = "test-file.csv"

Workspace = dict[str, Path]
MakeRunner = Callable[..., Runner]
ReadReport = Callable[[], dict[str, Any]]


def test_aborted_only_run_has_no_data_decision(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
) -> None:
    (workspace["source"] / MOCKED_CSV_NAME).write_bytes(b"")

    make_runner().run()
    report = read_report()

    assert report["results"][0]["decision"] is None
    assert report["decision"] is None
