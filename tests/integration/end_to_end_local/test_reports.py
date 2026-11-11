import hashlib
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any, NamedTuple
from unittest.mock import ANY

import pytest

from pylos.exceptions.data_error import SourceEmptyError
from pylos.results import ActionName, ActionStatus, Decision, RunObjectStatus, RunStatus, Severity
from pylos.runner import Runner

ENGINE_ID = "test-end-to-end-local"
CONTRACT_NAME = "orders"
MOCKED_CSV_NAME = "test-file.csv"

Workspace = dict[str, Path]
MakeRunner = Callable[..., Runner]
ReadReport = Callable[[], dict[str, Any]]

EXPECTATION_TYPE = "expect_column_values_to_not_be_null"
EXPECTATION_KEY = hashlib.sha256(f"{EXPECTATION_TYPE}-{ {'column': 'id'} }".encode()).hexdigest()


class Case(NamedTuple):
    """One source file and the whole report it must produce.

    The expected report starts as "the file was read and passed every expectation"
    (see ``_expected_report``). A case only states how it differs from that:

    Attributes:
        content: Bytes written to the source file.
        source_config: Overrides for the ``source`` block, e.g. ``{"on_empty": "fail"}``.
        on_failure_config: Overrides for the ``on_failure`` block.
        rows: Data rows in ``content``, used for the expectation's ``element_count``.
        expected_result: Fields of ``results[0]`` that differ from the default.
        expected_run: Run-level fields that differ from the default.
    """

    content: bytes
    source_config: dict[str, Any]
    on_failure_config: dict[str, Any]
    rows: int
    expected_result: dict[str, Any] | None = None
    expected_run: dict[str, Any] | None = None


def _expected_report(case: Case, source_file: Path) -> dict[str, Any]:
    """The whole report for ``case``: the default "read and passed" report plus the case's differences.

    Everything is compared 1-1 except the five values that change on every run
    (``run_ts``, both durations and both file timestamps), which are ``ANY``.
    """
    result: dict[str, Any] = {
        "status": RunObjectStatus.COMPLETED,
        "source_object": {
            "path": str(source_file),
            "size_bytes": len(case.content),
            "created_at": ANY,
            "modified_at": ANY,
            "metadata": {},
        },
        "row_count": case.rows,
        "column_count": 2,
        "read_duration_sec": ANY,
        "validation_duration_sec": ANY,
        "error_type": None,
        "error_message": None,
        "decision": Decision.PASSED,
        "expectations": [
            {
                "success": True,
                "expectation_name": f"{CONTRACT_NAME}_{EXPECTATION_TYPE}",
                "expectation_type": EXPECTATION_TYPE,
                "expectation_key": EXPECTATION_KEY,
                "expectation_kwargs": {"column": "id"},
                "description": None,
                "severity": Severity.CRITICAL,
                "element_count": case.rows,
                "observed_value": None,
                "unexpected_count": 0,
                "unexpected_percent": 0.0 if case.rows else None,
                "unexpected_values": [],
                "unexpected_index": [],
                "raised_exception": False,
                "exception_message": None,
                "meta": {"expectation_key": EXPECTATION_KEY},
                "notes": None,
            }
        ],
        "action": {
            "action": ActionName.IGNORE,
            "status": ActionStatus.SKIPPED,
            "dead_letter": None,
            "error": None,
        },
    }
    result.update(case.expected_result or {})

    report: dict[str, Any] = {
        "pylos_version": version("pylos"),
        "run_id": f"{CONTRACT_NAME}-{ENGINE_ID}",
        "run_ts": ANY,
        "results": [result],
        "run_status": RunStatus.COMPLETED,
        "decision": Decision.PASSED,
    }
    report.update(case.expected_run or {})
    return report


