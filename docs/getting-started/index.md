---
icon: material/rocket-launch-outline
---

# Getting started

A Pylos pipeline is one YAML file. This page shows a complete one with every key that works today,
runs it on two small CSV files, and reads what comes out.

!!! info "Install"

    Pylos is not on PyPI yet. From a clone of the repository, `uv sync` installs it with its
    dependencies.

## 📝 A complete config

Each numbered marker explains one key and links to its entry in the
[API Reference](../reference/index.md). The section headings in the explanations lead to the
[Configuration](../configuration/index.md) pages, where each key has more examples.

```yaml title="pipeline.yml"
id: orders_daily # (1)!
engine: pandas # (2)!

source: # (3)!
  storage: local # (4)!
  file_format: csv # (5)!
  file_path: data/orders_*.csv # (6)!
  on_empty: fail # (7)!
  options: # (8)!
    delimiter: ","
    encoding: utf-8

validation: # (9)!
  contract: # (10)!
    name: orders # (11)!
    description: Rules every daily orders file must satisfy. # (12)!
    expectations: # (13)!
      - expectation_type: expect_column_values_to_not_be_null # (14)!
        kwargs: # (15)!
          column: id
        severity: critical # (16)!
        name: id_not_null # (17)!
        description: An order without an id cannot be reconciled. # (18)!
        notes: Added after the 2026-03 incident. # (19)!
        meta: # (20)!
          owner: data-platform
      - expectation_type: expect_column_values_to_be_between
        kwargs:
          column: amount
          min_value: 0
        severity: warning
        name: amount_not_negative
  data_docs: # (21)!
    enabled: true
    store_path: output/data_docs/ # (22)!

on_failure: # (23)!
  action: move # (24)!
  dead_letter: output/dead-letters/ # (25)!
  mode: decision # (26)!

report: # (27)!
  storage: local # (28)!
  format: file # (29)!
  path: output/reports/ # (30)!
```

1. The name of the pipeline. It becomes part of the report's `run_id`, so keep it stable.
   See [`BaseEngine.id`][pylos.engines.base.BaseEngine.id].
2. Picks the engine that reads the data. Only `pandas` exists so far.
   See [`PandasEngine.engine`][pylos.engines.pandas.PandasEngine.engine].
3. Where the data comes from. See [`BaseEngine.source`][pylos.engines.base.BaseEngine.source] and
   the [Source](../configuration/source.md) page.
