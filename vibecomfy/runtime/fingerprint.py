from __future__ import annotations

from typing import Any


OVERRIDES_INCLUDE: set[str] = set()
OVERRIDES_EXCLUDE: set[str] = set()


def model_fingerprint(api_dict: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    triples: list[tuple[str, str, str]] = []
    for node in api_dict.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        include = class_type in OVERRIDES_INCLUDE or (
            "Loader" in class_type and class_type not in OVERRIDES_EXCLUDE
        )
        if not include:
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for slot, value in inputs.items():
            if isinstance(slot, str) and isinstance(value, str):
                triples.append((class_type, slot, value))
    return tuple(sorted(triples))
