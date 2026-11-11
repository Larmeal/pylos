"""Tests for pylos.actions: ignore / delete / move / copy on a source object."""

import pytest
from pydantic import ValidationError

from pylos.actions import IgnoreFailureAction, MoveFailureAction


def test_mode_defaults_to_decision() -> None:
    assert IgnoreFailureAction().mode == "decision"
    assert MoveFailureAction(action="move", dead_letter="dead").mode == "decision"


def test_mode_accepts_any_failure() -> None:
    assert MoveFailureAction(action="move", dead_letter="dead", mode="any_failure").mode == "any_failure"


def test_mode_rejects_an_unknown_value() -> None:
    with pytest.raises(ValidationError):
        MoveFailureAction(action="move", dead_letter="dead", mode="always")
