from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _lenient_json_loads(text: str) -> dict[str, Any]:
    """Parse workflow JSON, tolerating common hand-edit mistakes.

    Fixes applied on JSONDecodeError (in order):
    - unquoted `id` values like \"id\": 105_rope  → \"id\": \"105_rope\"
    - bare node ids in arrays like [4, 105, 0, 105_rope, 0, \"MODEL\"]
    - trailing commas before } or ] (e.g. {\"a\": 1,})
    Re-raises the original error if fixes do not help.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as orig:
        fixed = text
        def _quote_id(m):
            token = m.group(1)
            if token.isdigit():
                return m.group(0)
            return f'"id": "{token}"{m.group(2)}'
        fixed = re.sub(r'"id"\s*:\s*([A-Za-z0-9_]+)\s*([,}])', _quote_id, fixed)
        # Quote bare ids like 105_rope that appear as array values (e.g. links).
        fixed = re.sub(r'(?<![\w"])([0-9]+_[A-Za-z0-9_]+)(?![\w"])', r'"\1"', fixed)
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            raise orig


def load_workflow_json(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    data = _lenient_json_loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Workflow {path} did not decode to a JSON object")
    return data


def load_workflow_json_text(text: str) -> dict[str, Any]:
    """Parse workflow JSON text leniently (hand-edit tolerant)."""
    data = _lenient_json_loads(text)
    if not isinstance(data, dict):
        raise ValueError("Workflow text did not decode to a JSON object")
    return data


# Back-compat alias documented by the agent skill.


# Back-compat alias documented by the agent skill. Still lazy-exported from
# vibecomfy/__init__ and asserted by test_packaging/test_api_surface; removing
# it requires migrating every external caller first.
load_template = load_workflow_json
