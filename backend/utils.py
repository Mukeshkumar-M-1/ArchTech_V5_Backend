import re


def string_underscore_change(s: str) -> str:
    """Convert a string with spaces (or mixed case) to snake_case."""
    return re.sub(r'\s+', '_', s)
