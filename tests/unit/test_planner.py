"""Tests for pylos.planner: resolving the source glob into planned objects."""

import datetime
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest

from pylos.engines.pandas import PandasEngine
from pylos.planner import (
    _BOX_WIDTH,
    _OBJECT_PREVIEW,
    _PATH_WIDTH,
    Plan,
    Planner,
    _box,
    _elide_path,
    _human_size,
    _needs_quotes,
    _relative_to_cwd,
    _render_kwarg_scalar,
    _render_kwargs_lines,
    _render_value,
)
from pylos.results import SourceObjectMetadata
from pylos.utils.config_management import dict_replace_by_key

ENGINE_ID = "planner-test"
CONTRACT_NAME = "orders"
STAMP = datetime.datetime(2026, 9, 8, 21, 25, tzinfo=datetime.UTC)

MakeEngine = Callable[..., PandasEngine]
MakePlan = Callable[..., Plan]


def _rule(column: str, severity: str = "critical") -> dict[str, Any]:
    return {
        "expectation_type": "expect_column_values_to_not_be_null",
        "kwargs": {"column": column},
        "severity": severity,
    }


def _objects(count: int, size_bytes: int = 410, modified_at: datetime.datetime = STAMP) -> list[SourceObjectMetadata]:
    """Fabricated listing entries. ``gs://`` paths are shown as stored, whatever the working directory."""
    return [
        SourceObjectMetadata(
            path=f"gs://bucket/data/test_{index}.csv",
            size_bytes=size_bytes,
            created_at=modified_at,
            modified_at=modified_at,
        )
        for index in range(1, count + 1)
    ]


@pytest.fixture
def make_engine(tmp_path: Path) -> MakeEngine:
    """Factory: a pandas engine reading ``tmp_path/source``. Overrides replace config keys by name."""

    def _make(**overrides: Any) -> PandasEngine:
        config: dict[str, Any] = {
            "id": ENGINE_ID,
            "engine": "pandas",
            "source": {
                "storage": "local",
                "file_format": "csv",
                "file_path": str(tmp_path / "source" / "*.csv"),
                "on_empty": "skip",
                "options": {},
            },
            "validation": {
                "contract": {"name": CONTRACT_NAME, "expectations": [_rule("id")]},
                "data_docs": {"enabled": False},
            },
            "report": {"format": "file", "storage": "local", "path": "output/reports/"},
            "on_failure": {"action": "move", "dead_letter": "output/dead-letters/"},
        }
        return PandasEngine.model_validate(dict_replace_by_key(config, overrides))

    return _make


@pytest.fixture
def make_plan(make_engine: MakeEngine) -> MakePlan:
    """Factory: a ``Plan`` built by hand from fabricated objects, so no filesystem is read.

    The pattern is fixed to ``data/*.csv`` so the rendered text never carries the temp directory's name.
    """

    def _make(source_objects: Iterable[SourceObjectMetadata] = (), **overrides: Any) -> Plan:
        engine = make_engine(**{"file_path": "data/*.csv", **overrides})
        return Plan(
            engine_id=engine.id,
            engine_name=engine.engine,
            source=engine.source,
            contract=engine.validation.contract,
            on_failure=engine.on_failure,
            report=engine.report,
            data_docs_enabled=engine.validation.data_docs.enabled,
            source_objects=list(source_objects),
        )

    return _make


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "source"
    directory.mkdir()
    return directory


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        pytest.param(0, "0 B", id="zero"),
        pytest.param(410, "410 B", id="bytes_have_no_decimal"),
        pytest.param(1023, "1023 B", id="last_byte_value"),
        pytest.param(1024, "1.0 KB", id="first_kilobyte"),
        pytest.param(1536, "1.5 KB", id="fractional_kilobyte"),
        pytest.param(5 * 1024**2, "5.0 MB", id="megabytes"),
        pytest.param(1024**3, "1.0 GB", id="first_gigabyte"),
        pytest.param(5000 * 1024**3, "5000.0 GB", id="gigabytes_never_step_up"),
    ],
)
def test_human_size(size_bytes: int, expected: str) -> None:
    assert _human_size(size_bytes) == expected


