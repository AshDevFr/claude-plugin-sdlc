"""Exit codes and the error hierarchy.

The exit codes are a public contract: pipelines, hooks and the plugin branch on them, so a
value here never changes meaning.
"""

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_USAGE = 2
EXIT_PLATFORM = 3


class SpecsError(Exception):
    """An expected failure with a message fit for the user and a fixed exit code."""

    exit_code = EXIT_USAGE

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class CheckFailed(SpecsError):
    """A check ran and found a problem. A finding, not an error in the tool."""

    exit_code = EXIT_CHECK_FAILED


class UsageError(SpecsError):
    """The command line was wrong."""

    exit_code = EXIT_USAGE

    def __init__(self, message: str, usage: str | None = None):
        super().__init__(message)
        self.usage = usage


class ConfigError(SpecsError):
    """The repo's configuration is missing or invalid."""

    exit_code = EXIT_USAGE


class PlatformError(SpecsError):
    """The tracker or code host could not be reached or refused the request.

    Kept distinct from a failed check so a network problem never reads as a pass or a finding.
    """

    exit_code = EXIT_PLATFORM
