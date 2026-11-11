"""End-to-end: what happens to the source file when validation fails or the file cannot be read.

Local storage, pandas engine, local file sink. The report is checked against the
filesystem, so a report that claims a move cannot pass if the file did not move.

A file that cannot be read has two different causes, and they are not treated alike:

* the file itself is broken (bytes that are not valid text, rows that do not parse):
  reading it again will fail the same way;
* the environment is broken (permission denied, network, credentials): reading it
  again later may well work.

Which of them touches the file is the ``mode`` of the ``on_failure`` block: in
``decision`` (default) only data that was read and judged ``FAILED`` is acted on, an
unreadable file stays where it is and is reported as ``aborted``; in ``any_failure``
an unreadable file is acted on too, whatever the cause.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from pylos.engines import BaseEngine
from pylos.results import ActionName, ActionStatus, Decision, RunObjectStatus, RunStatus, Severity
from pylos.runner import Runner
from pylos.storages.local import LocalStorage

pytestmark = pytest.mark.integration

MOCKED_CSV_NAME = "test-file.csv"

Workspace = dict[str, Path]
MakeRunner = Callable[..., Runner]
ReadReport = Callable[[], dict[str, Any]]
MODES = ["decision", "any_failure"]


def _deny_reads(monkeypatch: pytest.MonkeyPatch, runner: Runner) -> None:
    """Make every CSV read fail with ``PermissionError``.

    A real permission error cannot be produced portably (Windows ignores chmod), so the
    read itself is made to fail. Everything after it is the real code.
    """

    def deny(self: BaseEngine, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("access denied")

    monkeypatch.setattr(type(runner.engine), "load_data", deny)


# The storage method each failure action ends up calling (see `actions.py`).
BACKEND_METHOD = {
    ActionName.MOVE: "move_obj",
    ActionName.COPY: "copy_obj",
    ActionName.DELETE: "delete_obj",
}


def _deny_action(monkeypatch: pytest.MonkeyPatch, action: ActionName) -> None:
    """Make ``action`` fail with ``PermissionError`` when the storage tries to perform it.

    A real permission error cannot be produced portably (Windows ignores chmod), so the
    storage call itself is made to fail. Everything before and after it is the real code.
    """

    def deny(self: LocalStorage, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("access denied for some reason")

    monkeypatch.setattr(LocalStorage, BACKEND_METHOD[action], deny)


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


def test_failed_validation_ignore_file_in_source(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
) -> None:
    """Same bad data as above, but ``on_failure`` is overridden: the verdict is unchanged, the file is not touched."""
    (workspace["source"] / MOCKED_CSV_NAME).write_text(
        "id,name\n1,a\n,b\n",
        encoding="utf-8",
    )

    make_runner(on_failure={"action": ActionName.IGNORE}).run()
    report = read_report()

    [obj] = report["results"]
    assert obj["decision"] == Decision.FAILED
    assert obj["action"]["action"] == ActionName.IGNORE
    assert obj["action"]["status"] == ActionStatus.SKIPPED

    assert (workspace["source"] / MOCKED_CSV_NAME).is_file()
    assert not workspace["dead_letter"].exists()


def test_failed_validation_delete_file_in_source(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
) -> None:
    """Same bad data as above, but ``on_failure`` is overridden to delete the file: the verdict is unchanged, the file is deleted from the source directory."""
    (workspace["source"] / MOCKED_CSV_NAME).write_text(
        "id,name\n1,a\n,b\n",
        encoding="utf-8",
    )

    make_runner(on_failure={"action": ActionName.DELETE}).run()
    report = read_report()

    [obj] = report["results"]
    assert obj["decision"] == Decision.FAILED
    assert obj["action"]["action"] == ActionName.DELETE
    assert obj["action"]["status"] == ActionStatus.COMPLETED

    assert not (workspace["source"] / MOCKED_CSV_NAME).exists()
    assert not workspace["dead_letter"].exists()


def test_failed_validation_moves_file_to_dead_letter(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
) -> None:
    """Data that fails a critical expectation: object completes, decision FAILED, file is acted on."""
    (workspace["source"] / MOCKED_CSV_NAME).write_text(
        "id,name\n1,a\n,b\n",
        encoding="utf-8",
    )

    make_runner(action=ActionName.MOVE).run()
    report = read_report()

    [obj] = report["results"]
    assert obj["status"] == RunObjectStatus.COMPLETED
    assert obj["decision"] == Decision.FAILED
    assert obj["action"]["action"] == ActionName.MOVE
    assert obj["action"]["status"] == ActionStatus.COMPLETED

    # The report claims the file moved: check the filesystem agrees.
    assert not (workspace["source"] / MOCKED_CSV_NAME).exists()
    assert (workspace["dead_letter"] / MOCKED_CSV_NAME).is_file()


def test_failed_validation_copy_file_to_dead_letter(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
) -> None:
    """Same bad data as above, but ``on_failure`` is overridden to copy the file: the verdict is unchanged, the file is copied to the dead letter directory."""
    (workspace["source"] / MOCKED_CSV_NAME).write_text(
        "id,name\n1,a\n,b\n",
        encoding="utf-8",
    )

    make_runner(action=ActionName.COPY).run()
    report = read_report()

    [obj] = report["results"]
    assert obj["decision"] == Decision.FAILED
    assert obj["action"]["action"] == ActionName.COPY
    assert obj["action"]["status"] == ActionStatus.COMPLETED

    assert (workspace["source"] / MOCKED_CSV_NAME).is_file()
    assert (workspace["dead_letter"] / MOCKED_CSV_NAME).is_file()


@pytest.mark.parametrize("action", [ActionName.MOVE, ActionName.COPY, ActionName.DELETE])
def test_failed_validation_but_the_action_itself_fails(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
    monkeypatch: pytest.MonkeyPatch,
    action: ActionName,
) -> None:
    """The data failed and the action was tried, but the storage refused: the report says so, the file is untouched.

    The object was read and judged, so it is ``completed`` with decision ``FAILED``. It is the
    action, not the object, that failed: ``ActionStatus.FAILED`` with the reason in ``error``.
    """
    (workspace["source"] / MOCKED_CSV_NAME).write_text(
        "id,name\n1,a\n,b\n",
        encoding="utf-8",
    )
    _deny_action(monkeypatch, action)

    # `delete` takes no dead_letter, so the whole block is replaced rather than one key.
    on_failure: dict[str, Any] = {"action": action}
    if action != ActionName.DELETE:
        on_failure["dead_letter"] = str(workspace["dead_letter"])
    make_runner(on_failure=on_failure).run()
    report = read_report()

    [obj] = report["results"]
    assert obj["status"] == RunObjectStatus.ABORTED
    assert obj["error_type"] == PermissionError.__name__
    assert obj["decision"] == Decision.FAILED
    assert obj["action"]["action"] == action
    assert obj["action"]["status"] == ActionStatus.FAILED

    # The report says the action failed: check the filesystem agrees, nothing was done.
    assert (workspace["source"] / MOCKED_CSV_NAME).is_file()
    assert not (workspace["dead_letter"] / MOCKED_CSV_NAME).exists()


class UnreadableCase(NamedTuple):
    """A source that cannot be read, the ``on_failure`` mode, and what must happen to the file."""

    content: bytes
    error_type: str
    mode: str
    # True when this mode acts on an unreadable file, so it ends up in the dead letter directory.
    triggers_action: bool
    # True: the file is fine and the read itself is made to fail (an environmental error).
    deny_reads: bool = False


CASES_UNREADABLE = [
    pytest.param(
        UnreadableCase(
            content=b"id,name\n\xff\xfe,a\n",
            error_type=UnicodeDecodeError.__name__,
            mode="decision",
            triggers_action=False,
        ),
        id="bytes_are_not_valid_utf8_in_decision_mode",
    ),
    pytest.param(
        UnreadableCase(
            content=b"id,name\n\xff\xfe,a\n",
            error_type=UnicodeDecodeError.__name__,
            mode="any_failure",
            triggers_action=True,
        ),
        id="bytes_are_not_valid_utf8_in_any_failure_mode",
    ),
    pytest.param(
        UnreadableCase(
            content=b"id,name\n1,a\n2,b,extra,more\n",
            error_type="ParserError",
            mode="decision",
            triggers_action=False,
        ),
        id="later_row_has_more_fields_than_header_in_decision_mode",
    ),
    pytest.param(
        UnreadableCase(
            content=b"id,name\n1,a\n2,b,extra,more\n",
            error_type="ParserError",
            mode="any_failure",
            triggers_action=True,
        ),
        id="later_row_has_more_fields_than_header_in_any_failure_mode",
    ),
    pytest.param(
        UnreadableCase(
            content=b"id,name\n1,a\n",
            error_type=PermissionError.__name__,
            mode="decision",
            triggers_action=False,
            deny_reads=True,
        ),
        id="permission_denied_in_decision_mode",
    ),
    pytest.param(
        UnreadableCase(
            content=b"id,name\n1,a\n",
            error_type=PermissionError.__name__,
            mode="any_failure",
            triggers_action=True,
            deny_reads=True,
        ),
        id="permission_denied_in_any_failure_mode",
    ),
]


@pytest.mark.parametrize("case", CASES_UNREADABLE)
def test_unreadable_source_is_aborted_and_the_file_follows_mode(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
    monkeypatch: pytest.MonkeyPatch,
    case: UnreadableCase,
) -> None:
    (workspace["source"] / MOCKED_CSV_NAME).write_bytes(case.content)

    runner = make_runner(mode=case.mode)
    if case.deny_reads:
        _deny_reads(monkeypatch, runner)

    runner.run()
    report = read_report()

    # The report names the failure the same way in both modes.
    [obj] = report["results"]
    assert obj["status"] == RunObjectStatus.ABORTED
    assert obj["error_type"] == case.error_type
    assert obj["error_message"]
    # Nothing was read, so nothing can be counted or validated.
    assert obj["row_count"] is None
    assert obj["column_count"] is None
    assert obj["expectations"] == []
    assert report["run_status"] == RunStatus.ABORTED

    # Only the mode decides whether the file is touched.
    assert (workspace["source"] / MOCKED_CSV_NAME).exists() is not case.triggers_action
    assert (workspace["dead_letter"] / MOCKED_CSV_NAME).exists() is case.triggers_action


@pytest.mark.parametrize("case", CASES_UNREADABLE)
def test_unreadable_source_has_no_data_decision(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
    monkeypatch: pytest.MonkeyPatch,
    case: UnreadableCase,
) -> None:
    (workspace["source"] / MOCKED_CSV_NAME).write_bytes(case.content)
    runner = make_runner(mode=case.mode)

    if case.deny_reads:
        _deny_reads(monkeypatch, runner)

    runner.run()
    report = read_report()

    assert report["results"][0]["decision"] is None
    assert report["decision"] is None


@pytest.mark.parametrize("mode", MODES)
def test_failed_validation_is_acted_on_in_every_mode(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
    mode: str,
) -> None:
    (workspace["source"] / MOCKED_CSV_NAME).write_text(
        "id,name\n1,a\n,b\n",
        encoding="utf-8",
    )

    make_runner(mode=mode).run()
    report = read_report()

    [obj] = report["results"]
    assert obj["decision"] == Decision.FAILED
    assert obj["action"]["action"] == ActionName.MOVE
    assert obj["action"]["status"] == ActionStatus.COMPLETED

    assert not (workspace["source"] / MOCKED_CSV_NAME).exists()
    assert (workspace["dead_letter"] / MOCKED_CSV_NAME).is_file()


# Make sure for Decisions that are not FAILED, the source is left alone.
class NotFailedCase(NamedTuple):
    """Data that was read and judged, but not ``FAILED``."""

    content: str
    severity: str
    decision: Decision


CASES_NOT_FAILED = [
    pytest.param(
        NotFailedCase(
            content="id,name\n1,a\n2,b\n",
            severity=Severity.CRITICAL,
            decision=Decision.PASSED,
        ),
        id="passed",
    ),
    pytest.param(
        # The null id breaks the expectation, but it is only a warning.
        NotFailedCase(
            content="id,name\n1,a\n,b\n",
            severity=Severity.WARNING,
            decision=Decision.WARNED,
        ),
        id="warned",
    ),
]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("case", CASES_NOT_FAILED)
def test_passed_or_warned_source_is_left_alone_in_every_mode(
    workspace: Workspace,
    make_runner: MakeRunner,
    read_report: ReadReport,
    mode: str,
    case: NotFailedCase,
) -> None:
    (workspace["source"] / MOCKED_CSV_NAME).write_text(case.content, encoding="utf-8")
    expectations = [
        {
            "expectation_type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": "id"},
            "severity": case.severity,
        }
    ]

    make_runner(mode=mode, expectations=expectations).run()
    report = read_report()

    [obj] = report["results"]
    assert obj["decision"] == case.decision
    assert obj["action"]["action"] == ActionName.IGNORE
    assert obj["action"]["status"] == ActionStatus.SKIPPED

    assert (workspace["source"] / MOCKED_CSV_NAME).is_file()
    assert not workspace["dead_letter"].exists()