4. Where the files live: `local` for the filesystem. See
   [`LocalSourceConfig.storage`][pylos.sources.local.LocalSourceConfig.storage] and
   [`storage`](../configuration/source.md#storage).
5. How to read each file. Only `csv` is read today. See
   [`FileBaseConfig.file_format`][pylos.sources.base.FileBaseConfig.file_format].
6. A path or glob. Every match is read and validated on its own. See
   [`FileBaseConfig.file_path`][pylos.sources.base.FileBaseConfig.file_path] and
   [`file_path`](../configuration/source.md#file_path).
7. What to do with a file that has a header but no rows. See
   [`FileBaseConfig.on_empty`][pylos.sources.base.FileBaseConfig.on_empty] and
   [`on_empty`](../configuration/source.md#on_empty).
8. Options handed straight to `pd.read_csv`. See
   [`FileBaseConfig.options`][pylos.sources.base.FileBaseConfig.options] and
   [`options`](../configuration/source.md#options).
9. What to check. See [`BaseEngine.validation`][pylos.engines.base.BaseEngine.validation] and the
   [Validation](../configuration/validation.md) page.
10. The rules for this dataset. See [`GXConfig.contract`][pylos.gx.models.GXConfig.contract].
11. The contract's name. It also appears in `run_id`. In the model this field is
    [`ContractConfig.data_asset_name`][pylos.gx.models.ContractConfig.data_asset_name], read from
    the YAML key `name`.
12. Free text about the contract's purpose.
    See [`ContractConfig.description`][pylos.gx.models.ContractConfig.description].
13. The list of expectations. See
    [`ContractConfig.expectations`][pylos.gx.models.ContractConfig.expectations] and
    [`expectations`](../configuration/validation.md#expectations).
14. A Great Expectations expectation, by its GX name. See
    [`ExpectationConfig.expectation_type`][pylos.gx.models.ExpectationConfig.expectation_type].
15. The expectation's own arguments, passed to GX unchanged. See
    [`ExpectationConfig.kwargs`][pylos.gx.models.ExpectationConfig.kwargs].
16. `critical`, `warning` or `info`. Only a failing `critical` expectation triggers `on_failure`.
    Defaults to `critical`. See
    [`ExpectationConfig.severity`][pylos.gx.models.ExpectationConfig.severity] and
    [`severity`](../configuration/validation.md#severity).
17. A readable name for the rule in the report. Without one it becomes `<contract name>_<expectation_type>`. See
    [`ExpectationConfig.name`][pylos.gx.models.ExpectationConfig.name].
18. Why the rule exists. See
    [`ExpectationConfig.description`][pylos.gx.models.ExpectationConfig.description].
19. A free-form note, or a list of notes. See
    [`ExpectationConfig.notes`][pylos.gx.models.ExpectationConfig.notes].
20. Any metadata you want carried along. The name `expectation_key` is reserved. See
    [`ExpectationConfig.meta`][pylos.gx.models.ExpectationConfig.meta].
21. An optional HTML view of the results from Great Expectations. Off unless you enable it. See
    [`GXConfig.data_docs`][pylos.gx.models.GXConfig.data_docs] and
    [`data_docs`](../configuration/validation.md#data_docs).
22. Where to write the HTML. Required when `enabled` is true. See
    [`DataDocsConfig.store_path`][pylos.gx.models.DataDocsConfig.store_path].
23. What happens to a source file that fails. It sits beside `validation`, not inside it. See
    [`BaseEngine.on_failure`][pylos.engines.base.BaseEngine.on_failure] and the
    [On failure](../configuration/on-failure.md) page.
24. `ignore`, `move`, `copy` or `delete`. See
    [`MoveFailureAction.action`][pylos.actions.MoveFailureAction.action].
25. The directory that receives moved or copied files. Needed for `move` and `copy`. See
    [`RelocateFailureAction.dead_letter`][pylos.actions.RelocateFailureAction.dead_letter].
26. When the action fires: `decision` (default) only for data judged bad, `any_failure` also for
    files Pylos could not read. See [`BaseFailureAction.mode`][pylos.actions.BaseFailureAction.mode]
    and [`mode`](../configuration/on-failure.md#mode).
27. Where the results are written. See [`BaseEngine.report`][pylos.engines.base.BaseEngine.report]
    and the [Report](../configuration/report.md) page.
28. `local` writes to the filesystem. See [`LocalSink.storage`][pylos.sinks.local.LocalSink.storage].
29. `file` writes one JSON document. See
    [`BaseFileFormat.format`][pylos.sinks.base.BaseFileFormat.format].
30. The directory for the report. See [`BaseFileFormat.path`][pylos.sinks.base.BaseFileFormat.path].

## 🚀 Run it

Make two small files for the config above to read. The second one has a missing id and a negative
amount.

```csv title="data/orders_good.csv"
id,amount
1,10
2,25
3,40
```

```csv title="data/orders_bad.csv"
id,amount
1,10
,25
3,-5
```

Load the config and hand it to a [`Runner`][pylos.runner.Runner]:

```python
from pylos.loader import from_yaml
from pylos.runner import Runner

Runner(from_yaml("pipeline.yml")).run()
```

`run()` returns nothing. Everything it learned is in the report.

## 📦 What you get

`orders_bad.csv` broke a critical rule, so it moved to the dead-letter directory. `orders_good.csv`
stayed where it was.

```text
data/orders_good.csv
output/dead-letters/orders_bad.csv
output/reports/orders-orders_daily.json
output/data_docs/
```

The report is one JSON document per run. This is an abridged copy of what the run above wrote
(paths and timings shortened, one of the two files shown):

```json
{
  "pylos_version": "0.0.1",
  "run_id": "orders-orders_daily",
  "run_ts": "2026-10-16T17:06:42.112985Z",
  "results": [
    {
      "status": "completed",
      "source_object": {
        "path": ".../data/orders_bad.csv",
        "size_bytes": 24
      },
      "row_count": 3,
      "column_count": 2,
      "decision": "failed",
      "expectations": [
        {
          "success": false,
          "expectation_name": "id_not_null",
          "severity": "critical",
          "unexpected_count": 1,
          "unexpected_percent": 33.33333333333333,
          "unexpected_index": [1]
        },
        {
          "success": false,
          "expectation_name": "amount_not_negative",
          "severity": "warning",
          "unexpected_count": 1,
          "unexpected_values": [-5]
        }
      ],
      "action": {
        "action": "move",
        "status": "completed",
        "dead_letter": "output/dead-letters",
        "error": null
      }
    }
  ],
  "run_status": "completed",
  "decision": "failed"
}
```

Two verdicts sit at the top. `run_status` says Pylos finished its job, and `decision` says the data
was bad because one file failed. [Failure policy](../concepts/failure-policy.md) explains how they are
decided, and [Reporting](../concepts/reporting.md) covers the rest of the report.

## 🧭 Where to go next

- [Source](../configuration/source.md), [Validation](../configuration/validation.md),
  [On failure](../configuration/on-failure.md) and [Report](../configuration/report.md) list every
  option of each section with examples.
- [Planned keys](../configuration/planned.md) lists what the design includes but the code does not
  accept yet.
