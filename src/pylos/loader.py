"""Loads a YAML config file into a validated engine."""

import logging
from pathlib import Path

from pydantic import TypeAdapter

from pylos.engines import Engine
from pylos.utils.yaml_loader import YamlLoader

logger = logging.getLogger(__name__)

_ADAPTER: TypeAdapter[Engine] = TypeAdapter(Engine)


def from_yaml(file_path: str | Path) -> Engine:
    """Load an engine configuration from a YAML file.

    Args:
        file_path (str | Path): Path to the YAML file to load.

    Returns:
        The validated engine. Its class is chosen by the file's ``engine`` field.
    """
    config = YamlLoader(file_path=file_path).load_yaml()
    engine = _ADAPTER.validate_python(config)
    logger.info("loaded config id=%s, engine=%s, from %s", engine.id, engine.engine, file_path)
    return engine