def test_elide_path_keeps_a_path_that_fits() -> None:
    fits = "a" * _PATH_WIDTH

    assert _elide_path("data/test_1.csv") == "data/test_1.csv"
    assert _elide_path(fits) == fits


def test_elide_path_cuts_from_the_left_and_marks_the_cut() -> None:
    path = "x" * 10 + "/data/test_1.csv".rjust(_PATH_WIDTH, "a")

    elided = _elide_path(path)

    assert len(elided) == _PATH_WIDTH
    assert elided.startswith("…")
    assert elided.endswith("/data/test_1.csv")
    assert elided[1:] == path[-(_PATH_WIDTH - 1) :]


def test_relative_to_cwd_shortens_a_path_inside_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert _relative_to_cwd(str(tmp_path / "data" / "a.csv")) == str(Path("data") / "a.csv")


def test_relative_to_cwd_leaves_a_path_outside_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inside = tmp_path / "inside"
    inside.mkdir()
    monkeypatch.chdir(inside)
    outside = str(tmp_path / "outside" / "a.csv")

    assert _relative_to_cwd(outside) == outside


def test_relative_to_cwd_leaves_a_uri_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert _relative_to_cwd("gs://bucket/data/a.csv") == "gs://bucket/data/a.csv"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("col_int64", id="identifier"),
        pytest.param("order id", id="inner_space"),
    ],
)
def test_needs_quotes_is_false_for_plain_text(value: str) -> None:
    assert _needs_quotes(value) is False


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param(" col", id="leading_space"),
        pytest.param("col ", id="trailing_space"),
        pytest.param("true", id="bool_lower"),
        pytest.param("FALSE", id="bool_upper"),
        pytest.param("None", id="none"),
        pytest.param("null", id="null"),
        pytest.param("yes", id="yes"),
        pytest.param("No", id="no"),
        pytest.param("~", id="tilde"),
        pytest.param("123", id="integer"),
        pytest.param("-1.5", id="negative_float"),
        pytest.param("1e3", id="exponent"),
        pytest.param("2000-01-01", id="date"),
        pytest.param("2000-01-01 00:00:00", id="timestamp"),
    ],
)
def test_needs_quotes_is_true_when_yaml_would_misread_the_text(value: str) -> None:
    assert _needs_quotes(value) is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(True, "true", id="true_is_not_python_true"),
        pytest.param(False, "false", id="false"),
        pytest.param("utf-8", '"utf-8"', id="string_is_quoted"),
        pytest.param(["a", "b"], "[a, b]", id="list_items_are_unquoted"),
        pytest.param([1, 2], "[1, 2]", id="list_of_numbers"),
        pytest.param([True, "x"], "[true, x]", id="list_keeps_bool_spelling"),
        pytest.param(0, "0", id="zero_is_not_dropped"),
        pytest.param(1.5, "1.5", id="float"),
        pytest.param(None, "None", id="none"),
    ],
)
def test_render_value(value: Any, expected: str) -> None:
    assert _render_value(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("col_int64", "col_int64", id="plain_string_stays_bare"),
        pytest.param("2000-01-01 00:00:00", '"2000-01-01 00:00:00"', id="timestamp_string_is_quoted"),
        pytest.param("true", '"true"', id="bool_looking_string_is_quoted"),
        pytest.param(True, "true", id="bool"),
        pytest.param(5, "5", id="number"),
        pytest.param(["a", "b"], "[a, b]", id="list"),
    ],
)
def test_render_kwarg_scalar(value: Any, expected: str) -> None:
    assert _render_kwarg_scalar(value) == expected


def test_render_kwargs_lines_keeps_declaration_order() -> None:
    kwargs = {"max_value": 5, "column": "col_int64", "min_value": 0}

    assert _render_kwargs_lines(kwargs, indent="  ") == [
        "  max_value: 5",
        "  column: col_int64",
        "  min_value: 0",
    ]


