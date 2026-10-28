from typing import NamedTuple

import pytest

from pylos.utils.config_management import dict_replace_by_key


class Case(NamedTuple):
    obj: dict
    replaced_key: dict
    deep_copy: bool
    expected: dict


CASES = [
    pytest.param(
        Case(
            obj={
                "key_1_level_1": {
                    "key_1_level_2": {
                        "key_1_level_3": "value_1_level_3",
                        "key_2_level_3": "value_1_level_3",
                    },
                },
                "key_2_level_1": 2,
            },
            replaced_key={"key_2_level_3": "new_value_1_level_3"},
            deep_copy=True,
            expected={
                "key_1_level_1": {
                    "key_1_level_2": {
                        "key_1_level_3": "value_1_level_3",
                        "key_2_level_3": "new_value_1_level_3",
                    },
                },
                "key_2_level_1": 2,
            },
        ),
        id="replace_nested_key_keeps_other_keys",
    ),
    pytest.param(
        Case(
            obj={"x": {"y": {"z": 1}}, "w": 2},
            replaced_key={"z": 9},
            deep_copy=True,
            expected={"x": {"y": {"z": 9}}, "w": 2},
        ),
        id="replace_value_with_int",
    ),
    pytest.param(
        Case(
            obj={"x": {"y": {"z": 1}}, "w": 2},
            replaced_key={"z": "new_value"},
            deep_copy=True,
            expected={"x": {"y": {"z": "new_value"}}, "w": 2},
        ),
        id="replace_value_with_str",
    ),
    pytest.param(
        Case(
            obj={"x": {"y": {"z": 1}}, "w": 2},
            replaced_key={"z": None},
            deep_copy=True,
            expected={"x": {"y": {"z": None}}, "w": 2},
        ),
        id="replace_value_with_none",
    ),
    pytest.param(
        Case(
            obj={"x": {"y": {"z": 1}}, "w": 2},
            replaced_key={"xxx": 42},
            deep_copy=True,
            expected={"x": {"y": {"z": 1}}, "w": 2},
        ),
        id="missing_key_leaves_obj_unchanged",
    ),
    pytest.param(
        Case(
            obj={"a": {"b": 1}, "c": "value"},
            replaced_key={"val": 1},
            deep_copy=True,
            expected={"a": {"b": 1}, "c": "value"},
        ),
        id="skip_str_sibling_when_key_is_its_substring",
    ),
    pytest.param(
        Case(
            obj={"a": {"b": 1}, "x": None},
            replaced_key={"b": 2},
            deep_copy=True,
            expected={"a": {"b": 2}, "x": None},
        ),
        id="skip_none_sibling",
    ),
    pytest.param(
        Case(
            obj={"a": {"b": 1}, "tags": ["b"]},
            replaced_key={"b": 2},
            deep_copy=True,
            expected={"a": {"b": 2}, "tags": ["b"]},
        ),
        id="skip_list_sibling_containing_key",
    ),
    pytest.param(
        Case(
            obj={"a": {"b": 1}, "f": 1.5, "t": True},
            replaced_key={"b": 2},
            deep_copy=True,
            expected={"a": {"b": 2}, "f": 1.5, "t": True},
        ),
        id="skip_float_and_bool_siblings",
    ),
    # Edge cases.
    pytest.param(
        Case(
            obj={},
            replaced_key={"a": 1},
            deep_copy=True,
            expected={},
        ),
        id="empty_obj_returns_empty",
    ),
    pytest.param(
        Case(
            obj={"a": {"b": 1}},
            replaced_key={},
            deep_copy=True,
            expected={"a": {"b": 1}},
        ),
        id="empty_replaced_key_leaves_obj_unchanged",
    ),
    pytest.param(
        Case(
            obj={"a": 1, "b": {"c": 2}},
            replaced_key={"a": 9},
            deep_copy=True,
            expected={"a": 9, "b": {"c": 2}},
        ),
        id="replace_top_level_key_without_recursing",
    ),
    pytest.param(
        Case(
            obj={"x": {"y": {"p": 1}}, "q": {"r": 2}},
            replaced_key={"p": 10, "r": 20},
            deep_copy=True,
            expected={"x": {"y": {"p": 10}}, "q": {"r": 20}},
        ),
        id="replace_multiple_keys_in_different_branches",
    ),
    pytest.param(
        Case(
            obj={"a": 1, "b": {"c": 2}},
            replaced_key={"a": 9, "c": 8},
            deep_copy=True,
            expected={"a": 9, "b": {"c": 8}},
        ),
        id="replace_multiple_keys_one_top_level_one_nested",
    ),
    pytest.param(
        Case(
            obj={"x": {"y": {"z": 1}}},
            replaced_key={"z": {"n": 1}},
            deep_copy=True,
            expected={"x": {"y": {"z": {"n": 1}}}},
        ),
        id="replace_nested_key_with_dict_replaces_whole_value",
    ),
    pytest.param(
        Case(
            obj={"a": {"b": 1}, "c": {"b": 1}},
            replaced_key={"b": 2},
            deep_copy=True,
            expected={"a": {"b": 2}, "c": {"b": 2}},
        ),
        id="duplicate_key_in_two_branches_replaces_both",
    ),
    pytest.param(
        Case(
            obj={"a": {"b": 1}, "c": {"b": 1}},
            replaced_key={"a": {"b": 2}},
            deep_copy=True,
            expected={"a": {"b": 2}, "c": {"b": 1}},
        ),
        id="replace_first_top_level_parent_with_dict",
    ),
    pytest.param(
        Case(
            obj={"a": {"b": 1}, "c": {"b": 1}},
            replaced_key={"c": {"b": 2}},
            deep_copy=True,
            expected={"a": {"b": 1}, "c": {"b": 2}},
        ),
        id="replace_last_top_level_parent_with_dict",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_dict_replace_by_key_replaces_keys_by_name_at_any_depth(case: Case) -> None:
    result = dict_replace_by_key(case.obj, case.replaced_key, case.deep_copy)
    assert result == case.expected


def test_deep_copy_true_leaves_original_untouched() -> None:
    obj = {"x": {"y": 1}}
    result = dict_replace_by_key(obj, {"y": 9}, deep_copy=True)

    assert obj == {"x": {"y": 1}}
    assert result is not obj
    assert result["x"] is not obj["x"]  # deep copy, not shallow


def test_deep_copy_false_mutates_in_place() -> None:
    obj = {"x": {"y": 1}}
    result = dict_replace_by_key(obj, {"y": 9}, deep_copy=False)

    assert result is obj
    assert obj == {"x": {"y": 9}}
