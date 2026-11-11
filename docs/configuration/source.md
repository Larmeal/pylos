---
icon: material/database-import-outline
---

# Source

The `source` section says where the data is and how to read it. Pylos expands the path to a list of
files and validates each one on its own, so a failing file never hides the others.

```yaml
source:
  storage: local
  file_format: csv
  file_path: data/orders_*.csv
  on_empty: skip
  options:
    delimiter: ","
```

The fields are documented in [`LocalSourceConfig`][pylos.sources.local.LocalSourceConfig] and, for
the ones every source shares, [`FileBaseConfig`][pylos.sources.base.FileBaseConfig].

## `storage`

Where the files live. It is declared, never guessed from the path, so a Windows path like
`C:/data/f.csv` is not mistaken for a URL.

| Value | Status |
|---|---|
| `local` | Works |
| `gcs` | Planned. Not usable yet: with `move`, `copy` or `delete` in `on_failure` the config fails at load |

A local path must not contain `://`, and a GCS path must start with `gs://`. Either mismatch fails
at load.

```yaml title="Planned: Google Cloud Storage"
source:
  storage: gcs
  file_format: csv
  file_path: gs://my-bucket/orders/orders_*.csv
```

See [`LocalSourceConfig.storage`][pylos.sources.local.LocalSourceConfig.storage] and
[`GCSSourceConfig.storage`][pylos.sources.gcs.GCSSourceConfig.storage].

## `file_format`

How to read each file. The field is free text, but only `csv` is read today.

```yaml
source:
  storage: local
  file_format: csv
  file_path: data/orders.csv
```

See [`FileBaseConfig.file_format`][pylos.sources.base.FileBaseConfig.file_format].

## `file_path`

A path or a glob. Pick the shape that matches how your files arrive.

=== "One file"

    ```yaml
    source:
      storage: local
      file_format: csv
      file_path: data/orders.csv
    ```

=== "Every file in a folder"

    ```yaml
    source:
      storage: local
      file_format: csv
      file_path: data/*.csv
    ```

=== "A date pattern"

    ```yaml
    source:
      storage: local
      file_format: csv
      file_path: data/orders_2026-10-*.csv
    ```

If the pattern matches no file at all, the run stops with a `FileNotFoundError` and no report is
written. That is different from a file that matches and has no rows, which is what
[`on_empty`](#on_empty) controls.

See [`FileBaseConfig.file_path`][pylos.sources.base.FileBaseConfig.file_path].

## `on_empty`

What it means when a file has a header but no rows. An empty file passes every column
expectation, so Pylos cannot tell a quiet day from a broken export. You declare which one this
pipeline expects.

| Value | What happens to the empty file |
|---|---|
| `skip` (default) | The file is left alone and recorded as completed with no decision |
| `fail` | The file is recorded as `aborted` and the [`on_failure`](on-failure.md) action runs on it |

=== "Skip"

    ```yaml
    source:
      storage: local
      file_format: csv
      file_path: data/orders_*.csv
      on_empty: skip
    ```

=== "Fail"

    ```yaml
    source:
      storage: local
      file_format: csv
      file_path: data/orders_*.csv
      on_empty: fail
    ```

See [`FileBaseConfig.on_empty`][pylos.sources.base.FileBaseConfig.on_empty].

## `options`

Reader options, passed straight to `pd.read_csv`. Pylos does not interpret them, so anything pandas
accepts works, and pandas rejects what it does not.

```yaml
source:
  storage: local
  file_format: csv
  file_path: data/orders_*.csv
  options:
    delimiter: ";"
    encoding: latin-1
    parse_dates: [created_at]
```

`parse_dates` matters when a date rule such as `expect_column_values_to_be_between` should compare
dates, not strings.

See [`FileBaseConfig.options`][pylos.sources.base.FileBaseConfig.options].
