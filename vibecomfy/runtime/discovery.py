from __future__ import annotations

import os
from pathlib import Path


def find_active_session(id: str = "default") -> str | None:
    session_dir = Path("out/sessions") / id
    pid_path = session_dir / "pid"
    url_path = session_dir / "url"
    if not pid_path.exists() or not url_path.exists():
        _cleanup_session_files(session_dir)
        return None
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        url = url_path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        _cleanup_session_files(session_dir)
        return None
    if not url:
        _cleanup_session_files(session_dir)
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        _cleanup_session_files(session_dir)
        return None
    except PermissionError:
        return url
    except OSError:
        _cleanup_session_files(session_dir)
        return None
    return url


def _cleanup_session_files(session_dir: Path) -> None:
    for name in ("pid", "url", "config.json"):
        try:
            (session_dir / name).unlink()
        except FileNotFoundError:
            pass
