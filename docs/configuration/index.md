---
icon: material/cog-outline
---

# Configuration

A config file has six top-level keys.

!!! warning "Misspelled keys are not always caught"

    A key Pylos does not know is rejected at the top level, in `source` and in `on_failure`. Inside
    `validation`, `report` and each expectation it is ignored without an error, so
    `severty: warning` runs as `critical` and `enabeld: true` leaves Data Docs off. Check the
    spelling there.

| Key | What it holds | Page |
|---|---|---|
| `id` | The pipeline's name, part of every `run_id` | [Getting started](../getting-started/index.md) |
| `engine` | What reads the data. Only `pandas` today | [Getting started](../getting-started/index.md) |
| `source` | Where the files are and how to read them | [Source](source.md) |
| `validation` | The contract and the Data Docs setting | [Validation](validation.md) |
| `on_failure` | What happens to a file that fails | [On failure](on-failure.md) |
| `report` | Where the results are written | [Report](report.md) |

The smallest config that loads:

```yaml title="minimal.yml"
id: orders_daily
engine: pandas

source:
  storage: local
  file_format: csv
  file_path: data/orders_*.csv

validation:
  contract:
    name: orders
    expectations:
      - expectation_type: expect_column_values_to_not_be_null
        kwargs:
          column: id

on_failure:
  action: ignore

report:
  storage: local
  format: file
  path: output/reports/
```

Every example on these pages is loaded by a test, so an example that stops matching the code fails
the build. Examples marked as planned are the exception, because they show keys the code does not
accept yet.

## Defaults

| Key | Default |
|---|---|
| `source.on_empty` | `skip` |
| `source.options` | empty |
| `validation.data_docs` | disabled |
| `on_failure` | `action: ignore` |
| `on_failure.mode` | `decision` |
| `expectations[].severity` | `critical` |

`id`, `engine`, `source`, `validation` and `report` have no default and must be present.
