from pathlib import Path

from pydantic import BaseModel, field_validator
from yaml import safe_load


class YamlLoader(BaseModel):
    """Loads one YAML config file, after checking that it exists and has a YAML extension."""

    file_path: Path | str

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: Path | str) -> Path:
        """Check that the path exists and is a file.

        Args:
            value (Path | str): The file path to validate.

        Returns:
            Path: The validated file path.

        Raises:
            FileNotFoundError: If the file path does not exist or is not a file.
        """
        path_obj = Path(value) if isinstance(value, str) else value
        if not path_obj.is_file():
            raise FileNotFoundError(f"The path '{path_obj}' does not exist or is not a file.")
        return path_obj

    @field_validator("file_path")
    @classmethod
    def validate_file_extension(cls, value: Path) -> Path:
        """Check that the file has a ``.yaml`` or ``.yml`` extension.

        Args:
            value (Path): The file path to validate.

        Returns:
            Path: The validated file path.

        Raises:
            ValueError: If the file extension is not .yaml or .yml.
        """
        if value.suffix not in {".yaml", ".yml"}:
            raise ValueError(f"The provided file path '{value}' does not have a valid YAML extension.")
        return value

    def load_yaml(self) -> dict:
        """Read the YAML file and parse it into a dict.

        Returns:
            The parsed configuration.
        """
        with open(self.file_path, encoding="utf-8") as file:
            return safe_load(file)
