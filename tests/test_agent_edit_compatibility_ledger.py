"""Guards for the agent-edit legacy alias compatibility ledger."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = (
    Path("vibecomfy/comfy_nodes/agent"),
    Path("vibecomfy/comfy_nodes/web"),
    Path("tests/browser"),
    Path("tests/fixtures/payload_contracts"),
    Path("tests/fixtures/e2e_sessions"),
    Path("tests/characterization"),
)

TEXT_SUFFIXES = {".js", ".mjs", ".py", ".json", ".md", ".txt"}

ALIAS_PATTERNS = {
    "executor_pending": re.compile(r"\bexecutor_pending\b"),
    "canvasApplyAllowed": re.compile(r"\bcanvasApplyAllowed\b"),
    "flattened_apply_allowed": re.compile(r"\b(?:apply_allowed|canvas_apply_allowed)\b"),
    "field_changes": re.compile(r"\bfield_changes\b"),
}

ALLOWED_ALIAS_FILES = {
    "executor_pending": {
        "tests/browser/active_row_rendering.test.mjs",
        "tests/browser/agent_edit_lifecycle.test.mjs",
        "tests/browser/agent_edit_lifecycle_transcript.test.mjs",
        "tests/browser/agent_edit_response_contract.test.mjs",
        "tests/browser/panel_thread_rating.test.mjs",
        "tests/browser/payload_contracts.test.mjs",
        "tests/browser/roundtrip_smoke.test.mjs",
        "vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js",
        "vibecomfy/comfy_nodes/web/panel_thread.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
    "canvasApplyAllowed": {
        "tests/browser/agent_edit_lifecycle.test.mjs",
        "tests/browser/agent_edit_lifecycle_transcript.test.mjs",
        "tests/browser/agent_edit_response_contract.test.mjs",
        "tests/browser/agent_edit_response_malformed.test.mjs",
        "tests/browser/payload_contracts.test.mjs",
        "tests/browser/roundtrip_smoke.test.mjs",
        "vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/panel_composer.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
    "flattened_apply_allowed": {
        "tests/browser/agent_edit_lifecycle.test.mjs",
        "tests/browser/agent_edit_lifecycle_transcript.test.mjs",
        "tests/browser/agent_edit_response_contract.test.mjs",
        "tests/browser/agent_edit_response_malformed.test.mjs",
        "tests/browser/payload_contracts.test.mjs",
        "tests/browser/roundtrip_smoke.test.mjs",
        "tests/fixtures/payload_contracts/agent_edit_accept_response.json",
        "tests/fixtures/payload_contracts/agent_edit_rebaseline_response.json",
        "tests/fixtures/payload_contracts/chat_rehydrate_response.json",
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit.py",
        "vibecomfy/comfy_nodes/agent/gates.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
    "field_changes": {
        "tests/browser/agent_edit_lifecycle.test.mjs",
        "tests/browser/agent_edit_response_contract.test.mjs",
        "tests/browser/panel_thread_rating.test.mjs",
        "tests/browser/payload_contracts.test.mjs",
        "tests/browser/roundtrip_smoke.test.mjs",
        "vibecomfy/comfy_nodes/agent/edit.py",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/diagnostics_reporting.js",
        "vibecomfy/comfy_nodes/web/panel_thread.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
}


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        for path in (ROOT / scan_root).rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def test_agent_edit_legacy_aliases_stay_inside_compatibility_ledger_allowlist() -> None:
    violations: list[str] = []

    for path in _iter_text_files():
        rel_path = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for alias_name, pattern in ALIAS_PATTERNS.items():
            if rel_path in ALLOWED_ALIAS_FILES[alias_name]:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    violations.append(f"{alias_name}: {rel_path}:{line_number}: {line.strip()}")

    assert not violations, (
        "Legacy agent-edit aliases must stay within tests/fixtures/agent_edit/"
        "compatibility_ledger.md allowlists:\n" + "\n".join(violations)
    )
