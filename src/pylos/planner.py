"""Resolves a config against reality: which files the glob matches, and a printable plan of the work."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pylos.actions import OnFailureActionConfig, RelocateFailureAction
from pylos.engines import Engine
from pylos.gx.models import ContractConfig, ExpectationConfig
from pylos.results import Severity, SourceObjectMetadata
from pylos.sinks import SinkConfig
from pylos.sources import SourceConfig
from pylos.storages import StorageBackend

_BOX_WIDTH = 78
_OBJECT_PREVIEW = 5
_PATH_WIDTH = 42
_SEVERITY_ORDER = (Severity.CRITICAL, Severity.WARNING, Severity.INFO)


def _elide_path(path: str) -> str:
    """Shortens a path for display by cutting from the left.

    The end of a path is what identifies it: the file name, and usually a
    folder or two above it. The prefix at the front ("the whole project lives
    under C:/Users/.../cosmos/...") tells the reader nothing new after the
    first line, so that is the part to cut. A single "…" marks where text was
    removed.

    Args:
        path: The path to shorten, as it would otherwise be printed.

    Returns:
        ``path`` unchanged if it fits within ``_PATH_WIDTH`` characters,
        otherwise its rightmost ``_PATH_WIDTH - 1`` characters prefixed with
        "…".

    Examples:
        A 79-character absolute path becomes:

            >>> _elide_path("C:/Users/armlo/.../cosmos/data/test_1.csv")
            '…t/personal-project/cosmos/data/test_1.csv'

        A short path like ``"data/test_1.csv"`` is already under the width
        limit and comes back unchanged.

    Note:
        The width is the module-level ``_PATH_WIDTH`` constant, so changing
        how much of the path shows never requires editing this function. The
        only caller is the object listing (``Plan._object_lines``), so a new
        width affects that one column.
    """
    if len(path) <= _PATH_WIDTH:
        return path
    return "…" + path[-(_PATH_WIDTH - 1) :]


def _relative_to_cwd(path: str) -> str:
    """Rewrites a local path relative to the current directory, when it can.

    ``LocalStorage`` resolves every object's path to an absolute one (see
    ``storages/local.py``). That identifies a file uniquely but is hard to
    read in a terminal: a plan run from the project root should show
    ``data/test_1.csv``, not
    ``C:/Users/armlo/OneDrive/Desktop/Project/personal-project/cosmos/data/test_1.csv``.
    This function shortens the path for display only. Callers pass the
    original ``obj.path`` everywhere else, so the ``source_object`` key the
    report uses is unchanged.

    Args:
        path: An absolute (or otherwise non-relative) path or URI, as stored
            on ``SourceObjectMetadata.path``.

    Returns:
        ``path`` relative to :func:`pathlib.Path.cwd`, or ``path`` unchanged
        when that is not possible: a URI from another backend
        (``gs://bucket/key`` has no filesystem location to relativize), or a
        local path outside the current tree (a different drive on Windows,
        or anywhere ``Path.relative_to`` would raise).

    Examples:
        Run from the project root, with the CWD at
        ``.../cosmos``:

            >>> _relative_to_cwd(".../cosmos/data/test_1.csv")
            'data/test_1.csv'
            >>> _relative_to_cwd("gs://my-bucket/data/test_1.csv")
            'gs://my-bucket/data/test_1.csv'

    Note:
        Only called for ``Plan.render(full_path=False)``, the default; pass
        ``full_path=True`` to show the path exactly as stored. If a future
        storage backend needs its own notion of "relative", add a URI scheme
        check here instead of a second function, since every call site
        already goes through this one.
    """
    if "://" in path:
        return path
    try:
        return str(Path(path).resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return path


def _human_size(size_bytes: float) -> str:
    """Formats a byte count so a person scanning a terminal can judge it.

    ``SourceObjectMetadata.size_bytes`` is the plain integer ``os.stat``
    reports, and nobody reading a plan wants to divide it by a million to see
    whether a file is big. This steps up through B, KB, MB and GB, stopping
    at the first unit where the number is under 1024.

    Args:
        size_bytes: A non-negative byte count, usually ``obj.size_bytes`` or
            a sum of several.

    Returns:
        The size with its unit: whole bytes for "B" ("410 B", never
        "410.0 B"), and one decimal place above that ("2.0 KB", "5.0 MB").
        Anything of a gigabyte or more stays in GB, even with more than three
        digits before the point.

    Examples:
        >>> _human_size(410)
        '410 B'
        >>> _human_size(2048)
        '2.0 KB'
        >>> _human_size(5 * 1024 * 1024)
        '5.0 MB'

    Note:
        The final ``raise AssertionError`` is unreachable, because the "GB"
        iteration always returns. It is there so a type checker can see that
        the function always returns a ``str``. To add a "TB" tier, extend
        the unit tuple; the divide-by-1024 loop already handles any number
        of units.
    """
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024 or unit == "GB":
            return f"{size_bytes:.0f} {unit}" if unit == "B" else f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    raise AssertionError("unreachable")


def _render_value(value: Any) -> str:
    """Renders one config value roughly as it looked in the YAML.

    Used for values shown as a ``key="value"`` pair, such as a source's
    reader ``options`` (``delimiter=","``). Every string is quoted, because
    the pair reads like a Python keyword argument, where a quoted string is
    always correct and never ambiguous. :func:`_render_kwarg_scalar`, used for
    the ``--full-rules`` block, quotes only when a bare string would change
    meaning. The two functions exist side by side because they render two
    different notations.

    Args:
        value: A single config value: a bool, string, list, number, or
            anything whose ``str()`` is already what should be shown.

    Returns:
        ``"true"``/``"false"`` for a bool, a double-quoted string for a
        ``str``, ``[item, item]`` for a list (each item rendered recursively
        and then unquoted, since a bracketed list already reads as one unit),
        or ``str(value)`` for anything else (``int``, ``float``, ``None``).
        A bool is checked first so it renders as YAML's ``true`` instead of
        falling through to ``str(value)`` as ``"True"``.

    Examples:
        >>> _render_value(True)
        'true'
        >>> _render_value("utf-8")
        '"utf-8"'
        >>> _render_value(["col_int64", "col_float64"])
        '[col_int64, col_float64]'
        >>> _render_value(0)
        '0'

    Note:
        To render a new value shape (a dict, say), add a branch before the
        final ``str(value)`` fallback. Both callers in this module (the
        source options in ``Plan._source_box`` and the scalar fallback in
        ``_render_kwarg_scalar``) go through this function, so the change
        reaches both.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_render_value(item).strip('"') for item in value) + "]"
    return str(value)


