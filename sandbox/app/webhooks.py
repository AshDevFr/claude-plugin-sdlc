"""A tiny webhook sender: the product code of the sdlc sandbox."""


def should_retry(status: int) -> bool:
    """Server errors are worth retrying; client errors are not."""
    return 500 <= status < 600


def backoff_seconds(attempt: int) -> int:
    """Delay before retry number `attempt` (1-based): 1, 4, 16, ..."""
    return 4 ** (attempt - 1)
