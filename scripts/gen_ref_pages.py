"""Generate the API reference pages and their navigation.

Runs inside the ``gen-files`` plugin on every build. It walks ``src/pylos`` and writes one
page per module under ``reference/``, each holding a single ``:::`` directive that
mkdocstrings expands. The navigation goes to ``reference/SUMMARY.md``, which
``literate-nav`` reads, so a new module appears in the docs without touching any config.

It also writes ``reference/index.md``: a map from each config key to its class, and a table of
every module with its one-line description and public names, both read from the source.
"""

from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent

import mkdocs_gen_files

PACKAGE = "pylos"

# Directories left out of the reference because they are internal plumbing, not API.
EXCLUDED_DIRS: tuple[str, ...] = ("utils",)

# Where each module sits on the index page. A module takes the group of its longest matching
# prefix, and a module that matches none lands in "Other", so a new module is never lost.
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Running a pipeline", ("loader", "runner", "planner", "policy")),
    ("Config sections", ("engines", "sources", "gx.models", "actions", "sinks")),
    ("Results and errors", ("results", "exceptions")),
    ("Internals", ("gx.validator", "gx.translation", "storages")),
)

# The config key a reader has in hand, and the class that holds it.
CONFIG_KEYS: tuple[tuple[str, str, str], ...] = (
    ("the whole file", "pylos.engines.Engine", "engines/index.md"),
    ("`source`", "pylos.sources.SourceConfig", "sources/index.md"),
    ("`validation`", "pylos.gx.models.GXConfig", "gx/models.md"),
    ("`on_failure`", "pylos.actions.OnFailureActionConfig", "actions.md"),
    ("`report`", "pylos.sinks.SinkConfig", "sinks/index.md"),
)

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src" / PACKAGE

MODULE_SYMBOL = '<code class="doc-symbol doc-symbol-nav doc-symbol-module"></code>'

nav = mkdocs_gen_files.Nav()
modules: list[tuple[str, str, str, list[str]]] = []


def describe(path: Path) -> tuple[str, list[str]]:
    """Read a module's one-line description and its public names, without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstring = ast.get_docstring(tree) or ""
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef) and not node.name.startswith("_"):
            names.append(node.name)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            # A type alias such as SourceConfig. Constants and __all__ are not API.
            if name[0].isupper() and not name.isupper() and not name.startswith("_"):
                names.append(name)
    return (docstring.splitlines()[0] if docstring else ""), names


def group_of(module: str) -> str:
    best_group, best_length = "Other", -1
    for group, prefixes in GROUPS:
        for prefix in prefixes:
            if (module == prefix or module.startswith(prefix + ".")) and len(prefix) > best_length:
                best_group, best_length = group, len(prefix)
    return best_group


for path in sorted(SRC.rglob("*.py")):
    relative = path.relative_to(SRC)

    if any(part in EXCLUDED_DIRS for part in relative.parts):
        continue

    # A module that has not been written yet would render as an empty page.
    if not path.read_text(encoding="utf-8").strip():
        continue

    parts = tuple(relative.with_suffix("").parts)
    doc_path = relative.with_suffix(".md")

    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
    elif parts[-1].startswith("_"):
        continue

    # The top-level ``pylos/__init__.py`` has no name to show beneath the package.
    if not parts:
        continue

    nav[tuple(f"{MODULE_SYMBOL} {part}" for part in parts)] = doc_path.as_posix()

    full_doc_path = Path("reference", doc_path)
    identifier = ".".join((PACKAGE, *parts))
    summary, names = describe(path)
    modules.append((".".join(parts), doc_path.as_posix(), summary, names))

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        fd.write(
            dedent(
                f"""\
                ---
                title: {parts[-1]}
                icon: material/code-tags
                ---

                ::: {identifier}
                    options:
                      heading_level: 2
                """
            )
        )

    # edit_uri points into docs/, so the source file is reached from one level up.
    mkdocs_gen_files.set_edit_path(full_doc_path, "../" + path.relative_to(ROOT).as_posix())

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())

index = [
    "---",
    "icon: material/api",
    "---",
    "",
    "# API Reference",
    "",
    "One page for every module of the `pylos` package, generated from the source. Names that start with",
    "an underscore and internal helper modules are left out. Until 1.0, anything documented here can",
    "change between minor versions.",
    "",
    "## From a config key to its class",
    "",
    "| In the YAML | Class | Page |",
    "|---|---|---|",
]
for label, identifier, page in CONFIG_KEYS:
    index.append(
        f"| {label} | [`{identifier.rsplit('.', 1)[1]}`][{identifier}] | [{page.removesuffix('.md')}]({page}) |"
    )

index += [
    "",
    "To run a config from Python, use [`from_yaml`][pylos.loader.from_yaml] and [`Runner`][pylos.runner.Runner].",
    "",
]

grouped: dict[str, list[tuple[str, str, str, list[str]]]] = {}
for module in modules:
    grouped.setdefault(group_of(module[0]), []).append(module)

for group in [name for name, _ in GROUPS] + ["Other"]:
    rows = grouped.get(group)
    if not rows:
        continue
    index += [f"## {group}", "", "| Module | What it is | Public names |", "|---|---|---|"]
    for module, page, summary, names in rows:
        shown = ", ".join(f"`{name}`" for name in names[:6]) + (", ..." if len(names) > 6 else "")
        index.append(f"| [`{module}`]({page}) | {summary.replace('|', '/')} | {shown} |")
    index.append("")

with mkdocs_gen_files.open("reference/index.md", "w") as fd:
    fd.write("\n".join(index))

mkdocs_gen_files.set_edit_path("reference/index.md", "../scripts/gen_ref_pages.py")
