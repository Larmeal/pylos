"""Runs a pipeline end to end: read, validate, decide, act and report."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from time import perf_counter
from typing import TYPE_CHECKING

from pylos.engines import Engine
from pylos.exceptions.data_error import SourceEmptyError
from pylos.gx.translation import GXTranslateExpectationResult
from pylos.gx.validator import GXValidator
from pylos.policy import PylosPolicy, SourceObjectPolicy
from pylos.results import (
    ActionName,
    ActionResult,
    ActionStatus,
    Decision,
    PylosResult,
    RunObjectStatus,
    RunStatus,
    SourceObjectMetadata,
    SourceObjectResult,
)

if TYPE_CHECKING:
    from pylos.actions import OnFailureActionConfig
    from pylos.gx.models import GXConfig
    from pylos.sinks import SinkConfig
    from pylos.sources import SourceConfig
    from pylos.storages import StorageBackend

logger = logging.getLogger(__name__)


class Runner:
    """Runs one pipeline end to end: list, read, validate, decide, act, report.

    For each source object the glob matches, the runner reads it with the engine,
    validates it with GX, asks ``SourceObjectPolicy`` for a decision and an action,
    performs the action, and records a ``SourceObjectResult``. When every object is
    done, it rolls the results up into one ``PylosResult`` and writes it to the
    report sink.

    One bad object does not stop the run. An empty source is handled according to
    ``source.on_empty``, any other exception marks that object ``aborted``, and the
    loop moves on to the next object. ``on_failure.mode`` decides whether an
    aborted object is acted on.

    Examples:
        >>> from pylos.loader import from_yaml
        >>> Runner(from_yaml("data/template_test.yml")).run()
    """

    def __init__(self, engine: Engine) -> None:
        """Prepare a runner for one loaded pipeline.

        Args:
            engine: The validated pipeline declaration, usually from
                ``pylos.loader.from_yaml``. Each source object is read into a
                copy of it, so this instance itself never holds data.
        """
        self.engine = engine
        self._storage = self.storage
        self._source = self.source
        self._validation = self.validation
        self._sink = self.sink
        self._on_failure = self.on_failure

    @property
    def on_failure(self) -> OnFailureActionConfig:
        """The ``on_failure`` block: what to do with a file that fails."""
        return self.engine.on_failure

    @property
    def sink(self) -> SinkConfig:
        """The ``report`` block: where the run's result is written."""
        return self.engine.report

    @property
    def validation(self) -> GXConfig:
        """The ``validation`` block: the contract and the Data Docs settings."""
        return self.engine.validation

    @property
    def source(self) -> SourceConfig:
        """The ``source`` block: which files to read, and how."""
        return self.engine.source

    @property
    def storage(self) -> StorageBackend:
        """The storage backend that lists the source files and relocates failed ones."""
        return self.engine.source.backend

    def __repr__(self) -> str:
        """A short summary for logs and the REPL: id, engine, source pattern and contract name."""
        return (
            f"Runner(id={self.engine.id!r}, "
            f"engine={self.engine.engine!r}, "
            f"source={self.source.file_path!r}, "
            f"contract={self.validation.contract.data_asset_name!r})"
        )

    @contextmanager
    def _timer(self) -> Generator[Callable[[], float]]:
        """Measure how long a ``with`` block takes.

        Yields:
            A function that returns the seconds elapsed since the block started.
            The clock keeps running after the block, so call it right after the
            block ends.

        Examples:
            >>> with self._timer() as elapsed:
            ...     do_work()
            >>> seconds = elapsed()
        """
        start = perf_counter()
        yield lambda: perf_counter() - start

    def _apply_action(self, action_result: ActionResult, src: str) -> Exception | None:
        """Performs the planned action and records whether it actually worked.

        Runs after the decision is final, so a failure here never changes the
        decision, expectations or statistics already computed for this source object.
        The exception is returned instead, so the caller can record the object as
        aborted and still keep the verdict. Nothing is raised from here: any exception
        from the storage backend is caught and recorded on ``action_result``, so one
        file's failed action cannot abort the objects still left in the loop.
        """
        if action_result.action == ActionName.IGNORE:
            return None

        try:
            self.on_failure.handle(src=src)
            action_result.status = ActionStatus.COMPLETED
            return None
        except Exception as e:
            logger.exception("failed to apply action %s for %s", action_result.action, src)
            action_result.status = ActionStatus.FAILED
            action_result.error = str(e)
            return e

    def run(self) -> None:
        """Process every source object, then write one report for the whole run.

        For each object the glob matches:

        1. Read it into a copy of the engine and collect its statistics.
        2. Validate it with GX and translate the result into ``ExpectationResult`` rows.
        3. Ask ``SourceObjectPolicy`` for the decision and the action.
        4. Perform the action (see ``_apply_action``).
        5. Record a ``SourceObjectResult``.

        How each kind of failure is recorded:

        - Empty source (``SourceEmptyError``): with ``on_empty: skip`` the file is
          left alone and the object is ``completed`` with no decision. With
          ``on_empty: fail`` the failure action is performed and the object is
          ``aborted``.
        - Any other exception while reading or validating: the object is
          ``aborted``, and the failure action runs only when ``on_failure.mode``
          is ``any_failure``.
        - The action itself fails: the object is ``aborted``, but its decision and
          expectation results are kept.

        After the loop, ``PylosPolicy`` gives the run-level decision, and
        ``run_status`` is ``completed`` if every object completed, ``aborted`` if
        every object aborted, and ``partial`` otherwise. The ``PylosResult`` is
        then written to the report sink; nothing is returned.

        ``run_id`` is ``<contract name>-<id>``, so every run of the same pipeline
        gets the same ``run_id``, and the local sink overwrites the previous
        report file.

        Raises:
            FileNotFoundError: With local storage, the pattern matched no file.
                The glob raises this before any object is processed, so no report
                is written.
        """
        source_object_metadata: list[SourceObjectMetadata] = self.storage.glob(self.engine.source.file_path)
        logger.info("resolved %d source object(s) for %s", len(source_object_metadata), self.engine.source.file_path)

        source_object_results: list[SourceObjectResult] = []
        for source in source_object_metadata:
            source: SourceObjectMetadata

            try:
                with self._timer() as duration:
                    engine = self.engine.model_copy().load_data(file_path=source.path)

                read_duration_sec = duration()
                statistics = engine.statistics()

                with self._timer() as validation_duration:
                    gx_result = GXValidator(config=self.validation).validate(df=engine.dataframe)

                validation_duration_sec = validation_duration()

                pylos_expectation_result = GXTranslateExpectationResult(
                    validation_config=self.validation.contract.expectations,
                ).translate(gx_result=gx_result)

                decision, action_result = SourceObjectPolicy(on_failure_config=self.on_failure).decide(
                    expectation_results=pylos_expectation_result
                )
                error_type = None
                error_message = None
            except SourceEmptyError as e:
                read_duration_sec = None
                validation_duration_sec = None
                gx_result = None
                statistics = {"row_count": e.row_count, "column_count": e.column_count}
                pylos_expectation_result = []
                decision = None
                error_type = type(e).__name__
                error_message = str(e)
                if self.source.on_empty == "skip":
                    logger.warning("source %s is empty, skipped per on_empty=skip: %s", source.path, e)
                    action_result = ActionResult(
                        action=ActionName.IGNORE,
                        status=ActionStatus.SKIPPED,
                        dead_letter=None,
                        error=None,
                    )
                    error_type = None
                    error_message = None
                else:
                    logger.warning("source %s is empty and on_empty=fail: %s", source.path, e)
                    action_result = SourceObjectPolicy(on_failure_config=self.on_failure).plan_action(Decision.FAILED)
            except Exception as e:
                logger.exception("failed to process %s", source.path)
                read_duration_sec = None
                validation_duration_sec = None
                gx_result = None
                statistics = {}
                pylos_expectation_result = []
                decision = None
                error_type = type(e).__name__
                error_message = str(e)
                action_result = (
                    SourceObjectPolicy(on_failure_config=self.on_failure).plan_action(Decision.FAILED)
                    if self.on_failure.mode == "any_failure"
                    else ActionResult(
                        action=ActionName.IGNORE, status=ActionStatus.SKIPPED, dead_letter=None, error=None
                    )
                )

            action_error = self._apply_action(action_result, source.path)
            if action_error is not None:
                error_type = type(action_error).__name__
                error_message = str(action_error)

            raw_gx_result = gx_result.describe_dict() if gx_result is not None else None
            source_object_results.append(
                SourceObjectResult(
                    status=RunObjectStatus.COMPLETED if error_type is None else RunObjectStatus.ABORTED,
                    source_object=source,
                    row_count=statistics.get("row_count"),
                    column_count=statistics.get("column_count"),
                    read_duration_sec=read_duration_sec,
                    validation_duration_sec=validation_duration_sec,
                    error_type=error_type,
                    error_message=error_message,
                    decision=decision,
                    expectations=pylos_expectation_result,
                    action=action_result,
                    raw_gx_result=raw_gx_result,
                )
            )

        pylos_decision = PylosPolicy().decide(source_object_results=source_object_results)

        if all(result.status == RunObjectStatus.COMPLETED for result in source_object_results):
            run_status = RunStatus.COMPLETED
        elif all(result.status == RunObjectStatus.ABORTED for result in source_object_results):
            run_status = RunStatus.ABORTED
        else:
            run_status = RunStatus.PARTIAL
        pylos_result = PylosResult(
            run_id=f"{self.validation.contract.data_asset_name}-{self.engine.id}",
            run_ts=datetime.datetime.now(tz=datetime.UTC),
            results=source_object_results,
            run_status=run_status,
            decision=pylos_decision,
        )

        logger.info("run %s finished: run_status=%s, decision=%s", pylos_result.run_id, run_status, pylos_decision)
        self._sink.write_sink(result=pylos_result)