def test_render_kwargs_lines_writes_column_list_one_column_per_line() -> None:
    assert _render_kwargs_lines({"column_list": ["a", "b"]}, indent="    ") == [
        "    column_list:",
        "      - a",
        "      - b",
    ]


def test_render_kwargs_lines_writes_other_lists_on_one_line() -> None:
    assert _render_kwargs_lines({"value_set": [True, False]}, indent="") == ["value_set: [true, false]"]


def test_render_kwargs_lines_treats_a_non_list_column_list_as_a_scalar() -> None:
    assert _render_kwargs_lines({"column_list": "abc"}, indent="  ") == ["  column_list: abc"]


def test_render_kwargs_lines_of_nothing_is_nothing() -> None:
    assert _render_kwargs_lines({}, indent="  ") == []


def test_box_draws_the_expected_frame() -> None:
    lines = _box("on failure", [("action", "move"), ("dead letter", "output/dead-letters")])

    assert lines == [
        "╭─ on failure " + "─" * 63 + "╮",
        "│" + "  action      : move".ljust(_BOX_WIDTH - 2) + "│",
        "│" + "  dead letter : output/dead-letters".ljust(_BOX_WIDTH - 2) + "│",
        "╰" + "─" * (_BOX_WIDTH - 2) + "╯",
    ]


def test_box_lines_all_share_one_width() -> None:
    lines = _box("source", [("storage", "local"), ("", "continued"), ("pattern", "data/*.csv")])

    assert {len(line) for line in lines} == {_BOX_WIDTH}


def test_box_aligns_every_colon_under_the_longest_label() -> None:
    _, first, second, _ = _box("t", [("a", "1"), ("longer label", "2")])

    assert first.index(":") == second.index(":")


def test_box_starts_a_continuation_row_under_the_value_above_it() -> None:
    _, first, second, _ = _box("t", [("options", "delimiter"), ("", "encoding")])

    assert second.index("encoding") == first.index("delimiter")
    assert ":" not in second


def test_box_needs_at_least_one_labelled_row() -> None:
    with pytest.raises(ValueError):
        _box("t", [("", "orphan")])


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def test_ordered_expectations_groups_by_severity_then_keeps_declaration_order(make_plan: MakePlan) -> None:
    plan = make_plan(
        expectations=[
            _rule("col_1", "warning"),
            _rule("col_2", "critical"),
            _rule("col_3", "info"),
            _rule("col_4", "critical"),
        ]
    )

    ordered = [rule.kwargs["column"] for rule in plan.ordered_expectations()]
    declared = [rule.kwargs["column"] for rule in plan.contract.expectations]

    assert ordered == ["col_2", "col_4", "col_1", "col_3"]
    assert declared == ["col_1", "col_2", "col_3", "col_4"], "the contract's own list must not be reordered"


def test_ordered_expectations_of_an_empty_contract_is_empty(make_plan: MakePlan) -> None:
    assert make_plan(expectations=[]).ordered_expectations() == []


def test_render_starts_with_the_engine_id_and_name(make_plan: MakePlan) -> None:
    assert make_plan().render().splitlines()[1] == f"  PYLOS plan · {ENGINE_ID} · pandas"


def test_render_shows_the_source_declaration(make_plan: MakePlan) -> None:
    plan = make_plan(
        file_path="data/test_*.csv",
        on_empty="fail",
        options={"delimiter": ",", "encoding": "utf-8"},
    )

    output = plan.render()

    assert "pandas.read_csv" in output
    assert 'options  : delimiter=","' in output
    assert 'encoding="utf-8"' in output
    assert "pattern  : data/test_*.csv" in output
    assert "on_empty : fail" in output


def test_render_omits_the_options_row_when_there_are_no_options(make_plan: MakePlan) -> None:
    assert "options  :" not in make_plan().render()


