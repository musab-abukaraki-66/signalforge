"""Pipeline exceptions. Each one means the run must stop rather than emit misleading output."""


class PipelineError(RuntimeError):
    """Base class for pipeline failures."""


class MissingInputError(PipelineError):
    """A required source file is absent."""


class SchemaError(PipelineError):
    """A source file does not have the expected columns."""


class DataQualityError(PipelineError):
    """One or more error-severity quality checks failed."""
