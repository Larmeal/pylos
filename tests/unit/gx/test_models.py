"""Tests for pylos.gx.models: the contract fills in what the YAML left out."""

from pylos.gx.models import ContractConfig


def _contract(*expectations: dict) -> ContractConfig:
    return ContractConfig.model_validate({"name": "orders", "expectations": list(expectations)})


def test_unnamed_expectation_is_named_after_contract_and_type() -> None:
    contract = _contract({"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": "id"}})

    assert contract.expectations[0].name == "orders_expect_column_values_to_not_be_null"


def test_explicit_expectation_name_is_kept() -> None:
    contract = _contract({"expectation_type": "expect_column_values_to_not_be_null", "name": "id_not_null"})

    assert contract.expectations[0].name == "id_not_null"


def test_empty_expectation_name_counts_as_unset() -> None:
    contract = _contract({"expectation_type": "expect_column_values_to_be_unique", "name": ""})

    assert contract.expectations[0].name == "orders_expect_column_values_to_be_unique"


def test_default_name_does_not_change_the_expectation_key() -> None:
    named = _contract(
        {"expectation_type": "expect_column_values_to_be_unique", "kwargs": {"column": "id"}, "name": "x"}
    )
    unnamed = _contract({"expectation_type": "expect_column_values_to_be_unique", "kwargs": {"column": "id"}})

    assert named.expectations[0].expectation_key == unnamed.expectations[0].expectation_key
