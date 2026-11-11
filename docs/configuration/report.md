---
icon: material/file-chart-outline
---

# Report

The `report` section says where the results are written. A report is written for every run, so
this section only picks the destination.

```yaml
report:
  storage: local
  format: file
  path: output/reports/
```

The section is a single entry today. See [`BaseEngine.report`][pylos.engines.base.BaseEngine.report].

## `storage`

Where the report goes.

| Value | Status |
|---|---|
| `local` | Works |
| `gcs` | Planned. A config that names it fails at load |
| `bigquery` | Planned. A config that names it fails at load |

See [`LocalSink.storage`][pylos.sinks.local.LocalSink.storage].

## `format`

How the report is laid out. `file` writes one JSON document. `table`, for rows in a table, belongs
to the planned BigQuery sink.

See [`BaseFileFormat.format`][pylos.sinks.base.BaseFileFormat.format] and
[`BaseTableFormat.format`][pylos.sinks.base.BaseTableFormat.format].

## `path`

Where a `file` report goes. If `path` is a directory, which includes one that does not exist yet,
the report is written to `<path>/<run_id>.json` and missing folders are created. If `path` is an
existing file, that file is overwritten.

```yaml
report:
  storage: local
  format: file
  path: output/reports/
```

The `run_id` is the contract name and the pipeline `id` joined with a hyphen. A pipeline with
contract `orders` and id `orders_daily` writes `output/reports/orders-orders_daily.json`. Running
it again replaces that file, so the folder holds the latest run of each pipeline and not a
history.

See [`BaseFileFormat.path`][pylos.sinks.base.BaseFileFormat.path] and
[`LocalSink`][pylos.sinks.local.LocalSink]. [Getting started](../getting-started/index.md#what-you-get)
shows a real report, and [Reporting](../concepts/reporting.md) describes its fields.
