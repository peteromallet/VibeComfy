from __future__ import annotations

import hashlib
import json
from pathlib import Path

from vibecomfy.comfy_nodes.agent._canonical_contract_primitives import canonical_json


FIXTURE = Path(__file__).parent / "fixtures" / "browser_contract" / "b18_canonical_json.json"


def test_b18_canonical_fixture_matches_checked_in_browser_vectors() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in payload["cases"]:
        value = case["value"]
        ascii_json = canonical_json(value, ensure_ascii=True)
        utf8_json = canonical_json(value, ensure_ascii=False)
        assert ascii_json == case["canonical_ascii"]
        assert utf8_json == case["canonical_utf8"]
        assert hashlib.sha256(ascii_json.encode()).hexdigest() == case["ascii_sha256"]
        assert hashlib.sha256(utf8_json.encode()).hexdigest() == case["utf8_sha256"]


def test_b18_python_fixture_retains_proto_as_data() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in payload["cases"]:
        value = case["value"]
        assert any(
            isinstance(candidate, dict) and "__proto__" in candidate
            for candidate in (value, value.get("outer", {}), *value.get("array", []))
        )
