"""Guards for the agent-edit legacy alias compatibility ledger."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = (
    Path("vibecomfy/comfy_nodes/agent"),
    Path("vibecomfy/comfy_nodes/web"),
    Path("tests/fixtures/payload_contracts"),
    Path("tests/fixtures/e2e_sessions"),
    Path("tests/characterization"),
)

TEXT_SUFFIXES = {".js", ".mjs", ".py", ".json", ".md", ".txt"}

LEDGER_PATH = ROOT / "tests/fixtures/agent_edit/compatibility_ledger.md"
ARCHITECTURE_LEDGER_PATH = ROOT / "docs/architecture/compatibility-ledger.md"

ALIAS_PATTERNS = {
    "queue_allowed": re.compile(r"\bqueue_allowed\b"),
    "candidate_graph": re.compile(r"\bcandidate_graph\b"),
}

# 2026-06-24 M2 alias-token inventory across SCAN_ROOTS before tightening:
# queue_allowed: 16 files / ~169 hits; candidate_graph: 11 files / ~56 hits;
# candidate_graph_hash: 9 files / ~93 hits. Only queue_allowed and
# candidate_graph are compatibility-specific and bounded enough for explicit
# scanner allowlists. candidate_graph_hash is canonical; apply_eligible and
# apply_eligibility are broader apply-eligibility behavior surfaces, so keep
# those covered by adapter/contract behavior tests instead of broad regex
# scanner allowlists.
ALLOWED_ALIAS_FILES = {
    "queue_allowed": {
        "tests/fixtures/payload_contracts/agent_edit_accept_response.json",
        "tests/fixtures/payload_contracts/agent_edit_rebaseline_response.json",
        "tests/fixtures/payload_contracts/chat_rehydrate_response.json",
        "vibecomfy/comfy_nodes/agent/_frag_chat.py",
        "vibecomfy/comfy_nodes/agent/_frag_humanize.py",
        "vibecomfy/comfy_nodes/agent/_frag_response_contract.py",
        "vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py",
        "vibecomfy/comfy_nodes/agent/audit.py",
        "vibecomfy/comfy_nodes/agent/authority_receipts.py",
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit.py",
        "vibecomfy/comfy_nodes/agent/edit_chat.py",
        "vibecomfy/comfy_nodes/agent/edit_humanize.py",
        "vibecomfy/comfy_nodes/agent/edit_response_contract.py",
        "vibecomfy/comfy_nodes/agent/executor_response.py",
        "vibecomfy/comfy_nodes/agent/executor_durable.py",
        "vibecomfy/comfy_nodes/agent/gates.py",
        "vibecomfy/comfy_nodes/agent/reorganise.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/panel_overlay.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
    "candidate_graph": {
        "vibecomfy/comfy_nodes/agent/_frag_batch_loop.py",
        "vibecomfy/comfy_nodes/agent/_frag_research.py",
        "vibecomfy/comfy_nodes/agent/_frag_response_contract.py",
        "vibecomfy/comfy_nodes/agent/_frag_revision_stages.py",
        "vibecomfy/comfy_nodes/agent/_turn_state_machine.py",
        "vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py",
        "vibecomfy/comfy_nodes/agent/candidate_transaction.py",
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit.py",
        "vibecomfy/comfy_nodes/agent/edit_batch_repl.py",
        "vibecomfy/comfy_nodes/agent/edit_research.py",
        "vibecomfy/comfy_nodes/agent/edit_response_contract.py",
        "vibecomfy/comfy_nodes/agent/edit_revision_stages.py",
        "vibecomfy/comfy_nodes/agent/execution_plan_runtime.py",
        "vibecomfy/comfy_nodes/agent/executor_response.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js",
        "vibecomfy/comfy_nodes/web/agent_status_poller.js",
        "vibecomfy/comfy_nodes/web/agentic_replay.js",
        "vibecomfy/comfy_nodes/web/preview_picker.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
}

PROHIBITED_ALLOWLIST_FRAGMENTS = (
    "panel_thread.js",
    "agent_edit_lifecycle_transcript",
    "transcript",
    "detail_selector",
    "bubble_detail",
    "model_provider",
    "provider_model",
)

FIXTURE_TOKEN_CLASSIFICATION_ANCHORS = {
    "_CLARIFY_FORBIDDEN_KEYS": (
        "### Clarify/noop forbidden-key guards",
        "retained legacy alias",
        "_CLARIFY_FORBIDDEN_KEYS`; it aliases `_NON_APPLYABLE_FORBIDDEN_KEYS`",
    ),
    "_CLARIFY_FORBIDDEN_RESPONSE_KEYS": (
        "### Edit-layer clarify-response sanitizer",
        "owned by response assembly",
        "keep it separate from the route-layer guard",
    ),
    "_strip_clarify_forbidden_response_fields": (
        "### Edit-layer clarify-response sanitizer",
        "_sanitize_pure_clarify_response",
        "may have added candidate/apply aliases",
    ),
    "apply_eligible": (
        "### `apply_eligible`",
        "Canonical executor/apply authorization bit",
        "N/A for the canonical authorization field",
    ),
    "candidate_graph_hash": (
        "### Graph hash fields",
        "active/session/diagnostic fields, not removable legacy aliases",
        "not removable legacy aliases",
    ),
    "client_graph_hash": (
        "### Graph hash fields",
        "active/session/diagnostic fields, not removable legacy aliases",
        "not removable legacy aliases",
    ),
    "graph": (
        "### `candidate_graph` / `graph` legacy candidate aliases",
        "top-level `candidate_graph` or `graph` alias",
        "status/debug, or compatibility display inputs",
    ),
    "action_client_graph_hash": (
        "### `submitted_client_graph_hash` / `action_client_graph_hash`",
        "Session migration/action-validation fields",
        "records `action_client_graph_hash`",
    ),
    "submitted_client_graph_hash": (
        "### `submitted_client_graph_hash` / `action_client_graph_hash`",
        "Session migration/action-validation fields",
        "Session allocation stores `submitted_client_graph_hash`",
    ),
}


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        for path in (ROOT / scan_root).rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def _ledger_scannable_backend_aliases() -> set[str]:
    text = LEDGER_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"Deliberately scannable bounded backend aliases:\s*(?P<aliases>.+)",
        text,
    )
    assert match, "Compatibility ledger must list deliberately scannable backend aliases."
    return set(re.findall(r"`([^`]+)`", match.group("aliases")))


def _read_ledgers() -> dict[str, str]:
    return {
        "fixture": LEDGER_PATH.read_text(encoding="utf-8"),
        "architecture": ARCHITECTURE_LEDGER_PATH.read_text(encoding="utf-8"),
    }


def _normalized_ledgers() -> dict[str, str]:
    return {name: re.sub(r"\s+", " ", text) for name, text in _read_ledgers().items()}


def _fixture_retained_alias_tokens_by_row() -> dict[str, str]:
    text = LEDGER_PATH.read_text(encoding="utf-8")
    header = "| Alias or shape | Owner | Allowed files | Fixture coverage | Deletion trigger |"
    in_table = False
    tokens_by_row: dict[str, str] = {}

    for line in text.splitlines():
        if line == header:
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= {"-", ":"}:
            continue
        for token in re.findall(r"`([^`]+)`", cells[0]):
            assert token not in tokens_by_row, f"duplicate fixture ledger table token: {token}"
            tokens_by_row[token] = cells[0]

    assert tokens_by_row, "Fixture compatibility ledger retained-alias table has no tokens."
    return tokens_by_row


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


def test_ledger_listed_scannable_backend_aliases_have_scanner_patterns() -> None:
    scannable_aliases = _ledger_scannable_backend_aliases()

    assert scannable_aliases == {
        "queue_allowed",
        "candidate_graph",
    }
    assert not (scannable_aliases - set(ALIAS_PATTERNS))
    assert not (scannable_aliases - set(ALLOWED_ALIAS_FILES))
    assert set(ALIAS_PATTERNS) == scannable_aliases
    assert set(ALLOWED_ALIAS_FILES) == scannable_aliases


def test_ledger_scanner_allowlists_do_not_cover_frontend_render_or_routing_paths() -> None:
    offending_paths = sorted(
        f"{alias_name}: {path}"
        for alias_name, paths in ALLOWED_ALIAS_FILES.items()
        for path in paths
        if any(fragment in path for fragment in PROHIBITED_ALLOWLIST_FRAGMENTS)
    )

    assert not offending_paths, (
        "Compatibility scanner allowlists must stay limited to true legacy "
        "aliases/shims, without broad frontend render, transcript/detail, or "
        "model/provider routing exceptions:\n" + "\n".join(offending_paths)
    )


def test_fixture_retained_alias_table_tokens_are_covered_by_architecture_ledger() -> None:
    architecture_text = ARCHITECTURE_LEDGER_PATH.read_text(encoding="utf-8")
    tokens_by_row = _fixture_retained_alias_tokens_by_row()
    uncovered_tokens: list[str] = []

    for token, row_label in tokens_by_row.items():
        if f"`{token}`" in architecture_text:
            continue
        anchors = FIXTURE_TOKEN_CLASSIFICATION_ANCHORS.get(token)
        if anchors and all(anchor in architecture_text for anchor in anchors):
            continue
        uncovered_tokens.append(f"{token} from fixture row {row_label!r}")

    assert not uncovered_tokens, (
        "Every backticked token in the fixture retained-alias table must be "
        "covered by exact architecture-ledger presence or by an explicit "
        "classification-map entry whose anchors exist:\n"
        + "\n".join(uncovered_tokens)
    )

    missing_classification_anchors = {
        token: [anchor for anchor in anchors if anchor not in architecture_text]
        for token, anchors in FIXTURE_TOKEN_CLASSIFICATION_ANCHORS.items()
    }
    missing_classification_anchors = {
        token: anchors
        for token, anchors in missing_classification_anchors.items()
        if anchors
    }
    assert not missing_classification_anchors


def test_ledgers_document_high_risk_retained_alias_distinctions() -> None:
    required_markers = {
        "AgentError": (
            "`AgentError`",
            "Python import compatibility alias",
            "AgentError = FailureEnvelope",
        ),
        "failure_hint_camelcase": (
            "camelCase inputs",
            "`failureKind`",
            "`nextAction`",
            "historical persisted error outcomes",
        ),
        "apply_eligible": (
            "`apply_eligible`",
            "Canonical executor/apply authorization",
            "compatibility fallback",
        ),
        "clarify_forbidden_keys": (
            "_CLARIFY_FORBIDDEN_KEYS",
            "route contract guard",
            "not a compatibility",
        ),
        "edit_layer_clarify_response_sanitizer": (
            "_CLARIFY_FORBIDDEN_RESPONSE_KEYS",
            "_strip_clarify_forbidden_response_fields",
            "_sanitize_pure_clarify_response",
            "response assembly",
            "content-identical to the route-layer set today",
            "pure clarify response assembly no longer emits candidate/apply fields before sanitization",
        ),
    }

    for ledger_name, text in _normalized_ledgers().items():
        for marker_name, markers in required_markers.items():
            missing = [marker for marker in markers if marker not in text]
            assert not missing, f"{ledger_name} ledger missing {marker_name}: {missing}"


def test_ledgers_classify_graph_hash_fields_without_legacy_alias_scanner_escape() -> None:
    for ledger_name, text in _normalized_ledgers().items():
        for marker in (
            "`client_graph_hash`",
            "`candidate_graph_hash`",
            "canonical",
            "N/A",
            "`submitted_client_graph_hash` / `action_client_graph_hash`",
            "Session migration",
        ):
            assert marker in text, f"{ledger_name} ledger missing graph-hash marker: {marker}"
        assert (
            "not a removable legacy alias" in text
            or "not removable legacy aliases" in text
        ), f"{ledger_name} ledger must classify graph hashes as canonical, not legacy aliases"
        assert (
            "Delete only after" in text
            or "Remove only after" in text
        ), f"{ledger_name} ledger missing graph-hash migration deletion trigger"

    scannable_aliases = _ledger_scannable_backend_aliases()
    assert "client_graph_hash" not in scannable_aliases
    assert "candidate_graph_hash" not in scannable_aliases
    assert "client_graph_hash" not in ALIAS_PATTERNS
    assert "candidate_graph_hash" not in ALIAS_PATTERNS
