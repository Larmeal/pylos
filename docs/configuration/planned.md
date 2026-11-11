---
icon: material/calendar-clock-outline
---

# Planned keys

These keys are part of the design and are not in the code yet. Using one today fails at load, as
each of the examples below does. They are shown for orientation and are not loaded by the tests.

The release numbers come from the roadmap and can move.

## Several reports and BigQuery

Planned for the release that adds BigQuery. `report` becomes a list, so one run can write to
several places, and a table sink takes a write mode.

```yaml title="Planned"
report:
  - type: file
    path: output/reports/
  - type: bigquery
    dataset: data_quality
    write_mode: merge # append | overwrite | merge
    merge_key: [run_id, source_object, expectation_key]
```

## Runtime behavior

Planned with GCS. A `runtime` section controls how an execution behaves, apart from what it checks.

```yaml title="Planned"
runtime:
  checkpoint: 1 # write to every sink after each object; -1 writes once at the end
  is_continue: false # skip objects this run already recorded; needs a run key
```

`run_key` is not a config key. The caller passes it for each execution.

## A shared contract file

Planned with Jinja templating. A contract can point at a file that several pipelines share.

```yaml title="Planned"
validation:
  contract: contracts/customer.yml
```

Jinja also brings `{{ env_var('...') }}`, so secrets stay out of the file.

## Profiling

Planned for a later release. Profiling records descriptive statistics over time.

```yaml title="Planned"
profile:
  enabled: true
  sample:
    rows: 100000
```

## More engines and storages

Spark and SQL engines, and more storages such as S3 and BigQuery tables, are planned. A table
source has no `file_path` or `file_format`, and no file action applies to it.

```yaml title="Planned"
engine: spark
source:
  storage: bigquery
  project: my-project
  dataset: raw
  table: customers
```
