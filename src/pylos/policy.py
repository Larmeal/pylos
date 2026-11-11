"""Turns validation results into decisions: the verdict on the data, and what to do with the file."""

from pylos.actions import IgnoreFailureAction, OnFailureActionConfig, RelocateFailureAction
from pylos.results import (
    ActionName,
    ActionResult,
    ActionStatus,
    Decision,
    ExpectationResult,
    Severity,
    SourceObjectResult,
)


class SourceObjectPolicy:
    """Decides what a validation result means, and what should happen to the file.

    Given the expectations checked against one source object, it answers the two
    questions the rest of the run needs:

    ```
    was the data good?       -> Decision.PASSED / WARNED / FAILED
    what do we do about it?  -> an ActionResult naming the action to perform
    ```

    Severity connects the two: a failure matters as much as the contract says
    it does.

    ```
    a critical expectation failed  -> FAIL, and the configured on_failure action is planned (move, copy, delete)
    only warnings failed           -> WARN, the file is left where it is
    nothing failed, or only info   -> PASS, the file is left where it is
    ```

    Only FAIL ever touches the file. WARN and PASS are still written to the
    report, but they do not move anything.

    SourceObjectPolicy is a brain with no hands. It never opens a file, relocates
    one, or writes a report, and it keeps no per-object state: ``decide()`` takes
    one object's results and returns the verdicts without storing them, so one
    instance could serve every object in a run. It can therefore be tested with
    nothing but a list of fabricated ``ExpectationResult`` objects: no GX, no
    storage, no engine, no I/O.

    The ``ActionResult`` it returns is only an intent: its status is ``PENDING``
    for an action that will run and ``SKIPPED`` when there is nothing to do. The
    report records that intent before the runner acts, so a row still at
    ``PENDING`` afterwards means the process died in between.

    It looks at one source object at a time, never at its neighbours. The
    run-level verdicts (``run_status``, ``decision``) are rollups computed over
    every object after the loop finishes; SourceObjectPolicy does not produce
    them.

    Attributes:
        on_failure_config: What the config said to do with a file that fails.
    """

    def __init__(self, on_failure_config: OnFailureActionConfig) -> None:
        """Prepare a policy for one pipeline.

        Args:
            on_failure_config: The pipeline's ``on_failure`` block, used only to
                choose the action for a ``FAILED`` object.
        """
        self.on_failure_config = on_failure_config

    def _make_decision(self, expectation_results: list[ExpectationResult]) -> Decision:
        """Reduces one object's expectation results to a verdict by worst severity.

        Only failures count, and a failed ``info`` expectation never lifts the
        verdict above ``PASS``. It is recorded as a note for a person and does
        not change the outcome.
        """
        failures = [result for result in expectation_results if not result.success]

        if any(result.severity == Severity.CRITICAL for result in failures):
            return Decision.FAILED
        if any(result.severity == Severity.WARNING for result in failures):
            return Decision.WARNED
        return Decision.PASSED

    def plan_action(self, decision_result: Decision) -> ActionResult:
        """Derives the unexecuted action from a verdict and ``on_failure_config``.

        Only ``FAIL`` leads to a real action, and only when the config is not
        ``IgnoreFailureAction``. Every other case returns ``IGNORE`` / ``SKIPPED``,
        because nothing touches the file. The runner performs a ``PENDING``
        action and updates its status afterwards.

        This is public, not only a step inside ``decide()``, because the runner
        also calls it directly for an object whose decision never came from
        expectations, such as a ``SourceEmptyError`` or an ``any_failure``
        abort. It passes ``Decision.FAILED`` to select the action without
        claiming that verdict happened.
        """
        if decision_result == Decision.FAILED and not isinstance(self.on_failure_config, IgnoreFailureAction):
            dead_letter = (
                self.on_failure_config.dead_letter
                if isinstance(self.on_failure_config, RelocateFailureAction)
                else None
            )
            return ActionResult(
                action=self.on_failure_config.action,
                status=ActionStatus.PENDING,
                dead_letter=dead_letter,
                error=None,
            )

        return ActionResult(
            action=ActionName.IGNORE,
            status=ActionStatus.SKIPPED,
            dead_letter=None,
            error=None,
        )

    def decide(self, expectation_results: list[ExpectationResult]) -> tuple[Decision, ActionResult]:
        """Turns one source object's expectation results into its two verdicts.

        This is the main entry point. The runner calls ``plan_action`` directly
        only for objects that have no expectation results to judge. Nothing is
        read, written or relocated here: the runner records the decision and
        then performs the action if one is due.

        Args:
            expectation_results: Every expectation checked against this one source
                object, as produced by ``gx/``.

        Returns:
            The ``Decision`` for the object and the ``ActionResult`` the runner
            should carry out. Neither is stored on ``self``.
        """
        decision_result = self._make_decision(expectation_results)
        action_result = self.plan_action(decision_result)

        return decision_result, action_result


class PylosPolicy:
    """Rolls the per-object decisions up into the decision for the whole run."""

    def _make_decision(self, source_object_results: list[SourceObjectResult]) -> Decision | None:
        """Determines the overall decision for a list of source object results.

        ``None`` entries (nothing to judge: an aborted read, or an empty source) are
        left out of the worst-of reduction instead of counting as a pass. If every
        object's decision is ``None``, the run never judged any data, so the
        run-level decision is ``None`` too, not the empty ``PASSED`` a plain
        reduction over an all-``None`` list would produce.
        """

        decisions = [result.decision for result in source_object_results if result.decision is not None]

        if not decisions:
            return None
        if Decision.FAILED in decisions:
            return Decision.FAILED
        if Decision.WARNED in decisions:
            return Decision.WARNED
        return Decision.PASSED

    def decide(self, source_object_results: list[SourceObjectResult]) -> Decision | None:
        """The run-level decision: the worst decision across all objects.

        ``FAILED`` if any object failed, otherwise ``WARNED`` if any warned,
        otherwise ``PASSED``. Objects with no decision (aborted or empty) are
        skipped, and if no object has a decision the result is ``None``.

        Args:
            source_object_results: Every object's result from this run.
        """
        return self._make_decision(source_object_results)
