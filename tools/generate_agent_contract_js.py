#!/usr/bin/env python3
"""Generate agent_edit_response_contract_generated.js from the Python source of truth.

Inputs (and ONLY these — no fixture corpus is ever read):
  1. Four contract constants from vibecomfy/comfy_nodes/agent/contracts.py:
       - REBASELINE_RECOVERY_FIELDS (8 fields)
       - PUBLIC_OUTCOME_KINDS
       - INTERNAL_TO_PUBLIC_OUTCOME
       - FAILURE_HINT_KEYS
  2. Two embedded blocks in this file (verbatim emitted sections):
       - EXTENDED_CONSTANTS_BLOCK
       - HELPERS_BLOCK

The agent_edit fixture corpus under tests/fixtures/agent_edit is a parity
corpus for Python/JS tests — NOT generator input; it must never be referenced
here (guarded by tests/test_agent_contract_codegen.py).

Produces: vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js

Determinism contract:
  - Key ordering follows REBASELINE_RECOVERY_FIELDS tuple order.
  - Double-quoted JS strings throughout.
  - 2-space indentation.
  - Single trailing newline (POSIX).
  - No timestamps, no version hashes, no non-deterministic output.
"""

from __future__ import annotations

import os
import sys


def _ensure_import_path() -> None:
    """Add the repo root to sys.path so we can import vibecomfy."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _load_fields() -> tuple[str, ...]:
    """Load REBASELINE_RECOVERY_FIELDS from the Python source of truth."""
    from vibecomfy.comfy_nodes.agent.contracts import REBASELINE_RECOVERY_FIELDS

    return REBASELINE_RECOVERY_FIELDS


def _load_constants() -> dict[str, object]:
    """Load shared constants from the Python source of truth."""
    from vibecomfy.comfy_nodes.agent.contracts import (
        FAILURE_HINT_KEYS,
        INTERNAL_TO_PUBLIC_OUTCOME,
        PUBLIC_OUTCOME_KINDS,
    )

    # INTERNAL_TO_PUBLIC_OUTCOME in Python includes all mappings; the JS
    # INTERNAL_OUTCOME_KIND_MAP is intentionally a subset — only the entries
    # that map to "candidate" because those are the only ones the JS dispatch
    # logic queries.
    internal_outcome_kind_entries = [
        (k, v)
        for k, v in INTERNAL_TO_PUBLIC_OUTCOME.items()
        if v == "candidate"
    ]
    return {
        "PUBLIC_OUTCOME_KINDS": tuple(PUBLIC_OUTCOME_KINDS),
        "INTERNAL_OUTCOME_KIND_ENTRIES": tuple(internal_outcome_kind_entries),
        "FAILURE_HINT_KEYS": tuple(FAILURE_HINT_KEYS),
    }


# Extended contract sections (completion proofs, obligation ledger, delta
# diagnostics, plan obligation states) plus their helper functions are emitted
# verbatim.  They mirror Python-sourced vocabulary that browser contract tests
# pin exactly — including the Python-canonical delta diagnostic spellings such
# as ``corrupted_delta`` — so they are embedded as fixed template content.
EXTENDED_CONSTANTS_BLOCK = "// \u2500\u2500 Completion proof states and domains (Python-sourced) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n// Source: vibecomfy/comfy_nodes/agent/completion_proofs.py\n\n/** Proof states: pass, fail, not_run, unknown.  Missing proof is never success. */\nexport const COMPLETION_PROOF_STATES = Object.freeze([\n  \"pass\",\n  \"fail\",\n  \"not_run\",\n  \"unknown\",\n]);\n\n/** Proof domains that each report an independent four-state result. */\nexport const COMPLETION_PROOF_DOMAINS = Object.freeze([\n  \"transformation_safety\",\n  \"graph_validity\",\n  \"task_satisfaction\",\n  \"runtime_readiness\",\n]);\n\n// \u2500\u2500 Obligation ledger vocabulary (Python-sourced) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n// Source: vibecomfy/comfy_nodes/agent/obligation_ledger.py\n\n/** Structural obligation kinds. */\nexport const OBLIGATION_KINDS = Object.freeze([\n  \"class_present\",\n  \"class_absent\",\n  \"value_match\",\n  \"edge_exists\",\n  \"terminal_output_domain\",\n  \"scope_preserved\",\n  \"obligation_declared\",\n]);\n\n/** Obligation evaluation statuses. */\nexport const OBLIGATION_STATUSES = Object.freeze([\n  \"satisfied\",\n  \"unsatisfied\",\n  \"unknown\",\n  \"not_evaluated\",\n  \"unsupported\",\n]);\n\n/** Obligation severities (criticality). */\nexport const OBLIGATION_SEVERITIES = Object.freeze([\n  \"required\",\n  \"recommended\",\n  \"optional\",\n]);\n\n// \u2500\u2500 Delta diagnostic codes (Python-sourced) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n// Source: vibecomfy/porting/edit/ops.py\n\nexport const DELTA_DIAGNOSTIC_CORRUPTED = \"corrupted_delta\";\nexport const DELTA_DIAGNOSTIC_TRUNCATED = \"truncated_delta\";\nexport const DELTA_DIAGNOSTIC_ABSENT = \"absent_delta\";\nexport const DELTA_DIAGNOSTIC_REPLAY_MISMATCH = \"replay_mismatch\";\n\n/** All delta diagnostic codes (including those from canonical_delta.js). */\nexport const DELTA_DIAGNOSTIC_CODES = Object.freeze([\n  \"malformed_delta\",\n  \"legacy_delta_shape\",\n  \"unsupported_scoped_apply\",\n  DELTA_DIAGNOSTIC_CORRUPTED,\n  DELTA_DIAGNOSTIC_TRUNCATED,\n  DELTA_DIAGNOSTIC_ABSENT,\n  DELTA_DIAGNOSTIC_REPLAY_MISMATCH,\n]);\n\n// \u2500\u2500 Plan obligation states (Python-sourced) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n// Source: vibecomfy/comfy_nodes/agent/obligation_ledger.py\n\nexport const PLAN_OBLIGATION_STATES = Object.freeze([\n  \"not_required\",\n  \"required_supported\",\n  \"required_unsupported\",\n]);"

HELPERS_BLOCK = "// \u2500\u2500 Proof state helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Check whether a value is a valid completion proof state.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidProofState(value) {\n  return COMPLETION_PROOF_STATES.includes(value);\n}\n\n/**\n * Check whether a value is a valid proof domain.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidProofDomain(value) {\n  return COMPLETION_PROOF_DOMAINS.includes(value);\n}\n\n// \u2500\u2500 Obligation ledger helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Check whether a value is a valid obligation kind.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidObligationKind(value) {\n  return OBLIGATION_KINDS.includes(value);\n}\n\n/**\n * Check whether a value is a valid obligation status.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidObligationStatus(value) {\n  return OBLIGATION_STATUSES.includes(value);\n}\n\n/**\n * Check whether a value is a valid obligation severity.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidObligationSeverity(value) {\n  return OBLIGATION_SEVERITIES.includes(value);\n}\n\n// \u2500\u2500 Delta envelope reader \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Read the cumulative V2 delta envelope from a response.\n * Returns the canonical ``{schema_version, ops}`` envelope or null.\n *\n * @param {*} response - raw response object\n * @returns {object|null}\n */\nexport function readDeltaEnvelope(response) {\n  if (!isObject(response)) {\n    return null;\n  }\n  const accepted = response.accepted_batch;\n  if (!Array.isArray(accepted)) {\n    return null;\n  }\n  const ops = [];\n  for (const statement of accepted) {\n    if (!isObject(statement) || !isObject(statement.op)) {\n      continue;\n    }\n    ops.push(statement.op);\n  }\n  return {\n    schema_version: \"2.0.0\",\n    ops,\n  };\n}\n\n/**\n * Read the idempotency key from a response or its turn identity.\n * @param {*} response - raw response object\n * @returns {string|null}\n */\nexport function readIdempotencyKey(response) {\n  if (!isObject(response)) {\n    return null;\n  }\n  return asString(response.idempotency_key)\n    || asString(response.idempotencyKey)\n    || asString(response.candidate?.turn_identity?.idempotency_key)\n    || asString(response.candidate?.turnIdentity?.idempotencyKey)\n    || asString(response.debug?.turn_identity?.idempotency_key)\n    || asString(response.debug?.turnIdentity?.idempotencyKey)\n    || null;\n}\n\n// \u2500\u2500 Obligation ledger reader \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Read task satisfaction / obligation ledger entries from a response.\n * These mirror the Python-side task_satisfaction and obligation_ledger fields\n * that are serialized onto applyable and clarify responses.\n *\n * @param {*} response - raw response object\n * @returns {object|null} { task_satisfaction, obligation_ledger } or null\n */\nexport function readObligationArtifacts(response) {\n  if (!isObject(response)) {\n    return null;\n  }\n  const taskSatisfaction = Array.isArray(response.task_satisfaction)\n    ? response.task_satisfaction\n    : null;\n  const obligationLedger = isObject(response.obligation_ledger)\n    ? response.obligation_ledger\n    : null;\n  if (!taskSatisfaction && !obligationLedger) {\n    return null;\n  }\n  return {\n    task_satisfaction: taskSatisfaction,\n    obligation_ledger: obligationLedger,\n  };\n}\n\n// \u2500\u2500 Non-applyable clarify detection \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Detect whether a response represents a non-applyable clarify outcome.\n * Non-applyable clarify responses must carry clarification_required=true\n * and must NOT carry candidate, graph, apply_eligible, or eligibility fields\n * that could be mistaken for applyable content.\n *\n * @param {*} response - raw response object\n * @returns {boolean}\n */\nexport function isNonApplyableClarify(response) {\n  if (!isObject(response)) {\n    return false;\n  }\n  const outcomeKind = asString(response.outcome?.kind);\n  if (outcomeKind !== \"clarify\") {\n    return false;\n  }\n  // Non-applyable clarify must not carry candidate payloads.\n  if (isObject(response.candidate) || isObject(response.candidate_graph) || isObject(response.graph)) {\n    return false;\n  }\n  // Must carry clarification markers.\n  if (response.clarification_required !== true && response.clarificationRequired !== true) {\n    return false;\n  }\n  return true;\n}"

def generate_js(fields: tuple[str, ...]) -> str:
    """Produce the complete JS module source as a string."""
    constants = _load_constants()

    field_js_entries = ",\n".join(
        f"    {f}: asString(recovery.{f})"
        for f in fields
    )

    # The search paths for extractRebaselineRecovery — these are the snake_case
    # dotted paths where a rebaseline_recovery object may nest inside a failure
    # response.  They are NOT derived from REBASELINE_RECOVERY_FIELDS; they are
    # the structural response-paths where the recovery payload lives.
    issue_context_paths = [
        "response?.agent_failure_context?.issues",
        "response?.outcome?.agent_failure_context?.issues",
        "response?.debug?.failure?.agent_failure_context?.issues",
    ]
    issue_context_js = ",\n".join(f"    {path}" for path in issue_context_paths)

    # Serialise the Python constants to JS literals.
    import json

    public_outcome_kinds_js = json.dumps(list(constants["PUBLIC_OUTCOME_KINDS"]), indent=2)
    failure_hint_keys_js = json.dumps(list(constants["FAILURE_HINT_KEYS"]), indent=2)
    internal_kind_entries_js = ",\n".join(
        f'    {json.dumps(k)}: {json.dumps(v)}'
        for k, v in constants["INTERNAL_OUTCOME_KIND_ENTRIES"]
    )

    return f"""\