CASES_REPORT_REFLECTS_SOURCE_STATE = [
    pytest.param(
        Case(
            content=b"",
            source_config={"on_empty": "skip"},
            on_failure_config={"mode": "decision"},
            rows=0,
            expected_result={
                "status": RunObjectStatus.COMPLETED,
                "row_count": None,
                "column_count": None,
                "error_type": None,
                "decision": None,
                "expectations": [],
            },
            expected_run={"decision": None},
        ),
        id="zero_byte_with_on_empty_skip",
    ),
    pytest.param(
        Case(
            content=b"",
            source_config={"on_empty": "fail"},
            on_failure_config={"mode": "decision"},
            rows=0,
            expected_result={
                "status": RunObjectStatus.ABORTED,
                "row_count": None,
                "column_count": None,
                "error_type": SourceEmptyError.__name__,
                "error_message": ANY,
                "decision": None,
                "expectations": [],
                # on_empty=fail is recognized, not environmental: acted on regardless
                # of on_failure.mode, same as any other Decision.FAILED.
                "action": {
                    "action": ActionName.MOVE,
                    "status": ActionStatus.COMPLETED,
                    "dead_letter": ANY,
                    "error": None,
                },
            },
            expected_run={"run_status": RunStatus.ABORTED, "decision": None},
        ),
        id="zero_byte_with_on_empty_fail",
    ),
    pytest.param(
        Case(
            content=b"id,name\n",
            source_config={"on_empty": "skip"},
            on_failure_config={"mode": "decision"},
            rows=0,
            expected_result={
                "status": RunObjectStatus.COMPLETED,
                "row_count": 0,
                "error_type": None,
                "decision": None,
                "expectations": [],
            },
            expected_run={"decision": None},
        ),
        id="has_header_no_rows_on_empty_skip",
    ),
    pytest.param(
        Case(
            content=b"id,name\n",
            source_config={"on_empty": "fail"},
            on_failure_config={"mode": "decision"},
            rows=0,
            expected_result={
                "status": RunObjectStatus.ABORTED,
                "row_count": 0,
                "error_type": SourceEmptyError.__name__,
                "error_message": ANY,
                "decision": None,
                "expectations": [],
                "action": {
                    "action": ActionName.MOVE,
                    "status": ActionStatus.COMPLETED,
                    "dead_letter": ANY,
                    "error": None,
                },
            },
            expected_run={"run_status": RunStatus.ABORTED, "decision": None},
        ),
        id="has_header_no_rows_on_empty_fail",
    ),
    pytest.param(
        Case(
            content=b"id,name\n1,a\n2,b\n",
            source_config={"on_empty": "skip"},
            on_failure_config={"mode": "decision"},
            rows=2,
        ),
        id="normal_on_empty_skip",
    ),
    pytest.param(
        Case(
            content=b"id,name\n1,a\n2,b\n",
            source_config={"on_empty": "fail"},
            on_failure_config={"mode": "decision"},
            rows=2,
        ),
        id="normal_on_empty_fail",
    ),
]


# What the report looks like for the "normal" case (the dict built by `_expected_report`).
# {
#   "pylos_version": "0.1.0",
#   "run_id": "orders-test-end-to-end-local",
#   "run_ts": "2026-10-10T16:13:45.034915Z",
#   "results": [
#     {
#       "status": RunObjectStatus.COMPLETED,
#       "source_object": {
#         "path": ".../source/test-file.csv",
#         "size_bytes": 16,
#         "created_at": "2026-10-10T16:13:44.990000Z",
#         "modified_at": "2026-10-10T16:13:44.996910Z",
#         "metadata": {}
#       },
#       "row_count": 2,
#       "column_count": 2,
#       "read_duration_sec": 0.0017306999943684787,
#       "validation_duration_sec": 0.03437090000079479,
#       "error_type": null,
#       "error_message": null,
#       "decision": Decision.PASSED,
#       "expectations": [
#         {
#           "success": true,
#           "expectation_name": "orders_expect_column_values_to_not_be_null",
#           "expectation_type": "expect_column_values_to_not_be_null",
#           "expectation_key": "8aa21df4ef85b66523329aa39fa9aa20ff07ff3d64b51157a75fa7250445e9c6",
#           "expectation_kwargs": {"column": "id"},
#           "description": null,
#           "severity": Severity.CRITICAL,
#           "element_count": 2,
#           "observed_value": null,
#           "unexpected_count": 0,
#           "unexpected_percent": 0.0,
#           "unexpected_values": [],
#           "unexpected_index": [],
#           "raised_exception": false,
#           "exception_message": null,
#           "meta": {"expectation_key": "8aa21df4ef85b66523329aa39fa9aa20ff07ff3d64b51157a75fa7250445e9c6"},
#           "notes": null
#         }
#       ],
#       "action": {
#         "action": ActionName.IGNORE,
#         "status": ActionStatus.SKIPPED,
#         "dead_letter": null,
#         "error": null
#       }
#     }
#   ],
#   "run_status": RunStatus.COMPLETED,
#   "decision": Decision.PASSED
# }


@pytest.mark.parametrize("case", CASES_REPORT_REFLECTS_SOURCE_STATE)
def test_report_reflects_source_state(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
    case: Case,
) -> None:
    source_file = workspace["source"] / MOCKED_CSV_NAME
    source_file.write_bytes(case.content)

    make_runner(**case.source_config, **case.on_failure_config).run()
    report = read_report()

    assert report == _expected_report(case, source_file.resolve())