_TIMESTAMP_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _needs_quotes(value: str) -> bool:
    """Whether writing this string bare, as plain YAML, would change its meaning.

    ``--full-rules`` renders each expectation's ``kwargs`` like a hand-written
    YAML file (see ``Plan._rule_lines``), and in real YAML most strings have
    no quotes: ``column: col_int64``, not ``column: "col_int64"``. Some
    strings, though, are strings only on the Python side; a YAML parser
    reading the same bare text would get a bool, a number or a timestamp.
    This function detects those cases, so the renderer knows when it must
    quote to keep the value a string.

    Args:
        value: The exact text that would otherwise be written bare.

    Returns:
        True when a YAML parser would misread ``value`` unquoted: it is empty
        or has leading/trailing whitespace, it spells a bool or null
        (``"true"``, ``"None"``, ``"~"``, case-insensitively), it parses as a
        number (``float(value)`` succeeds), or it starts with a
        ``YYYY-MM-DD`` date. False for an ordinary identifier like a column
        name, which is unambiguous and reads better bare.

    Examples:
        >>> _needs_quotes("col_int64")
        False
        >>> _needs_quotes("2000-01-01 00:00:00")
        True
        >>> _needs_quotes("true")
        True
        >>> _needs_quotes(" col")
        True

    Note:
        This covers the shapes that appear in GX expectation ``kwargs`` today
        (dates, numbers as strings, and so on). If a future expectation adds
        a new ambiguous shape (a string that looks like a YAML list,
        ``"[1, 2]"``, say), add a check for it here. ``_render_kwarg_scalar``
        is the only caller and needs no change.
    """
    if value == "" or value.strip() != value:
        return True
    if value.lower() in {"true", "false", "null", "none", "yes", "no", "~"}:
        return True
    try:
        float(value)
    except ValueError:
        pass
    else:
        return True
    return bool(_TIMESTAMP_LIKE.match(value))


