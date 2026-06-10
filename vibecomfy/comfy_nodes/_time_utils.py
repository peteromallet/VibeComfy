"""Shared timestamp helpers for comfy_nodes."""

import time


def _now() -> str:
    """Return current UTC time as an ISO-8601 formatted string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