// agent_edit_response_contract_generated.js — Generated JS contract (snake_case canonical)
//
// AUTO-GENERATED by python -m tools.generate_agent_contract_js.
// Source of truth: vibecomfy/comfy_nodes/agent/contracts.py
//
// Symbols in this module use snake_case as the canonical wire format,
// matching the Python wire format and the lifecycle module's existing output.
// camelCase input acceptance and camelCase output wrapping are layered on top
// by agent_edit_response_contract.js — they are NOT part of this module.
//
// inferLegacyOutcome is explicitly JS-only and outside the single-source schema.

// ── Internal helpers ────────────────────────────────────────────────────────

function isObject(value) {{
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}}

function asString(value) {{
  return typeof value === "string" ? value : null;
}}

// ── Constants (shared, Python-sourced) ──────────────────────────────────────

export const PUBLIC_OUTCOME_KINDS = Object.freeze({public_outcome_kinds_js});

export const INTERNAL_OUTCOME_KIND_MAP = Object.freeze({{
{internal_kind_entries_js},
}});

export const FAILURE_HINT_KEYS = Object.freeze({failure_hint_keys_js});

export const NORMALIZED_RESPONSE_MARKER = "__agentEditResponseNormalized";

{EXTENDED_CONSTANTS_BLOCK}