def _render_kwarg_scalar(value: Any) -> str:
    """Renders one kwarg value the way a hand-written YAML file would.

    The ``--full-rules`` counterpart to ``_render_value``: the same job in a
    different notation. ``_render_value`` always quotes a string, because it
    renders a Python-style ``key="value"`` pair. This function quotes only
    when :func:`_needs_quotes` says a bare string would be misread, so a
    column name like ``col_int64`` looks the way it does in the source YAML.
    Non-string values (bools, numbers) go straight to ``_render_value``,
    since they have no such ambiguity.

    Args:
        value: One value from an expectation's ``kwargs`` dict, e.g. the
            ``"col_int64"`` in ``{"column": "col_int64"}``.

    Returns:
        The bare string when it is unambiguous, a double-quoted string when
        it is not, or ``_render_value(value)`` for anything that is not a
        string.

    Examples:
        >>> _render_kwarg_scalar("col_int64")
        'col_int64'
        >>> _render_kwarg_scalar("2000-01-01 00:00:00")
        '"2000-01-01 00:00:00"'
        >>> _render_kwarg_scalar(True)
        'true'
        >>> _render_kwarg_scalar(5)
        '5'

    Note:
        ``_render_kwargs_lines`` calls this once for each value other than
        ``column_list``. It needs only the value, not the caller's
        indentation or ``key:`` prefix, so another part of the plan could
        reuse it for the same YAML-style rendering.
    """
    if isinstance(value, str):
        return f'"{value}"' if _needs_quotes(value) else value
    return _render_value(value)


def _render_kwargs_lines(kwargs: dict[str, Any], indent: str) -> list[str]:
    """Renders one expectation's kwargs, YAML-shaped, under the given indent.

    This is the body of one rule's ``kwargs:`` block in ``--full-rules``
    output. Keys appear in declaration order (a ``dict`` preserves it, and so
    does PyYAML's loader), each on its own line as ``key: value``, the same
    shape as the source YAML. ``column_list`` is the exception. It belongs to
    ``expect_table_columns_to_match_ordered_list``, which checks the columns'
    *order*, so the list is written one bare item per line instead of the
    one-line ``[a, b, c]`` any other list gets. That way a reader sees the
    order instead of inferring it from a bracket.

    Args:
        kwargs: One expectation's ``kwargs`` dict, e.g.
            ``{"column": "col_int64", "min_value": 0, "max_value": 5}``.
        indent: The literal whitespace prefix for every returned line, which
            the caller computes to line up under the rule's number (see
            ``Plan._rule_lines``).

    Returns:
        One line per key, each prefixed with ``indent``, ready to append to
        the plan's lines. A ``column_list`` key adds a ``"column_list:"``
        line plus one ``"  - <name>"`` line per column, indented two more
        spaces.

    Examples:
        >>> _render_kwargs_lines(
        ...     {"column": "col_int64", "min_value": 0, "max_value": 5},
        ...     indent="          ",
        ... )
        ['          column: col_int64', '          min_value: 0', '          max_value: 5']

    Note:
        ``column_list`` is matched by key name, not by shape (such as "any
        list longer than N items"), because it is the only GX kwarg where
        order is the point of the expectation. Other list-valued kwargs
        (``value_set``, say) are unordered and read fine as
        ``_render_value``'s ``[true, false]``. If a future expectation needs
        one item per line, add its key next to ``"column_list"`` in the
        condition below instead of exploding every list.
    """
    lines: list[str] = []
    for key, value in kwargs.items():
        if key == "column_list" and isinstance(value, list):
            lines.append(f"{indent}{key}:")
            lines.extend(f"{indent}  - {item}" for item in value)
        else:
            lines.append(f"{indent}{key}: {_render_kwarg_scalar(value)}")
    return lines


def _box(title: str, rows: list[tuple[str, str]]) -> list[str]:
    """Draws one titled box. Every box has the same width, so they stack cleanly.

    Every section of the plan (``source``, ``validate``, ``on failure``,
    ``report``) is drawn by this function; nothing else in the file builds a
    box border. A row is a ``(label, value)`` pair, laid out by two rules:

    1. Each row's colon sits one space after the longest label in *this* box
       (not the whole plan), so ``storage``, ``reader`` and ``options`` in
       the source box share one colon column despite their different
       lengths.
    2. A row labelled ``""`` continues the row above it, for one value that
       spans several lines (a wrapped list of reader options, or the
       per-severity rule counts). It has no label or colon, only enough
       leading whitespace to start under the first line's value, so the
       block reads as one item.

    Args:
        title: The box's name, shown in its top border (``"╭─ source ─..."``).
        rows: The box's content, top to bottom. At least one row must have a
            non-empty label, because the longest label sets the colon column.

    Returns:
        The box as a list of bordered, padded lines: a top border, one line
        per row, and a bottom border. Every line is exactly ``_BOX_WIDTH``
        characters, so stacked boxes have a straight right edge.

    Examples:
        >>> for line in _box("on failure", [("action", "move"), ("dead letter", "output/dead-letters")]):
        ...     print(line)
        ╭─ on failure ───────────────────────────────────────────────────────────────╮
        │  action      : move                                                        │
        │  dead letter : output/dead-letters                                         │
        ╰────────────────────────────────────────────────────────────────────────────╯

    Note:
        To change the total width, edit the module-level ``_BOX_WIDTH``
        constant, not this function. To change the alignment rule itself
        (left-aligning values instead of aligning colons, say), this is the
        only function to edit; every ``Plan._*_box`` method just builds
        ``rows`` and passes them here.
    """
    head = f"╭─ {title} "
    lines = [head + "─" * (_BOX_WIDTH - len(head) - 1) + "╮"]

    label_width = max(len(label) for label, _ in rows if label)
    for label, value in rows:
        if label:
            body = f"  {label.ljust(label_width + 1)}: {value}"
        else:
            body = " " * (label_width + 5) + value
        lines.append("│" + body.ljust(_BOX_WIDTH - 2) + "│")

    lines.append("╰" + "─" * (_BOX_WIDTH - 2) + "╯")
    return lines