@pytest.mark.parametrize(
    ("count", "summary"),
    [
        pytest.param(0, "0 objects resolved", id="none"),
        pytest.param(1, "1 object resolved · 410 B", id="one_is_singular"),
        pytest.param(2, "2 objects resolved · 820 B", id="two_is_plural"),
    ],
)
def test_render_summarises_the_resolved_objects(make_plan: MakePlan, count: int, summary: str) -> None:
    assert summary in make_plan(_objects(count)).render()


def test_render_separates_thousands_in_the_object_count(make_plan: MakePlan) -> None:
    assert "1,200 objects resolved · 1.2 KB" in make_plan(_objects(1200, size_bytes=1)).render()


def test_render_lists_at_most_the_preview_and_counts_the_rest(make_plan: MakePlan) -> None:
    output = make_plan(_objects(_OBJECT_PREVIEW + 1)).render()

    assert "test_5.csv" in output
    assert "test_6.csv" not in output
    assert "… 1 more" in output


def test_render_has_no_more_line_at_exactly_the_preview_size(make_plan: MakePlan) -> None:
    output = make_plan(_objects(_OBJECT_PREVIEW)).render()

    assert "test_5.csv" in output
    assert "more" not in output


def test_render_full_objects_lists_all_of_them_with_a_position(make_plan: MakePlan) -> None:
    output = make_plan(_objects(_OBJECT_PREVIEW + 1)).render(full_objects=True)

    assert "       6  gs://bucket/data/test_6.csv" in output
    assert "more" not in output


def test_render_shows_modified_time_in_utc_by_default(make_plan: MakePlan) -> None:
    assert "modified 2026-09-08 21:25" in make_plan(_objects(1)).render()


def test_render_shows_modified_time_in_the_requested_timezone(make_plan: MakePlan) -> None:
    assert "modified 2026-09-09 04:25" in make_plan(_objects(1)).render(timezone="Asia/Bangkok")


def test_render_rejects_an_unknown_timezone(make_plan: MakePlan) -> None:
    with pytest.raises(ValueError, match="Asia/Bangkog"):
        make_plan(_objects(1)).render(timezone="Asia/Bangkog")


