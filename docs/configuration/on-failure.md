---
icon: material/alert-octagon-outline
---

# On failure

`on_failure` says what happens to a source file whose data was judged bad. It sits beside
`validation`, not inside it, because it can also apply to a file Pylos could not read at all.

```yaml
on_failure:
  action: move
  dead_letter: output/dead-letters/
```

If you leave the section out, the action is `ignore`: the file stays put, and the report still
records what failed. A report is always written, so this section only controls what happens to the
file.

## `action`

=== "Ignore"

    ```yaml
    on_failure:
      action: ignore
    ```

    The file stays where it is. No other field is needed.

=== "Move"

    ```yaml
    on_failure:
      action: move
      dead_letter: output/dead-letters/
    ```

    The file goes into `dead_letter` and the original is removed.

=== "Copy"

    ```yaml
    on_failure:
      action: copy
      dead_letter: output/dead-letters/
    ```

    A copy goes into `dead_letter` and the original stays.

=== "Delete"

    ```yaml
    on_failure:
      action: delete
    ```

    The file is removed. Nothing is kept, so use it only for data you can fetch again.

See [`IgnoreFailureAction`][pylos.actions.IgnoreFailureAction],
[`MoveFailureAction`][pylos.actions.MoveFailureAction],
[`CopyFailureAction`][pylos.actions.CopyFailureAction] and
[`DeleteFailureAction`][pylos.actions.DeleteFailureAction].

## `dead_letter`

The directory that receives files for `move` and `copy`. It is required for those two and not
accepted for the others. Trailing slashes are stripped, and an empty value or `/` fails at load.

On local storage the path can be relative or absolute. See
[`RelocateFailureAction.dead_letter`][pylos.actions.RelocateFailureAction.dead_letter].

## `mode`

`mode` decides which outcomes make the action fire.

| Mode | A file judged bad | A file Pylos could not read |
|---|---|---|
| `decision` (default) | Action runs | Left where it is, recorded as `aborted` with the error |
| `any_failure` | Action runs | Action runs |

`decision` is the safe choice. A read error can be temporary, such as a file still being written,
and `any_failure` would move a healthy file because of it. Choose `any_failure` when an unreadable
file really should be quarantined.

```yaml
on_failure:
  action: move
  dead_letter: output/dead-letters/
  mode: any_failure
```

In both modes a file that passed, or only warned, is left alone. See
[`BaseFailureAction.mode`][pylos.actions.BaseFailureAction.mode].

## The storage backend

A `move`, `copy` or `delete` needs a storage backend to touch the file. Pylos fills it in from the
`source` section, so the action works on the same storage the file was read from. You do not set
it. See [`RelocateFailureAction.backend`][pylos.actions.RelocateFailureAction.backend].
