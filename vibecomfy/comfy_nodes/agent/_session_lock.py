"""Lease-backed mutual exclusion for durable agent session state."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import Any


LOCK_FILE_NAME = ".session_state.lock"
DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
LOCK_LEASE_SECONDS = 30.0
LOCK_POLL_SECONDS = 0.025


def _process_alive(pid: int) -> bool:
    """Return ``True`` when a process with *pid* exists on this host."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    else:
        return True


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically via a sibling temporary file and rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


class SessionStateLock:
    """Mutual-exclusion lock for per-session state files.

    Structured owner metadata (pid, hostname, timestamp) is stored in the lock
    file so that dead-owner and stale-lease locks can be recovered safely.

    The small configuration hooks keep the historical ``session`` façade
    patchable while allowing the locking algorithm to live in this module.
    """

    def __init__(
        self,
        session_dir: Path,
        *,
        timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self.session_dir = session_dir
        self.lock_path = session_dir / self._lock_file_name()
        self.timeout_seconds = timeout_seconds
        self._fd: int | None = None
        self._lock_id: str | None = None
        self._heartbeat_stop: threading.Event | None = None
        self._heartbeat_thread: threading.Thread | None = None

    def _lock_file_name(self) -> str:
        return LOCK_FILE_NAME

    def _lease_seconds(self) -> float:
        return LOCK_LEASE_SECONDS

    def _poll_seconds(self) -> float:
        return LOCK_POLL_SECONDS

    def _process_is_alive(self, pid: int) -> bool:
        return _process_alive(pid)

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        _write_json_atomic(path, payload)

    def _read_lock_metadata(self) -> dict[str, Any] | None:
        """Read structured owner metadata from the lock file.

        Returns ``None`` for corrupt, unreadable, empty, or legacy-format
        (non-JSON) locks so the caller can quarantine them.
        """
        try:
            raw = self.lock_path.read_text(encoding="utf-8").strip()
            if not raw:
                return None
            return json.loads(raw)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None

    def _write_lock_metadata(self, fd: int) -> None:
        """Write structured owner metadata into the open file descriptor."""
        self._lock_id = uuid.uuid4().hex
        payload = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "timestamp": time.time(),
            "lock_id": self._lock_id,
        }
        os.write(fd, (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))
        os.fsync(fd)

    def _refresh_lock_lease(self) -> None:
        """Atomically renew this owner's cross-host lease."""
        current = self._read_lock_metadata()
        if not isinstance(current, dict) or current.get("lock_id") != self._lock_id:
            raise RuntimeError("session lock ownership changed during lease renewal")
        current["timestamp"] = time.time()
        self._write_json_atomic(self.lock_path, current)

    def _heartbeat_lock_lease(self) -> None:
        stop = self._heartbeat_stop
        if stop is None:
            return
        interval = max(0.25, self._lease_seconds() / 3.0)
        while not stop.wait(interval):
            try:
                self._refresh_lock_lease()
            except Exception:
                # Ownership verification on exit and competing acquisition
                # remain fail-closed. A failed renewal must not touch a
                # successor's lock file.
                return

    def _start_lock_heartbeat(self) -> None:
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_lock_lease,
            name=f"vibecomfy-session-lock-{self._lock_id}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _quarantine_lock(self, reason: str) -> bool:
        """Rename *lock_path* to a ``.corrupt-<ts>-...`` sibling.

        Returns ``True`` when the lock is gone after the call (whether we
        removed it or it disappeared on its own).
        """
        ts = int(time.time())
        dest = self.lock_path.with_name(f".corrupt-{ts}-{self.lock_path.name}-{reason}")
        counter = 0
        while dest.exists():
            counter += 1
            dest = self.lock_path.with_name(
                f".corrupt-{ts}-{counter}-{self.lock_path.name}-{reason}"
            )
        try:
            self.lock_path.rename(dest)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            try:
                self.lock_path.unlink()
                return True
            except FileNotFoundError:
                return True
            except OSError:
                return False

    def _try_recover(self) -> bool:
        """Attempt to recover a dead-owner or stale-lease lock.

        Recovery is conservative: live same-host owners and fresh cross-host
        leases are left untouched, while corrupt, dead-owner, and stale locks
        are quarantined before acquisition is retried.
        """
        try:
            stat_before = self.lock_path.stat()
        except FileNotFoundError:
            return True

        metadata = self._read_lock_metadata()
        if metadata is None:
            try:
                file_age = time.time() - self.lock_path.stat().st_mtime
                if file_age < 0.1:
                    return False
            except FileNotFoundError:
                return True
            self._quarantine_lock("corrupt_or_legacy")
            return True

        pid = metadata.get("pid")
        hostname = metadata.get("hostname")
        timestamp = metadata.get("timestamp")

        if not (
            isinstance(pid, int)
            and isinstance(hostname, str)
            and isinstance(timestamp, (int, float))
        ):
            self._quarantine_lock("malformed_metadata")
            return True

        if hostname == socket.gethostname():
            if self._process_is_alive(pid):
                return False
        elif time.time() - timestamp <= self._lease_seconds():
            return False

        try:
            stat_after = self.lock_path.stat()
        except FileNotFoundError:
            return True

        if (
            stat_after.st_ino != stat_before.st_ino
            or stat_after.st_mtime_ns != stat_before.st_mtime_ns
        ):
            return False

        recheck = self._read_lock_metadata()
        if recheck is not None:
            if not (
                recheck.get("pid") == pid
                and recheck.get("hostname") == hostname
                and recheck.get("timestamp") == timestamp
            ):
                return False

        self._quarantine_lock("dead_or_stale_owner")
        return True

    def __enter__(self) -> SessionStateLock:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                self._write_lock_metadata(self._fd)
                self._start_lock_heartbeat()
                return self
            except FileExistsError:
                if self._try_recover():
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out acquiring session lock {self.lock_path}")
                time.sleep(self._poll_seconds())

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._heartbeat_stop is not None:
            self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=max(1.0, self._lease_seconds() / 2.0))
        self._heartbeat_stop = None
        self._heartbeat_thread = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        if self._lock_id is not None:
            current = self._read_lock_metadata()
            if isinstance(current, dict) and current.get("lock_id") == self._lock_id:
                try:
                    self.lock_path.unlink()
                except FileNotFoundError:
                    pass


__all__ = [
    "DEFAULT_LOCK_TIMEOUT_SECONDS",
    "LOCK_FILE_NAME",
    "LOCK_LEASE_SECONDS",
    "LOCK_POLL_SECONDS",
    "SessionStateLock",
]
