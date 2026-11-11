---
icon: material/check-decagram-outline
---

# Validation

The `validation` section holds the contract, which is the list of rules every source file must
satisfy, and the optional Great Expectations Data Docs.

```yaml
validation:
  contract:
    name: orders
    expectations:
      - expectation_type: expect_column_values_to_not_be_null
        kwargs:
          column: id
  data_docs:
    enabled: false
```

The YAML key is `validation`. The fields are documented in [`GXConfig`][pylos.gx.models.GXConfig].

## `contract`

The rules for one dataset.

| Field | Required | What it does |
|---|---|---|
| `name` | yes | The contract's name. Appears in the report's `run_id` |
| `description` | no | Free text about the contract's purpose |
| `expectations` | yes | The list of rules |

`name` is the YAML spelling of [`data_asset_name`][pylos.gx.models.ContractConfig.data_asset_name].
Great Expectations also needs a datasource, a batch definition and a suite name. Pylos derives them
from `name` as `<name>_source`, `<name>_batch` and `<name>_suite`, and you can override them with
`datasource_name`, `batch_definition_name` and `expectation_suite_name`. Most contracts never need
to.

```yaml
validation:
  contract:
    name: orders
    description: Rules every daily orders file must satisfy.
    expectations:
      - expectation_type: expect_column_values_to_not_be_null
        kwargs:
          column: id
```

See [`ContractConfig`][pylos.gx.models.ContractConfig].

## `expectations`

Each entry is one rule.

| Field | Required | Default | What it does |
|---|---|---|---|
| `expectation_type` | yes | | A Great Expectations expectation name, unchanged |
| `kwargs` | no | empty | The expectation's own arguments |
| `severity` | no | `critical` | What a failure means. See [`severity`](#severity) |
| `name` | no | `<contract name>_<expectation_type>` | A readable name for the rule, shown in the report |
| `description` | no | none | Why the rule exists |
| `notes` | no | none | A free-form note, or a list of notes |
| `meta` | no | empty | Metadata carried through to the report |

The default name is the same for two rules of the same type, such as `not_null` on two columns. Give
such rules their own `name` to tell them apart in the report. Pylos also computes an `expectation_key` for each rule, a SHA-256 hash of its type and kwargs, and uses
it to match each result to its rule. It appears in `meta` of the report. Setting `expectation_key`
yourself fails at load, because the name is reserved.

Pylos does not check the expectation name or its kwargs when it loads the file. Great Expectations
does that when the rule runs.

These are the expectations the project's own template uses, each with its kwargs:

=== "Not null"

    ```yaml
    validation:
      contract:
        name: orders
        expectations:
          - expectation_type: expect_column_values_to_not_be_null
            kwargs:
              column: id
            name: id_not_null
    ```

=== "Unique"

    ```yaml
    validation:
      contract:
        name: orders
        expectations:
          - expectation_type: expect_column_values_to_be_unique
            kwargs:
              column: id
            name: id_unique
    ```

=== "Range"

    ```yaml
    validation:
      contract:
        name: orders
        expectations:
          - expectation_type: expect_column_values_to_be_between
            kwargs:
              column: amount
              min_value: 0
              max_value: 1000000
            severity: warning
    ```

=== "Allowed values"

    ```yaml
    validation:
      contract:
        name: orders
        expectations:
          - expectation_type: expect_column_values_to_be_in_set
            kwargs:
              column: status
              value_set: [new, paid, refunded]
    ```

=== "Column type"

    ```yaml
    validation:
      contract:
        name: orders
        expectations:
          - expectation_type: expect_column_values_to_be_of_type
            kwargs:
              column: id
              type_: int64
    ```

=== "Schema"

    ```yaml
    validation:
      contract:
        name: orders
        expectations:
          - expectation_type: expect_table_columns_to_match_ordered_list
            kwargs:
              column_list: [id, amount, status]
            description: A column rename or reorder invalidates every rule after it.
    ```

See [`ExpectationConfig`][pylos.gx.models.ExpectationConfig] and the
[Great Expectations gallery](https://greatexpectations.io/expectations/) for the full list of
names.

## `severity`

Severity decides what a failing rule means for the file.

| Severity | If the rule fails |
|---|---|
| `critical` (default) | The file's decision is `failed` and [`on_failure`](on-failure.md) runs |
| `warning` | The decision is `warned`. The file stays where it is |
| `info` | Recorded in the report. The decision stays `passed` and the file stays where it is |

```yaml
validation:
  contract:
    name: orders
    expectations:
      - expectation_type: expect_column_values_to_not_be_null
        kwargs:
          column: id
        severity: critical
      - expectation_type: expect_column_values_to_be_between
        kwargs:
          column: amount
          min_value: 0
        severity: warning
      - expectation_type: expect_column_values_to_not_be_null
        kwargs:
          column: note
        severity: info
```

See [`ExpectationConfig.severity`][pylos.gx.models.ExpectationConfig.severity] and
[Failure policy](../concepts/failure-policy.md).

## `data_docs`

An HTML view of the results, rendered by Great Expectations. It is off unless you enable it, and
then nothing is written. Pylos's own report is the record. Data Docs is for people who want to
browse.

```yaml
validation:
  contract:
    name: orders
    expectations:
      - expectation_type: expect_column_values_to_not_be_null
        kwargs:
          column: id
  data_docs:
    enabled: true
    store_path: output/data_docs/
```

`store_path` is required when `enabled` is true, and omitting it fails at load. A relative
`store_path` is turned into an absolute path at load, so it keeps pointing at the same place if the
working directory changes later.

See [`DataDocsConfig`][pylos.gx.models.DataDocsConfig].
