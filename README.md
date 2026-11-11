<p align="center">
  <img src="images\github-logo.png" width="300" height="300" />
</p>

<h1 align="center">
  <b style="font-size: 1.5em; letter-spacing: 0.15em;">✦ PYLOS ✦</b>
</h1>

<p align="center">
  <i>A framework for encapsulating Great Expectations within data pipelines</i>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python Version" /></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff" /></a>
  <a href="https://pre-commit.com/"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit" alt="pre-commit" /></a>
  <a href="https://docs.greatexpectations.io/"><img src="https://img.shields.io/badge/great--expectations-1.x-orange.svg" alt="Great Expectations" /></a>
  <a href="https://pandas.pydata.org/"><img src="https://img.shields.io/badge/pandas-2.x-150458.svg?logo=pandas" alt="Pandas" /></a>
  <a href="https://docs.pydantic.dev/"><img src="https://img.shields.io/badge/pydantic-v2-E92063.svg?logo=pydantic" alt="Pydantic" /></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" /></a>
</p>

---

## What it is

Pylos (pronounced "PY-los") is a data validation and profiling framework for data pipelines. It handles the operational
work around [Great Expectations](https://greatexpectations.io/): it manages configuration,
dispatches across engines, decides what happens when validation fails, and reports results to
pluggable sinks.

Pylos runs as a layer inside someone else's pipeline (Airflow, Dagster, or a plain script). It is
not a pipeline, a scheduler, or an ETL tool. It is built for automated systems that run daily and
report on data processing, and is not meant for interactive data exploration.

## What it adds over Great Expectations

| | |
|---|---|
| Failure lifecycle | GX reports that a batch failed, but it will not move the offending file to a dead-letter location or record what happened. Pylos does both. |
| Multi-engine dispatch | The same declarative YAML runs on pandas, Spark or SQL. |
| Profiling | GX 1.x removed much of the profiling support that 0.x had. Pylos brings it back (planned for v0.6). |

## How it works

```
                        ┌──── profile ─────┐
Source ──[ Engine ]────►┤                  ├────► Sink
                        └──── validate ────┘
                                 │
                (validate only)  │
                                 ▼
                          Policy ──► Action on the Source
```

Profiling and validation read the source the same way, run on the same engine, and write to the
same sink. Profiling never fails, so only validation can trigger an action on the source file.

## Features

- One YAML file per pipeline, parsed and validated by Pydantic. A typo fails when the file loads,
  not ten minutes into a run.
- Each expectation has a severity: `critical`, `warning` or `info`. The severity decides whether
  the pipeline acts on a failure.
- On failure, Pylos can `ignore`, `move`, `copy` or `delete` the source file. The storage system
  that owns the data does the work: GCS moves its own objects, and the OS moves local files.
- A report is always written, separately from the file action, so one pipeline can write to
  BigQuery *and* move the file. The report is written *before* the file is touched.
- One file is one batch, so every result names the file it came from.
- Two error classes decide what is retryable. `ConfigurationError` aborts the run, and `DataError`
  dead-letters one source file. Any other exception is fatal: it stops the run before any file is
  touched, so a network blip cannot quarantine healthy files.
- A bad file is skipped and recorded, and the remaining files still run.
- The library returns the reasoning behind every result. The CLI is a thin wrapper around it.
- Editor autocomplete comes from a JSON Schema generated from the same Pydantic models Pylos
  validates with, so the schema always matches what the code accepts.

```yaml
id: customer_daily
engine: pandas

source:
  storage: local                # local | gcs
  file_format: csv
  file_path: data/*.csv
  on_empty: fail                # fail | skip

validation:
  contract:
    name: customer
    expectations:
      - expectation_type: expect_column_values_to_not_be_null
        kwargs: {column: id}
        severity: critical      # critical | warning | info

on_failure:
  action: move                  # ignore | move | copy | delete
  dead_letter: output/dead-letters/
```

## Not in scope

- Scheduling
- Writing validated data out (ETL)
- Data catalog or lineage
- Alerting, which the orchestrator's `on_failure_callback` handles better
- Exploratory data analysis
- A drift platform. Pylos ships a time-series table, and drift is computed with SQL views over it.
- An in-house expectation vocabulary. GX expectation names pass through unchanged.

## Roadmap

| | Ships |
|---|---|
| v0.1 | pandas · local · CSV, end to end · `action: ignore\|move\|copy\|delete` · JSON sink · GX Data Docs · library API · error taxonomy · retry-safe reports |
| v0.2 | GCS · BigQuery sink · `merge` · checkpoint / resume · custom expectations |
| v0.3 | Jinja · contract reuse · CLI |
| v0.4 | Spark |
| v0.5 | SQL |
| v0.6 | profiling + drift SQL views |

## Status

Pylos is pre-v0.1 and under active construction. The local path works end to end with pandas and
CSV files: configuration, the GX adapter, local storage, the planner, the policy, the file actions
(`ignore`, `move`, `copy`, `delete`) and the local JSON report sink. `run()` writes the report to
the sink and returns nothing. GCS storage, the GCS sink and the BigQuery sink are placeholders
until v0.2.

## Development

```bash
uv sync                  # install with dev groups
uv sync --extra gcp      # add the GCP extra
uv run ruff check src/   # lint
uv run pytest            # test
prek install             # pre-commit hooks
```