@dataclass
class Plan:
    """What the run will do, resolved against reality, with nothing executed.

    The config alone cannot say which files a run will touch, and the file
    list alone cannot say what will happen to them. ``Plan`` holds both,
    which is why it is worth rendering before a run instead of after.

    ``Plan`` is a plain ``@dataclass``, not a Pydantic model, although every
    field it holds (``source``, ``contract``, ...) is a validated Pydantic
    model. Those models already ran their validators once, when the engine's
    YAML was loaded. A dataclass never re-runs them, whereas nesting a
    validated model inside another ``BaseModel`` can re-trigger its
    ``model_validator``\\ s unexpectedly. ``Plan`` only reads its fields: it
    is a snapshot, and only a test should construct one by hand.

    Attributes:
        engine_id: The pipeline's stable ``id``, shown in the header.
        engine_name: Which engine will read the data ("pandas", "spark", "sql").
        source: The declared source, for the pattern, reader and options.
        contract: The rules that will be applied to every object.
        on_failure: What happens to an object whose critical rules fail.
        report: Where the report is written, whatever the outcome.
        data_docs_enabled: Whether GX will also render its HTML view.
        source_objects: What the glob actually found, sorted by path.

    Examples:
        ``Planner.plan()`` normally builds it, but a test can construct one
        directly from fabricated data, without touching a real filesystem:

            >>> plan = Plan(
            ...     engine_id="test_config",
            ...     engine_name="pandas",
            ...     source=source_config,
            ...     contract=contract_config,
            ...     on_failure=IgnoreFailureAction(),
            ...     report=report_config,
            ...     data_docs_enabled=False,
            ...     source_objects=[],
            ... )
            >>> print(plan.render())
    """

    engine_id: str
    engine_name: str
    source: SourceConfig
    contract: ContractConfig
    on_failure: OnFailureActionConfig
    report: SinkConfig
    data_docs_enabled: bool
    source_objects: list[SourceObjectMetadata]

    def ordered_expectations(self) -> list[ExpectationConfig]:
        """Every rule, ordered by severity and then by declaration order.

        This is the single definition of rule order. ``_rule_lines`` uses it
        to number ``--full-rules`` output, and anything else that needs
        "rule 4" to mean the same rule every time (a report, a log line)
        should use it too. It is public, with no leading underscore, so those
        callers can reuse it instead of re-deriving the order.

        Both sort keys (a rule's ``severity`` and its position in
        ``self.contract.expectations``) come from the config alone, never
        from anything resolved at plan time. So the order is deterministic:
        the same contract numbers its rules identically on every run and on
        every machine.

        Returns:
            Every expectation in ``self.contract.expectations``, grouped by
            severity in the order ``critical``, ``warning``, ``info``
            (``_SEVERITY_ORDER``), in declaration order within each group.
            The list is new; the contract's own list is not modified.

        Examples:
            A contract declaring ``[warning_rule, critical_rule]`` (in that
            order) returns ``[critical_rule, warning_rule]``. Severity wins
            over declaration order, even though ``critical_rule`` was
            written second.

        Note:
            To change the severity order (``info`` before ``warning``, say),
            edit the module-level ``_SEVERITY_ORDER`` tuple. Neither this
            method nor its callers hardcode the three names, so they all
            follow automatically.
        """
        ordered: list[ExpectationConfig] = []
        for severity in _SEVERITY_ORDER:
            ordered.extend(rule for rule in self.contract.expectations if rule.severity == severity)
        return ordered

    def _source_box(self) -> list[str]:
        """Builds the ``╭─ source ─...`` box: where the data comes from.

        Turns ``self.source`` (a ``SourceConfig``) into ``(label, value)``
        rows for storage, reader, options, glob pattern and ``on_empty``,
        then passes them to ``_box``. This method does no drawing itself.

        Returns:
            The bordered box as a list of lines (see ``_box``). Each reader
            option gets its own row (``options`` on the first, an empty label
            on the rest), so ``{"delimiter": ",", "encoding": "utf-8"}``
            renders as two lines, one option each.

        Examples:
            For a CSV source with two options and a wildcard pattern, the
            box's rows read (label, value) as:

                ("storage", "local")
                ("reader", "pandas.read_csv")
                ("options", 'delimiter=","')
                ("", 'encoding="utf-8"')
                ("pattern", "data/test_*.csv")
                ("on_empty", "skip")

        Note:
            To show a new source field (a future ``compression`` option,
            say), add a row to ``rows`` here. ``_box`` aligns whatever rows
            it is given, so it needs no change.
        """
        rows = [
            ("storage", self.source.storage),
            ("reader", f"{self.engine_name}.read_{self.source.file_format}"),
        ]
        option_lines = [f"{key}={_render_value(value)}" for key, value in self.source.options.items()]
        for index, line in enumerate(option_lines):
            rows.append(("options" if index == 0 else "", line))
        rows.append(("pattern", self.source.file_path))
        rows.append(("on_empty", self.source.on_empty))
        return _box("source", rows)

    def _object_lines(self, full: bool, full_path: bool, tz: ZoneInfo) -> list[str]:
        """Lists the resolved source objects: what the glob actually found.

        This is the only part of the plan that reports on reality instead of
        the declaration. ``self.source_objects`` came from a real
        ``backend.glob()`` call (see ``Planner.prepare_source_metadata``), so
        the plan can say "12 objects, 5.1 KB" instead of "however many files
        match when the run starts". It sits outside the ``╭─...╮`` boxes
        (compare ``_source_box``) because a list of arbitrarily many files
        does not fit their fixed-width rows.

        Args:
            full: List every object instead of only the first
                ``_OBJECT_PREVIEW`` (5), with an index number on each line.
                Backs the CLI's future ``--full-objects`` flag.
            full_path: Show each object's path exactly as stored (absolute,
                for local files) instead of relative to the current
                directory. See ``_relative_to_cwd``.
            tz: The zone to render each object's ``modified_at`` timestamp
                in, already resolved by ``render()`` from its ``timezone``
                argument.

        Returns:
            Lines to insert into the plan: a blank line, a summary line
            ("N objects resolved · size"), a blank line, one line per listed
            object, and, when ``full`` is False and there are more than
            ``_OBJECT_PREVIEW`` objects, a final "… N more" line. When the
            glob matched nothing, only a blank line and "0 objects resolved".

        Examples:
            With ``full=False`` and three objects found:

                    3 objects resolved · 1.2 KB

                      data/test_1.csv                410 B   modified 2026-09-08 21:25
                      data/test_2.csv                533 B   modified 2026-08-28 00:07
                      data/test_3.csv                410 B   modified 2026-05-23 15:28

        Note:
            The preview count is the module-level ``_OBJECT_PREVIEW``
            constant, and the path column width is ``_PATH_WIDTH`` (through
            ``_elide_path``). Adjust those instead of the layout arithmetic
            in this method.
        """
        total = len(self.source_objects)
        total_size = sum(obj.size_bytes for obj in self.source_objects)

        noun = "object" if total == 1 else "objects"
        if not total:
            return ["", f"    0 {noun} resolved"]

        lines = ["", f"    {total:,} {noun} resolved · {_human_size(total_size)}", ""]

        shown = self.source_objects if full else self.source_objects[:_OBJECT_PREVIEW]
        for index, obj in enumerate(shown, start=1):
            size = _human_size(obj.size_bytes).rjust(8)
            stamp = obj.modified_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            display_path = obj.path if full_path else _relative_to_cwd(obj.path)
            prefix = f"{index:>8}  " if full else "      "
            lines.append(f"{prefix}{_elide_path(display_path).ljust(30)}{size}   modified {stamp}")

        if not full and total > _OBJECT_PREVIEW:
            lines.append(f"      … {total - _OBJECT_PREVIEW:,} more")
        return lines

    def _validate_box(self) -> list[str]:
        """Builds the ``╭─ validate ─...`` box: the contract, summarized.

        Shows counts only ("9 totals", then "8 critical" and "1 warning"),
        never the rules themselves. The rules are left to ``_rule_lines``,
        shown only with ``--full-rules``, because counts fit in a
        fixed-height box and a rule list does not. The per-severity rows are
        continuation rows, like the options in ``_source_box``: a first row
        labelled ``rules``, then one unlabelled row per severity that has at
        least one rule, which ``_box`` lines up under "N totals".

        Returns:
            The bordered box (see ``_box``). A severity with no rules gets no
            row, so a contract with only critical rules shows no "0 warning"
            line.

        Examples:
            For a contract with 8 critical rules and 1 warning rule, the rows
            (label, value) read:

                ("contract", "test_1_schema")
                ("rules", "9 totals")
                ("", "8 critical")
                ("", "1 warning")
                ("data docs", "disabled")

        Note:
            The severities come from the module-level ``_SEVERITY_ORDER``, as
            everywhere else in the file. Adding a fourth severity there is
            all it takes for it to appear here.
        """
        total = len(self.contract.expectations)
        noun = "total" if total == 1 else "totals"

        rows = [
            ("contract", self.contract.data_asset_name),
            ("rules", f"{total} {noun}"),
        ]
        for severity in _SEVERITY_ORDER:
            count = sum(1 for rule in self.contract.expectations if rule.severity == severity)
            if count:
                rows.append(("", f"{count} {severity}"))
        rows.append(("data docs", "enabled" if self.data_docs_enabled else "disabled"))
        return _box("validate", rows)

    def _rule_lines(self) -> list[str]:
        """Every rule, numbered and grouped by severity, with kwargs shown YAML-style.

        Only called for ``render(full_rules=True)``. The default plan shows
        just ``_validate_box``'s counts, because twelve multi-line rule
        blocks is a lot to show someone who only wants to know whether the
        plan looks right. Each rule renders like an entry in the contract
        YAML (``expectation_type:``, then an indented ``kwargs:`` block from
        ``_render_kwargs_lines``), except that the rule's number replaces the
        ``-`` of a YAML list. The number makes a rule addressable the same
        way in the plan and in a report ("rule 4 failed" means the same rule
        in both). Plain ``-`` bullets cannot do that, and neither can names,
        since not every rule has one.

        Returns:
            Lines to insert into the plan. For each severity with at least
            one rule: a blank line and a "<severity> · N rules" header, then
            for each rule a blank line, its numbered ``expectation_type:``
            line, and an indented ``kwargs:`` block if it has kwargs. Empty
            if the contract has no expectations.

        Examples:
            A single ``expect_column_values_to_not_be_null`` critical rule
            on ``col_int64`` renders as:

                    critical · 1 rule

                       1  expectation_type: expect_column_values_to_not_be_null
                          kwargs:
                            column: col_int64

        Note:
            Numbering starts at 1 and continues across every severity group
            without resetting, which is why ``number`` is declared once,
            outside the ``for severity`` loop, and only ever incremented.
        """
        ordered = self.ordered_expectations()
        if not ordered:
            return []

        lines: list[str] = []
        number = 0
        for severity in _SEVERITY_ORDER:
            group = [rule for rule in ordered if rule.severity == severity]
            if not group:
                continue
            noun = "rule" if len(group) == 1 else "rules"
            lines.extend(["", f"    {severity} · {len(group)} {noun}"])
            for rule in group:
                number += 1
                prefix = f"{number:>8}  "
                indent = " " * len(prefix)
                lines.append("")
                lines.append(f"{prefix}expectation_type: {rule.expectation_type}")
                if rule.kwargs:
                    lines.append(f"{indent}kwargs:")
                    lines.extend(_render_kwargs_lines(rule.kwargs, indent + "  "))
        return lines

    def _on_failure_box(self) -> list[str]:
        """Builds the ``╭─ on failure ─...`` box: what happens to a bad file.

        ``self.on_failure`` is a discriminated union (``IgnoreFailureAction``,
        ``DeleteFailureAction``, ``RelocateFailureAction``, ...). Only
        ``RelocateFailureAction`` (``move``/``copy``) has a destination worth
        showing; for every other action the ``action`` field says
        everything. So this is an ``isinstance`` check instead of a fixed set
        of rows: one row for ``action: ignore`` or ``action: delete``, two
        for ``action: move``, and ``_box`` does not need to know why.

        Returns:
            The bordered box (see ``_box``): always an ``action`` row, plus a
            ``dead letter`` row only when ``self.on_failure`` is a
            ``RelocateFailureAction``.

        Examples:
            For ``on_failure: {action: move, dead_letter: output/dead-letters/}``,
            the rows read ``[("action", "move"), ("dead letter", "output/dead-letters/")]``;
            for ``action: ignore``, just ``[("action", "ignore")]``.

        Note:
            A future action that needs an extra row (``copy`` showing whether
            it overwrites, say) follows the same pattern: add an
            ``isinstance`` branch here and leave ``_box`` alone.
        """
        rows: list[tuple[str, str]] = [("action", self.on_failure.action)]
        if isinstance(self.on_failure, RelocateFailureAction):
            rows.append(("dead letter", self.on_failure.dead_letter))
        return _box("on failure", rows)

    def _report_box(self) -> list[str]:
        """Builds the ``╭─ report ─...`` box: where the results are written.

        A report is always written, pass or fail (per the project's
        failure-handling rules), so unlike ``on failure`` this box has no
        conditional content: only where the report goes and how many
        expectations it covers (it holds one row per expectation per
        object). The object count is left out of the box, because it can be
        large and already has its own summary line in ``_object_lines``.

        Returns:
            The bordered box (see ``_box``), with a ``save on`` row (the
            sink's ``path`` if it has one, otherwise its ``storage``) and an
            ``expectations`` row.

        Examples:
            For a local file sink at ``output/reports/`` and a 9-rule
            contract, the rows read
            ``[("save on", "output/reports/"), ("expectations", "9")]``.

        Note:
            ``getattr(self.report, "path", None)`` is there because not every
            ``SinkConfig`` has a ``path`` (a BigQuery sink would not).
            Falling back to ``self.report.storage`` keeps the box working for
            any sink type without an ``isinstance`` check per type.
        """
        destination = getattr(self.report, "path", None) or self.report.storage
        rows = [
            ("save on", destination),
            ("expectations", str(len(self.contract.expectations))),
        ]
        return _box("report", rows)

    def render(
        self,
        full_objects: bool = False,
        full_rules: bool = False,
        full_path: bool = False,
        timezone: str = "UTC",
    ) -> str:
        """Renders the plan for a terminal. This is the module's public entry point.

        Everything else in ``Plan`` and the module-level helpers supports
        this method. A caller (a script today, a CLI ``--dry`` command later)
        only needs ``Planner(engine).plan().render()``. It assembles the
        boxes and the object listing in a fixed order (source, objects,
        validate, rules, on failure, report, summary). Every argument
        controls verbosity only. None of them changes what the run would do,
        only how much of it this call prints.

        Args:
            full_objects: List every resolved object instead of the first
                five (see ``_object_lines``). For a future CLI
                ``--full-objects`` flag.
            full_rules: List every rule, not just the per-severity counts
                (see ``_rule_lines``). For a future CLI ``--full-rules``
                flag.
            full_path: Show each object's path exactly as stored instead of
                relative to the current directory (see ``_relative_to_cwd``).
                For a future CLI ``--full-path`` flag.
            timezone: IANA zone name to render each object's modified time
                in, e.g. ``"Asia/Bangkok"``. It is the reader's preference,
                not part of the plan, so it is a render argument instead of a
                ``Plan`` field: the same ``Plan`` renders in whatever zone
                the reader asks for, without being rebuilt.

        Returns:
            The complete plan as one multi-line string, ready to ``print()``.
            Every line is padded or bordered to a consistent width (see
            ``_BOX_WIDTH``), so it lines up in a monospace terminal.

        Raises:
            ValueError: ``timezone`` is not a recognized IANA zone name (a
                typo like ``"Asia/Bangkog"``, for example). The check runs at
                the start of the call, before any line is built, so a bad
                timezone never produces a half-rendered plan.

        Examples:
            >>> print(Planner(engine).plan().render())
              PYLOS plan · test_config · pandas
            <BLANKLINE>
            ╭─ source ───────────────────────────────────────────────────────────────────╮
            │  storage  : local                                                          │
            ...
              Plan: 1 object · 9 expectations

        Note:
            To add a section (a future ``runtime`` box once checkpointing
            exists, say), write a ``Plan._runtime_box`` method like the
            others and call it here at the right point in the sequence. The
            existing boxes need no change.
        """
        try:
            tz = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown IANA timezone {timezone!r}.") from exc

        total = len(self.source_objects)
        noun = "object" if total == 1 else "objects"
        rule_count = len(self.contract.expectations)
        rule_noun = "expectation" if rule_count == 1 else "expectations"

        lines = ["", f"  PYLOS plan · {self.engine_id} · {self.engine_name}", ""]
        lines.extend(self._source_box())
        lines.extend(self._object_lines(full=full_objects, full_path=full_path, tz=tz))
        lines.append("")
        lines.extend(self._validate_box())
        if full_rules:
            lines.extend(self._rule_lines())
        lines.append("")
        lines.extend(self._on_failure_box())
        lines.append("")
        lines.extend(self._report_box())
        lines.extend(["", f"  Plan: {total:,} {noun} · {rule_count} {rule_noun}", ""])
        return "\n".join(lines)


