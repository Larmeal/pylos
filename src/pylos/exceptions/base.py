"""The base error classes: ``PylosError``, ``ConfigurationError`` and ``DataError``."""


class PylosError(Exception):
    """Base class for every error Pylos raises.

    Callers catch this to handle anything Pylos is responsible for without also
    catching unrelated failures from pandas, Great Expectations or a cloud SDK.
    """


class ConfigurationError(PylosError):
    """The configuration is wrong, so the run cannot start.

    A malformed YAML file, a field that fails validation, an expectation that
    does not exist, or an action that the source kind does not support. Raised by
    the loader and by parse-time validators, before any data is read.

    Retrying does not help; the file has to change. The run aborts and no source
    object is validated.
    """


class DataError(PylosError):
    """One source object's data is bad, and only that source object is affected.

    A corrupt CSV, a file that cannot be parsed, a schema that does not match.
    Raised by the reader once it recognises a failure as belonging to the data
    rather than to the environment.

    The source object is recorded and dead-lettered according to ``on_failure``, and
    the run continues with the remaining source objects. A recorded partial run is
    better than an aborted one that leaves the day missing from the report.
    """
