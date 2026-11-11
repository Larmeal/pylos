"""Errors about the data inside a source file, such as an empty file."""

from .base import DataError


class SourceEmptyError(DataError):
    """A source object has no data to validate.

    ``row_count``/``column_count`` carry whatever shape was known when it was
    raised. A file that parsed but has no rows (only a header) knows both; a file
    that could not be parsed at all (zero bytes) knows neither, so both default to
    ``None``. The runner reports the values carried here, because by the time the
    exception is caught, the engine object that held the dataframe is gone.
    """

    def __init__(
        self,
        message: str,
        row_count: int | None = None,
        column_count: int | None = None,
    ) -> None:
        """Create the error with whatever shape of the data was known.

        Args:
            message: What was empty, e.g. ``"data/x.csv is empty"``.
            row_count: Rows found, when the file could be parsed.
            column_count: Columns found, when the file could be parsed.
        """
        super().__init__(message)
        self.row_count = row_count
        self.column_count = column_count
