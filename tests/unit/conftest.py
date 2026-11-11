"""Shared fixtures for the Pylos test suite.

Fixtures defined here are available to every test under ``tests/`` without import.
Put cross-cutting factories here (sample Pydantic models, fake storage, etc.);
keep module-specific fixtures next to their test file.
"""

import datetime
import logging

import pytest

from pylos.results import (
    ActionName,
    ActionResult,
    ActionStatus,
    Decision,
    ExpectationResult,
    PylosResult,
    RunObjectStatus,
    RunStatus,
    Severity,
    SourceObjectMetadata,
    SourceObjectResult,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def pylos_result_with_failures() -> PylosResult:
    """A PylosResult with every field populated: one object that was validated and failed.

    ``error_type`` and ``error_message`` stay ``None`` on purpose: they describe an object
    that could not be read (``RunObjectStatus.ABORTED``), which contradicts a completed
    object whose data simply failed its expectations.
    """
    return PylosResult(
        pylos_version="0.0.0-test",
        run_id="test-run-id-with-failures",
        run_ts=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        results=[
            SourceObjectResult(
                status=RunObjectStatus.COMPLETED,
                source_object=SourceObjectMetadata(
                    path="fake/path/to/source.csv",
                    size_bytes=123,
                    created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
                    modified_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
                    metadata={"etag": "fake-etag", "md5_hash": "fake-md5"},
                ),
                row_count=5,
                column_count=5,
                read_duration_sec=0.001,
                validation_duration_sec=0.002,
                error_type=None,
                error_message=None,
                decision=Decision.FAILED,
                expectations=[
                    ExpectationResult(
                        success=False,
                        expectation_name="id is never null",
                        expectation_type="expect_column_values_to_not_be_null",
                        expectation_key="sha256(expectation_type-kwargs)",
                        expectation_kwargs={"column": "id"},
                        description="Column 'id' must not contain nulls.",
                        severity=Severity.CRITICAL,
                        element_count=5,
                        observed_value=None,
                        unexpected_count=2,
                        unexpected_percent=40.0,
                        unexpected_values=[None, None],
                        unexpected_index=[1, 3],
                        raised_exception=False,
                        exception_message=None,
                        meta={"owner": "data-team"},
                        notes="Fake failing expectation for tests.",
                    )
                ],
                action=ActionResult(
                    action=ActionName.MOVE,
                    status=ActionStatus.FAILED,
                    dead_letter="fake/path/to/dead_letter",
                    error="PermissionError: cannot write to dead_letter",
                ),
                raw_gx_result={"success": False, "results": [{"success": False}]},
            )
        ],
        run_status=RunStatus.COMPLETED,
        decision=Decision.FAILED,
    )


@pytest.fixture
def pylos_result_with_success() -> PylosResult:
    """A PylosResult with every field populated: one object that was validated and passed.

    ``error_type``, ``error_message`` and ``action.error`` stay ``None``, and ``action.dead_letter``
    too: nothing went wrong, and a passed object is never acted on (``IGNORE`` / ``SKIPPED``).
    """
    return PylosResult(
        pylos_version="0.0.0-test",
        run_id="test-run-id-with-success",
        run_ts=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        results=[
            SourceObjectResult(
                status=RunObjectStatus.COMPLETED,
                source_object=SourceObjectMetadata(
                    path="fake/path/to/source.csv",
                    size_bytes=123,
                    created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
                    modified_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
                    metadata={"etag": "fake-etag", "md5_hash": "fake-md5"},
                ),
                row_count=5,
                column_count=5,
                read_duration_sec=0.001,
                validation_duration_sec=0.002,
                error_type=None,
                error_message=None,
                decision=Decision.PASSED,
                expectations=[
                    ExpectationResult(
                        success=True,
                        expectation_name="id is never null",
                        expectation_type="expect_column_values_to_not_be_null",
                        expectation_key="sha256(expectation_type-kwargs)",
                        expectation_kwargs={"column": "id"},
                        description="Column 'id' must not contain nulls.",
                        severity=Severity.CRITICAL,
                        element_count=5,
                        observed_value=0,
                        unexpected_count=0,
                        unexpected_percent=0.0,
                        unexpected_values=[],
                        unexpected_index=[],
                        raised_exception=False,
                        exception_message=None,
                        meta={"owner": "data-team"},
                        notes="Fake passing expectation for tests.",
                    )
                ],
                action=ActionResult(
                    action=ActionName.IGNORE,
                    status=ActionStatus.SKIPPED,
                    dead_letter=None,
                    error=None,
                ),
                raw_gx_result={"success": True, "results": [{"success": True}]},
            )
        ],
        run_status=RunStatus.COMPLETED,
        decision=Decision.PASSED,
    )
