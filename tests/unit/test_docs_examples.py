"""Every YAML example in the docs, and every file in ``example/configs``, must load.

A fenced ``yaml`` block under ``docs/`` is checked, so an example that drifts from the models
fails here instead of misleading a reader. Two kinds of block are handled:

* A full config (it has an ``engine`` key) is loaded as written.
* A fragment (``source:``, ``on_failure:`` and so on) replaces that section of a small valid
  config, and the result is loaded.

A block whose info string mentions ``Planned`` shows keys the code does not accept yet, so it is
skipped.
"""

import re
import textwrap
from pathlib import Path

import pytest
import yaml

from pylos.loader import from_yaml

DOCS = Path(__file__).resolve().parents[2] / "docs"

_FENCE = re.compile(r"^(?P<indent>[ \t]*)```(?:yaml|yml)(?P<info>[^\n]*)\n(?P<body>.*?)^(?P=indent)```", re.S | re.M)

_BASE_CONFIG = {
    "id": "docs_example",
    "engine": "pandas",
    "source": {"storage": "local", "file_format": "csv", "file_path": "data/*.csv"},
    "validation": {
        "contract": {
            "name": "docs_contract",
            "expectations": [{"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": "id"}}],
        }
    },
    "on_failure": {"action": "ignore"},
    "report": {"storage": "local", "format": "file", "path": "output/reports/"},
}


def _blocks() -> list[pytest.param]:
    found = []
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        for index, match in enumerate(_FENCE.finditer(text), start=1):
            if "planned" in match.group("info").lower():
                continue
            body = textwrap.dedent(match.group("body"))
            line = text.count("\n", 0, match.start()) + 1
            found.append(pytest.param(body, id=f"{page.relative_to(DOCS).as_posix()}:{line}#{index}"))
    return found


def _as_full_config(body: str) -> dict:
    data = yaml.safe_load(body)
    assert isinstance(data, dict), "a YAML example must be a mapping"
    if "engine" in data:
        return data
    return {**_BASE_CONFIG, **data}


EXAMPLE_CONFIGS = sorted((Path(__file__).resolve().parents[2] / "example" / "configs").glob("*.yml"))


@pytest.mark.parametrize("config", EXAMPLE_CONFIGS, ids=lambda path: path.name)
def test_example_config_loads(config: Path) -> None:
    from_yaml(config)


def test_docs_have_yaml_examples() -> None:
    assert _blocks(), "no YAML blocks were found under docs/, so the check below would pass without checking"


@pytest.mark.parametrize("body", _blocks())
def test_yaml_example_loads(body: str, tmp_path: Path) -> None:
    config = tmp_path / "pipeline.yml"
    config.write_text(yaml.safe_dump(_as_full_config(body)), encoding="utf-8")

    from_yaml(config)
