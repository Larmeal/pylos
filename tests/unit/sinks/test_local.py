"""Tests for pylos.sinks.local: writing the run report to the local filesystem."""

import json
from pathlib import Path

from pylos.results import PylosResult
from pylos.sinks.local import LocalSink


def test_write_sink_creates_missing_directory(
    tmp_path: Path,
    pylos_result_with_success: PylosResult,
) -> None:
    target_dir = tmp_path / "reports"
    sink = LocalSink(storage="local", format="file", path=str(target_dir))

    sink.write_sink(pylos_result_with_success)

    assert target_dir.parent.is_dir()


def test_write_sink_names_file_after_run_id(
    tmp_path: Path,
    pylos_result_with_success: PylosResult,
) -> None:
    sink = LocalSink(storage="local", format="file", path=str(tmp_path))

    sink.write_sink(pylos_result_with_success)

    assert (tmp_path / f"{pylos_result_with_success.run_id}.json").exists()


def test_write_sink_writes_full_result_as_json(
    tmp_path: Path,
    pylos_result_with_success: PylosResult,
) -> None:
    sink = LocalSink(storage="local", format="file", path=str(tmp_path))

    sink.write_sink(pylos_result_with_success)

    written = json.loads((tmp_path / f"{pylos_result_with_success.run_id}.json").read_text(encoding="utf-8"))
    assert written == json.loads(pylos_result_with_success.model_dump_json())