// ── Candidate-payload detection ─────────────────────────────────────────────

/**
 * Check whether a raw response contains a candidate payload.
 *
 * candidate_graph is treated as a peer of candidate and graph (rather than
 * nested under .candidate) because it is the canonical snake_case wire
 * container for structured graph data.  This flattening keeps the logic in
 * normalizeCandidateGraph straightforward and avoids a recursive-normalization
 * tangle when a response carries only candidate_graph without a parent
 * candidate envelope.  The decision is deliberate and cross-checked against
 * the Python-side candidate-graph extraction in agent_edit.py.
 *
 * @param {{*}} response - raw response object
 * @returns {{boolean}}
 */
export function responseHasCandidatePayload(response) {{
  if (!isObject(response)) {{
    return false;
  }}
  return isObject(response.candidate)
    || isObject(response.candidate_graph)
    || isObject(response.graph);
}}

// ── Rebaseline recovery (snake_case canonical) ──────────────────────────────

/**
 * Normalize a raw rebaseline-recovery object to the canonical snake_case shape.
 * Fields not present or non-string are set to null.
 *
 * @param {{*}} recovery - raw recovery value
 * @returns {{object|null}} canonical snake_case recovery, or null
 */
export function normalizeRebaselineRecovery(recovery) {{
  if (!recovery || typeof recovery !== "object") {{
    return null;
  }}
  return {{
{field_js_entries},
  }};
}}

