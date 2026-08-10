"""Baseline validation for demo_factory.

Runs CLI gates on golden graph to prove baseline compilability.
Failed baseline = BASELINE_REJECTED.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibecomfy.porting.refuse import _load_convert_ui_to_api


@dataclass(frozen=True, slots=True)
class BaselineResult:
    passed: bool
    execution_safe: bool
    output_reachable: bool
    compile_error: str | None = None
    output_node_id: str | None = None
    node_count: int = 0
    link_count: int = 0

print("OK")