def test_render_shows_paths_relative_to_the_working_directory_unless_asked_not_to(
    make_plan: MakePlan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    local = SourceObjectMetadata(path=str(tmp_path / "a.csv"), size_bytes=1, created_at=STAMP, modified_at=STAMP)
    plan = make_plan([local])

    assert "      a.csv " in plan.render()
    assert "      a.csv " not in plan.render(full_path=True)


def test_render_counts_the_rules_by_severity(make_plan: MakePlan) -> None:
    plan = make_plan(expectations=[_rule("a"), _rule("b"), _rule("c", "warning")])

    output = plan.render()

    assert "rules     : 3 totals" in output
    assert "2 critical" in output
    assert "1 warning" in output


def test_render_leaves_out_a_severity_with_no_rules(make_plan: MakePlan) -> None:
    output = make_plan(expectations=[_rule("a")]).render()

    assert "rules     : 1 total" in output
    assert "1 critical" in output
    assert "warning" not in output
    assert "info" not in output


@pytest.mark.parametrize("enabled", [False, True])
def test_render_shows_whether_data_docs_are_enabled(make_plan: MakePlan, tmp_path: Path, enabled: bool) -> None:
    plan = make_plan(data_docs={"enabled": enabled, "store_path": str(tmp_path / "docs")})

    assert f"data docs : {'enabled' if enabled else 'disabled'}" in plan.render()


def test_render_hides_the_rules_unless_asked(make_plan: MakePlan) -> None:
    assert "expectation_type:" not in make_plan().render()


def test_render_full_rules_numbers_them_across_severity_groups(make_plan: MakePlan) -> None:
    plan = make_plan(
        expectations=[
            _rule("col_1", "warning"),
            _rule("col_2", "critical"),
            _rule("col_3", "info"),
            _rule("col_4", "critical"),
        ]
    )

    lines = plan.render(full_rules=True).splitlines()
    numbered = [line.split()[0] for line in lines if "expectation_type:" in line]
    columns = [line.split(": ")[1] for line in lines if line.strip().startswith("column:")]

    assert numbered == ["1", "2", "3", "4"]
    assert columns == ["col_2", "col_4", "col_1", "col_3"]
    assert any("critical · 2 rules" in line for line in lines)
    assert any("warning · 1 rule" in line for line in lines)
    assert any("info · 1 rule" in line for line in lines)


def test_render_full_rules_omits_the_kwargs_block_of_a_rule_without_kwargs(make_plan: MakePlan) -> None:
    rule = {"expectation_type": "expect_table_row_count_to_be_between", "severity": "critical"}
    plan = make_plan(expectations=[rule])

    output = plan.render(full_rules=True)

    assert "expectation_type: expect_table_row_count_to_be_between" in output
    assert "kwargs:" not in output


@pytest.mark.parametrize("action", ["ignore", "delete"])
def test_render_on_failure_has_no_dead_letter_for_actions_without_a_destination(
    make_plan: MakePlan, action: str
) -> None:
    output = make_plan(on_failure={"action": action}).render()

    assert f"action : {action}" in output
    assert "dead letter" not in output


@pytest.mark.parametrize("action", ["move", "copy"])
def test_render_on_failure_shows_the_dead_letter_for_relocating_actions(make_plan: MakePlan, action: str) -> None:
    output = make_plan(on_failure={"action": action, "dead_letter": "output/dead-letters/"}).render()

    assert f"action      : {action}" in output
    assert "dead letter : output/dead-letters" in output


def test_render_report_shows_where_it_is_saved_and_how_many_expectations_it_covers(make_plan: MakePlan) -> None:
    output = make_plan(expectations=[_rule("a"), _rule("b")]).render()

    assert "save on      : output/reports/" in output
    assert "expectations : 2" in output


def test_render_closes_with_a_summary_line(make_plan: MakePlan) -> None:
    plan = make_plan(_objects(2), expectations=[_rule("a"), _rule("b")])

    assert plan.render().rstrip().splitlines()[-1] == "  Plan: 2 objects · 2 expectations"


def test_render_summary_line_is_singular_for_one_expectation(make_plan: MakePlan) -> None:
    plan = make_plan(_objects(1), expectations=[_rule("a")])

    assert plan.render().rstrip().splitlines()[-1] == "  Plan: 1 object · 1 expectation"


def test_render_is_identical_when_called_twice(make_plan: MakePlan) -> None:
    plan = make_plan(_objects(3))

    assert plan.render() == plan.render()


def test_render_whole_plan(make_plan: MakePlan) -> None:
    sized = [obj.model_copy(update={"size_bytes": 410 * index}) for index, obj in enumerate(_objects(3), start=1)]
    plan = make_plan(
        sized,
        file_path="data/test_*.csv",
        options={"delimiter": ",", "encoding": "utf-8"},
        expectations=[
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {"column": "amount", "min_value": 0, "max_value": 5},
                "severity": "warning",
            },
            _rule("id"),
        ],
    )

    assert (
        plan.render(full_rules=True)
        == """
  PYLOS plan · planner-test · pandas

╭─ source ───────────────────────────────────────────────────────────────────╮
│  storage  : local                                                          │
│  reader   : pandas.read_csv                                                │
│  options  : delimiter=","                                                  │
│             encoding="utf-8"                                               │
│  pattern  : data/test_*.csv                                                │
│  on_empty : skip                                                           │
╰────────────────────────────────────────────────────────────────────────────╯

    3 objects resolved · 2.4 KB

      gs://bucket/data/test_1.csv      410 B   modified 2026-09-08 21:25
      gs://bucket/data/test_2.csv      820 B   modified 2026-09-08 21:25
      gs://bucket/data/test_3.csv     1.2 KB   modified 2026-09-08 21:25

╭─ validate ─────────────────────────────────────────────────────────────────╮
│  contract  : orders                                                        │
│  rules     : 2 totals                                                      │
│              1 critical                                                    │
│              1 warning                                                     │
│  data docs : disabled                                                      │
╰────────────────────────────────────────────────────────────────────────────╯

    critical · 1 rule

       1  expectation_type: expect_column_values_to_not_be_null
          kwargs:
            column: id

    warning · 1 rule

       2  expectation_type: expect_column_values_to_be_between
          kwargs:
            column: amount
            min_value: 0
            max_value: 5

╭─ on failure ───────────────────────────────────────────────────────────────╮
│  action      : move                                                        │
│  dead letter : output/dead-letters                                         │
╰────────────────────────────────────────────────────────────────────────────╯

╭─ report ───────────────────────────────────────────────────────────────────╮
│  save on      : output/reports/                                            │
│  expectations : 2                                                          │
╰────────────────────────────────────────────────────────────────────────────╯

  Plan: 3 objects · 2 expectations
"""
    )


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