/**
 * Extract a rebaseline-recovery payload from a response object.
 * Searches snake_case paths only:
 *   1. response.rebaseline_recovery (top-level)
 *   2. response.agent_failure_context.issues[*].rebaseline_recovery
 *   3. response.outcome.agent_failure_context.issues[*].rebaseline_recovery
 *   4. response.debug.failure.agent_failure_context.issues[*].rebaseline_recovery
 *
 * camelCase input paths are NOT handled here — see the pre-pass in
 * agent_edit_response_contract.js for camelCase input acceptance.
 *
 * @param {{*}} response - raw response object
 * @returns {{object|null}} canonical snake_case recovery, or null
 */
export function extractRebaselineRecovery(response) {{
  const topLevel = normalizeRebaselineRecovery(response?.rebaseline_recovery);
  if (topLevel) {{
    return topLevel;
  }}
  const issueSources = [
{issue_context_js},
  ];
  for (const issues of issueSources) {{
    if (!Array.isArray(issues)) {{
      continue;
    }}
    for (const issue of issues) {{
      const recovery = normalizeRebaselineRecovery(issue?.rebaseline_recovery);
      if (recovery) {{
        return recovery;
      }}
    }}
  }}
  return null;
}}

{HELPERS_BLOCK}
"""


def main() -> int:
    """Generate and write the JS contract file to disk.

    Pass --output <path> to write to a custom location (for testing).
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=None,
        help="Write to this path instead of the default location.",
    )
    args = parser.parse_args()

    _ensure_import_path()

    fields = _load_fields()

    if len(fields) != 8:
        print(
            f"ERROR: REBASELINE_RECOVERY_FIELDS has {len(fields)} entries; expected 8.",
            file=sys.stderr,
        )
        return 1
    expected = (
        "action",
        "endpoint",
        "reason",
        "last_known_baseline_graph_hash",
        "submit_graph_hash",
        "submit_structural_graph_hash",
        "client_graph_hash",
        "client_structural_graph_hash",
    )
    if fields != expected:
        print(
            f"ERROR: REBASELINE_RECOVERY_FIELDS does not match expected canonical order.\n"
            f"  got:      {fields!r}\n"
            f"  expected: {expected!r}",
            file=sys.stderr,
        )
        return 1

    js_source = generate_js(fields)

    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "vibecomfy",
            "comfy_nodes",
            "web",
            "agent_edit_response_contract_generated.js",
        )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(js_source)

    print(f"Wrote {output_path} ({len(js_source)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