class Planner:
    """Turns a declaration into the concrete work a run would do.

    It resolves the source glob, and it is the only part of a dry run that
    touches the outside world. It only lists: no file is opened, no
    expectation is run, nothing is moved and nothing is written, so a dry run
    has no side effect here to switch off.

    ``Planner`` (which does the I/O) and ``Plan`` (the dataclass above, pure
    formatting) are separate classes. That lets ``Plan.render()`` be tested
    with fabricated data and no real filesystem, and lets the same resolved
    ``Plan`` be rendered several times (different ``timezone``,
    ``full_rules``, ...) without globbing again.

    Examples:
        >>> from pylos.loader import from_yaml
        >>> engine = from_yaml("data/template_test.yml")
        >>> print(Planner(engine).plan().render())
          PYLOS plan · test_config · pandas
        ...
    """

    def __init__(self, engine: Engine) -> None:
        """Builds a ``Planner`` for one engine's declaration.

        Args:
            engine: The loaded, validated pipeline declaration (usually the
                result of ``pylos.loader.from_yaml(...)``). ``Planner`` does
                not re-read or re-validate it; config mistakes were already
                caught at load time.

        Note:
            ``self.backend`` is pulled out here only so
            ``prepare_source_metadata`` can read ``self.backend.glob(...)``
            instead of ``self.engine.source.backend.glob(...)``. It is the
            same object as ``engine.source.backend``, not a copy.
        """
        self.engine = engine
        self.source_config = self.engine.source
        self.validation_config = self.engine.validation
        self.backend: StorageBackend = self.source_config.backend

    def prepare_source_metadata(self) -> list[SourceObjectMetadata]:
        """Resolves the source's glob pattern against the filesystem, now.

        This is the only I/O in the module; everything else in
        ``planner.py`` formats data that was already fetched. Two calls can
        return different answers, because a file can appear or disappear in
        between. That is why ``Plan`` is a snapshot: ``Planner.plan()`` calls
        this once, and every part of ``render()`` reports against that one
        list, so the numbers in a printed plan always agree with each other
        even if the filesystem keeps changing.

        Returns:
            Every object the source's glob pattern matched, as
            ``SourceObjectMetadata`` (path, size, modified time), sorted
            alphabetically by path. The backend's ``glob`` does the sorting,
            so the plan lists objects in the same order the runner will
            process them, and the five-object preview in
            ``Plan._object_lines`` is the same on every run.

        Examples:
            For ``source.file_path: "data/test_*.csv"`` matching three
            files, this returns three items sorted as
            ``test_1.csv, test_2.csv, test_3.csv``, each with its own
            ``size_bytes`` and ``modified_at`` timestamp from the filesystem.

        Note:
            What "glob" means for local files or a GCS bucket is decided by
            the storage backend (``self.backend.glob``, e.g.
            ``storages/local.py``). This method only calls it, so it works
            unchanged for every backend that implements ``StorageBackend``.
        """
        return self.backend.glob(pattern=self.source_config.file_path)

    def plan(self) -> Plan:
        """Resolves the declaration into a ``Plan``. This is the class's main entry point.

        Other code (a future CLI, a test, the examples in this module) calls
        this method; everything else on ``Planner`` and ``Plan`` supports it.
        It does two things: it resolves the source's glob against the
        filesystem (``prepare_source_metadata``), and it copies every other
        field from ``self.engine`` unchanged, since those are declared, not
        discovered.

        Returns:
            A ``Plan`` combining ``self.engine``'s declaration with the
            result of ``prepare_source_metadata()``. Call ``.render()`` on it
            to get the printable plan.

        Examples:
            >>> plan = Planner(engine).plan()
            >>> plan.engine_id
            'test_config'
            >>> len(plan.source_objects)
            1

        Note:
            To resolve something else at plan time (checking that the report
            sink's directory is writable, say), do the work here and pass the
            result to ``Plan(...)`` as another field, the way
            ``source_objects`` is passed. ``Plan`` stays a plain snapshot of
            the result.
        """
        return Plan(
            engine_id=self.engine.id,
            engine_name=self.engine.engine,
            source=self.source_config,
            contract=self.validation_config.contract,
            on_failure=self.engine.on_failure,
            report=self.engine.report,
            data_docs_enabled=self.validation_config.data_docs.enabled,
            source_objects=self.prepare_source_metadata(),
        )
