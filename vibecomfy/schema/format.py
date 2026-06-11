from __future__ import annotations

from typing import Any


def format_issue(issue: Any) -> str:
    d = issue.detail or {}
    loc = " ".join(f"{k}={d[k]}" for k in ("node_id", "class_type", "input") if k in d)
    return f"[{issue.code}] {loc}: {issue.message}".strip()