def test_plan_lists_the_matching_files_with_their_size(make_engine: MakeEngine, source_dir: Path) -> None:
    (source_dir / "a.csv").write_bytes(b"id\n1\n")
    (source_dir / "ignored.txt").write_bytes(b"not a csv")

    plan = Planner(make_engine()).plan()

    [only] = plan.source_objects
    assert only.path == str((source_dir / "a.csv").resolve())
    assert only.size_bytes == len(b"id\n1\n")


def test_plan_sorts_numbers_by_value_not_by_digit(make_engine: MakeEngine, source_dir: Path) -> None:
    for name in ("test_2.csv", "test_10.csv", "test_1.csv"):
        (source_dir / name).write_bytes(b"id\n1\n")

    plan = Planner(make_engine()).plan()

    assert [Path(obj.path).name for obj in plan.source_objects] == ["test_1.csv", "test_2.csv", "test_10.csv"]


def test_plan_sorting_is_stable_for_names_equal_as_numbers(make_engine: MakeEngine, source_dir: Path) -> None:
    for name in ("test_1.csv", "test_01.csv", "test_001.csv"):
        (source_dir / name).write_bytes(b"id\n1\n")

    names = [Path(obj.path).name for obj in Planner(make_engine()).plan().source_objects]

    assert names == sorted(names, key=lambda name: name)
    assert names == [Path(obj.path).name for obj in Planner(make_engine()).plan().source_objects]


def test_plan_sorting_ignores_letter_case(make_engine: MakeEngine, source_dir: Path) -> None:
    for name in ("B.csv", "a.csv", "C.csv"):
        (source_dir / name).write_bytes(b"id\n1\n")

    plan = Planner(make_engine()).plan()

    assert [Path(obj.path).name for obj in plan.source_objects] == ["a.csv", "B.csv", "C.csv"]


def test_plan_carries_the_declaration_over_unchanged(make_engine: MakeEngine, source_dir: Path) -> None:
    (source_dir / "a.csv").write_bytes(b"id\n1\n")
    engine = make_engine()

    plan = Planner(engine).plan()

    assert plan.engine_id == ENGINE_ID
    assert plan.engine_name == "pandas"
    assert plan.source is engine.source
    assert plan.contract is engine.validation.contract
    assert plan.on_failure is engine.on_failure
    assert plan.report is engine.report
    assert plan.data_docs_enabled is False


def test_plan_is_a_snapshot_of_the_moment_it_was_made(make_engine: MakeEngine, source_dir: Path) -> None:
    (source_dir / "a.csv").write_bytes(b"id\n1\n")
    plan = Planner(make_engine()).plan()

    (source_dir / "late.csv").write_bytes(b"id\n2\n")

    assert len(plan.source_objects) == 1
    assert "1 object resolved" in plan.render()


@pytest.mark.usefixtures("source_dir")
def test_plan_raises_when_nothing_matches_the_pattern(make_engine: MakeEngine) -> None:
    # LocalStorage.glob raises on an empty listing, so a dry run over no files fails here instead
    # of rendering "0 objects resolved". That branch is reachable only through a hand-built Plan.
    with pytest.raises(FileNotFoundError):
        Planner(make_engine()).plan()
