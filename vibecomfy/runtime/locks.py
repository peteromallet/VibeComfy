"""Small cross-process locks for named managed-runtime resources."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import fcntl


@contextmanager
def resource_lock(directory: str | Path) -> Iterator[None]:
    """Serialize lifecycle mutations without locking the long-lived daemon."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    lock_path = path / ".lifecycle.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


__all__ = ["resource_lock"]
