"""Converts a Great Expectations result into Pylos's own ``ExpectationResult`` rows."""

import logging
from typing import Any

from great_expectations.core.expectation_validation_result import (
    ExpectationSuiteValidationResult,
)

from pylos.gx.models import ExpectationConfig
from pylos.results import ExpectationResult

logger = logging.getLogger(__name__)


class GXTranslateExpectationResult:
    """Turns one GX validation result into Pylos's own ``ExpectationResult`` rows.

    This class sits at the GX/Pylos boundary. Everything downstream of
    ``translate()`` (policy, sinks, reports) works only with Pylos's own
    ``ExpectationResult`` model and never touches a GX object. Every GX-specific
    detail (the nested result dict shape, the ``partial_``-prefixed keys, the fact
    that ``meta`` is the only field that survives a suite round trip) stays in this
    one class. When a future GX version changes its result schema, the fix is a
    diff to ``translate()`` alone, and nothing else in Pylos needs to change.

    GX's result dict carries no Pylos identifiers of its own. ``expectation_key``
    survives the round trip only through ``expectation_config.meta``; GX regenerates
    its own ``id`` when a suite is added to a context, so that field cannot be used.
    ``translate()`` uses the key to match each GX result back to the
    ``ExpectationConfig`` that produced it, then rebuilds the fields Pylos reports
    on. Some come from our own config (name, type, kwargs, description, severity)
    and others from GX's result payload (success, counts, unexpected values).

    Attributes:
        validation_config: The expectations that were validated, used to look up
            each GX result's declared name/description/severity by its key.
    """

    def __init__(self, validation_config: list[ExpectationConfig]) -> None:
        """Prepare a translator for one contract.

        Args:
            validation_config: The contract's expectations, in any order. Each GX
                result is matched back to one of these by ``expectation_key``.
        """
        self.validation_config = validation_config

    def _mapping_expectation_config(self, expectation_key: str) -> ExpectationConfig:
        """Finds the ``ExpectationConfig`` that declared the given key.

        Raises:
            ValueError: No expectation in ``validation_config`` has this key, so
                the GX result does not belong to this contract.
        """
        for config in self.validation_config:
            if config.expectation_key == expectation_key:
                return config
        raise ValueError(f"ExpectationConfig with key {expectation_key!r} not found.")

    def translate(self, gx_result: ExpectationSuiteValidationResult) -> list[ExpectationResult]:
        """Converts ``gx_result`` into ``ExpectationResult`` rows, one per expectation.

        Returns:
            One ``ExpectationResult`` per entry in ``gx_result["results"]``, in
            GX's order.

        Raises:
            ValueError: ``gx_result`` has no ``results`` list; an entry is missing
                ``expectation_key`` in ``expectation_config.meta``; an entry's key
                matches no expectation in ``validation_config``; or an entry has no
                ``exception_info``. A missing key means Pylos's own meta injection
                did not survive validation, which is a framework bug, not a user
                error.
        """

        if not gx_result.get("results"):
            raise ValueError("No results found in the Great Expectations validation result.")

        pylos_expectation_result: list[ExpectationResult] = []
        for result in gx_result.get("results"):  # type: ignore
            result: dict

            expectation_config_data: dict[str, Any] | None = result.get("expectation_config")
            meta: dict[str, Any] = (expectation_config_data or {}).get("meta") or {}

            expectation_key = meta.get("expectation_key")
            if expectation_key is None:
                raise ValueError(
                    "Missing 'expectation_key' in the GX result's 'expectation_config.meta'. Pylos "
                    "always injects this key into the expectation's meta before validation, so its "
                    "absence here means Great Expectations did not echo it back as expected, which is "
                    "a bug in the Pylos framework, please report it to the maintainers."
                )
            expectation_config: ExpectationConfig = self._mapping_expectation_config(expectation_key)

            expectation_name = expectation_config.name
            expectation_type = expectation_config.expectation_type
            expectation_kwargs = expectation_config.kwargs
            description = expectation_config.description
            severity = expectation_config.severity

            result_data: dict[str, Any] | None = result.get("result")

            success: bool = result.get("success")  # type: ignore
            element_count: int | None = result_data.get("element_count") if result_data else None
            observed_value: Any | None = result_data.get("observed_value") if result_data else None
            unexpected_count: int | None = result_data.get("unexpected_count") if result_data else None
            unexpected_percent: float | None = result_data.get("unexpected_percent") if result_data else None
            unexpected_values: list[Any] | None = result_data.get("partial_unexpected_list") if result_data else None
            unexpected_index: list[int] | None = (
                result_data.get("partial_unexpected_index_list") if result_data else None
            )

            if exception_info := result.get("exception_info"):
                if "raised_exception" in exception_info:
                    raised_exception: bool = exception_info.get("raised_exception")
                    exception_message: str | None = exception_info.get("exception_message")
                else:
                    # NOTE: Have only one exception info dictionary, so we can directly extract the values.
                    # If someday there are multiple exception info dictionaries,
                    # this loop will store the last one encountered.
                    for value in exception_info.values():
                        raised_exception = value.get("raised_exception")
                        exception_message = value.get("exception_message")
            else:
                raise ValueError("Exception info is missing from the result.")

            raw_notes: str | list[str] | None = (
                expectation_config_data.get("notes") if expectation_config_data else None
            )
            notes: str | None = "\n".join(raw_notes) if isinstance(raw_notes, list) else raw_notes
            pylos_expectation_result.append(
                ExpectationResult(
                    expectation_key=expectation_key,
                    expectation_name=expectation_name,
                    expectation_type=expectation_type,
                    expectation_kwargs=expectation_kwargs,
                    description=description,
                    severity=severity,
                    success=success,
                    element_count=element_count,
                    observed_value=observed_value,
                    unexpected_count=unexpected_count,
                    unexpected_percent=unexpected_percent,
                    unexpected_values=unexpected_values,
                    unexpected_index=unexpected_index,
                    raised_exception=raised_exception,
                    exception_message=exception_message,
                    meta=meta,
                    notes=notes,
                )
            )
        return pylos_expectation_result
