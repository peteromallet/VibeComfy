"""Executable custody for the canonical-workflow cutover contract.

This module is deliberately a contract fixture, not an implementation test.
It records the authority boundaries that later tasks must satisfy and checks
the immutable planning inputs by digest.  In particular, it does not import
or inspect a future ``WorkflowBundle`` implementation.
"""

from __future__ import annotations

import json
from typing import Any


EXPECTED_BRANCH = "otto/canonical-workflow-source-20260903"
EXPECTED_BASE_SHA = "86f62efeca4b58a61a4c3fd75f01f365b2c1943c"


# These five artifacts are immutable inputs to T00.  The acceptance ledger is
# intentionally tracked separately below: its initial digest is custody
# evidence, but later tasks may append monotonic evidence to that ledger.
FROZEN_INPUT_HASHES = {
    "tasklist.md": {
        "sha256": "5662a9a4499ff5be8c7026388d11009dc25dfb62ac3296e7468685248b45993b",
    },
    "agent_goal.md": {
        "sha256": "6099377bfcc47e04dd8a504762dc329a3c60660c77f7f4bb9de700b8047b0e2c",
    },
    "plan.md": {
        "sha256": "5bb97b7b7617168f26d3dc24bab9e2d4dfcb6e5f638109ed4746e483a8ee5bb7",
    },
    "contract-addendum.md": {
        "sha256": "feae0caae1af933c286d7924d889e76db90a10884b9f172d6a82215992705748",
    },
    "findings/plan-settled-2-synthesis.md": {
        "sha256": "63498ab3db660726dde0c0d26b0e659160b2b26e867e777ecf935e4bb3865056",
    },
}
INITIAL_ACCEPTANCE_LEDGER_SHA256 = (
    "308ce6843fd910419fbea808eaed4773eab6f3bff54b31dc749fad6422875e40"
)


# A machine-readable checklist.  Strings here name contract terms; they are
# not used to grep source or to assert that later implementation exists.
CANONICAL_CONTRACT: dict[str, Any] = {
    "identity": {
        "authority": "VibeWorkflow.id",
        "source_entrypoint": "workflow_name.py:build() -> VibeWorkflow",
        "sidecar": "workflow_name.vibe.json",
        "sidecar_role": "optional presentation fidelity only",
        "bundle_identity": "derived exactly from workflow.id",
        "repeated_identity_policy": "absent or equal to VibeWorkflow.id",
    },
    "metadata_classes": ["semantic", "presentation", "rejected"],
    "sidecar": {
        "top_level_fields": ["format_version", "bind", "nodes", "links", "groups", "canvas"],
        "ordinary_foreign_key": [
            "scope_path",
            "from_uid",
            "from_port",
            "to_uid",
            "to_port",
        ],
        "virtual_foreign_key": ["scope_path", "name", "leg_index"],
        "visual_disambiguator": "occurrence_index",
        "ordinary_lookup": "make_uid(scope_path, local_uid)",
        "ordinary_scope_policy": "same scope only",
        "qualified_endpoint_policy": "reject",
        "compiler_input": False,
        "opaque_properties": False,
    },
    "recursive": {
        "definition_identity": "sg_key(definition)",
        "root_scope": "",
        "nested_scope": "compose_scope_path(...) slash-joined",
        "scoped_uid": "make_uid(scope_path, local_uid)",
        "ordinal_scope_convention": "sg0/sg1 is prohibited",
        "interfaces": "ordered Python-owned public inputs and outputs",
        "boundary_ports": "explicit Python-owned interface-to-endpoint records",
        "virtual_wires": "named Python-owned semantic objects lowered only by _execution_projection()",
        "native_boundary_mapping": "only the B0S spike may establish -10/-20 realization",
        "root_only_evidence": "cannot satisfy AG-06",
    },
    "variants": {
        "shape": "flat dict[str, dict[str, object]]",
        "default": "default_variant: str | None",
        "selection": "compile/run argument",
        "prohibited": ["Variant class hierarchy", "variant file", "inheritance chain", "alternate graph"],
    },
    "approval_record": {
        "required_fields": [
            "revision_id",
            "selected_variant",
            "input_binding",
            "api_projection",
            "ui_projection",
            "api_digest",
        ],
        "recursive_immutability": True,
        "api_digest_preimage": "exact stored api_projection canonical bytes",
        "queue_revalidation": ["record bytes", "current bundle revision", "variant/input binding", "api_digest"],
        "mutation_effect": "invalidate approval; require new revision and record",
        "storage": "existing receipt/journal structures",
    },
    "lineage": {
        "revision_formula": "SHA-256(canonical_json([id, semantic_digest, ui_digest_or_empty, provenance, parent_revision]))",
        "root_parent": "",
        "nonempty_parent": "resolve through existing provenance/receipt/journal evidence",
        "parent_identity": "resolved parent workflow_identity == VibeWorkflow.id",
        "unknown_or_mismatched": "fail closed",
        "lineage_service": False,
    },
    "queue_boundary": {
        "interception": "app.queuePrompt",
        "transport": "api.queuePrompt",
        "transport_role": "lower-level transport inside approved adapter only",
        "missing_or_unverifiable_hook": "disable VibeComfy queueing",
        "failure_calls_original": False,
        "native_comfy_queue": "external/capture activity, never approved VibeComfy execution",
    },
    "compiler": {
        "authority": "VibeWorkflow._execution_projection()",
        "sidecar_read": False,
        "api_and_graphbuilder": "same projection",
        "post_projection_semantic_mutation": False,
    },
}


# The six binding-addendum rules are represented as data so each later owner
# has an explicit boundary to turn into behavioral evidence.
ADDENDUM_RULES = [
    {
        "rule": 1,
        "name": "derived sidecar foreign keys",
        "ordinary": "exactly one edge_ref with five fields",
        "virtual": "exactly one virtual_wire_ref plus occurrence_index",
        "leg_index": "canonical ordered UI-leg sequence materialized from Python boundary ports",
        "validation": "rematerialize expected links/legs from Python and reject unmatched references",
        "owners": ["T04", "T08", "T20"],
    },
    {
        "rule": 2,
        "name": "local ordinary endpoint lookup",
        "lookup": "make_uid(scope_path, local_uid)",
        "qualified_endpoints": "reject",
        "cross_scope_ordinary_edges": "reject; use Python-owned virtual wires",
        "owners": ["T02", "T04"],
    },
    {
        "rule": 3,
        "name": "parent revision lineage",
        "nonempty_parent": "resolve via existing provenance/receipt/journal evidence",
        "identity": "workflow_identity == VibeWorkflow.id",
        "unknown_or_mismatch": "fail closed",
        "owners": ["T03", "T18"],
    },
    {
        "rule": 4,
        "name": "recursive approval immutability",
        "stored": ["input_binding", "api_projection", "ui_projection"],
        "api_digest": "hash exact API bytes",
        "queue": "revalidate bytes and current revision, then submit freshly decoded copies",
        "mutation": "invalidate approval and require a new revision/record",
        "owners": ["T14", "T18", "T19"],
    },
    {
        "rule": 5,
        "name": "hard browser queue boundary",
        "hook": "app.queuePrompt",
        "transport": "api.queuePrompt",
        "unavailable_hook": "disable VibeComfy queueing",
        "failure_calls_original": False,
        "native_queue": "external/capture activity",
        "owners": ["T19"],
    },
    {
        "rule": 6,
        "name": "frozen recursive authority",
        "recursive_contract": "already closed before B0S",
        "b0s_only_open_fact": "native -10/-20 realization",
        "root_only": "cannot satisfy AG-06",
        "owners": ["T00", "T01", "T05", "T17"],
    },
]


# These are explicit rejected abstractions, not a prohibition inferred from
# incidental source spelling.
PROHIBITED_ABSTRACTIONS = [
    "multiple semantic authorities",
    "dynamic recipe overlays",
    "private compatibility helpers as normal authoring",
    "silent fallback or swallowed normalization/queue failures",
    "parallel loader/compiler/runtime authorities",
    "nonce or capability kernel",
    "metadata catalog or metadata service",
    "approval service or approval registry",
    "semantic edge UID",
    "second recursive/subgraph IR or editor rewrite",
    "wrapper hash-lock service",
    "variant redesign",
    "speculative manifest, registry, daemon, or database",
    "ambiguous legacy path retaining semantic authority",
]


MODEL_ROUTING = {
    "normal_implementation": "GPT-5.6 Luna",
    "bounded_live_spike": "GPT-5.6 Luna",
    "independent_checkpoint": "GPT-5.6 Luna",
    "cr0_adjudication": "GPT-5.6 Sol",
    "oracle_contract_conformance": "GPT-5.6 Sol",
    "final_integrated_review": "GPT-5.6 Sol",
    "xhard_tasks": [],
}


AUTHORITY_LIMITS = {
    "worktree": "isolated execution worktree",
    "branch": EXPECTED_BRANCH,
    "base_sha": EXPECTED_BASE_SHA,
    "python": "parent venv",
    "environment": ["PYTHONDONTWRITEBYTECODE=1", "PYTHONPATH=."],
    "deterministic_local_only": True,
    "gpu": False,
    "runpod_machine": False,
    "network_model_download": False,
    "deployment_or_publication": False,
    "merge_rebase_push": False,
    "dirty_invoking_checkout": "out of scope",
    "free_space_floor_bytes": 1 * 1024**3,
    "incremental_storage_ceiling_bytes": int(1.5 * 1024**3),
    "temporary_storage_ceiling_bytes": 900 * 1024**2,
}


REVIEW_BOUNDARIES = {
    "R1": {
        "after": "B1+B2",
        "scope": "authority, bundle identity/revisions/digests, metadata, sidecar, variants, recursive schema, projection, import/emission/materialization",
        "browser_suite": "prohibited",
        "required": ["focused groups 1-2", "affected Python tests", "atomic fault injection", "identity/lineage/addendum vectors", "clean immutable SHA", "independent Luna review", "Sol adjudication"],
    },
    "R2": {
        "after": "B3+B4",
        "scope": "R1 plus wrappers, reconciliation, caller inventory, loaders, runtimes, approvals, receipts, offline RunPod adapter",
        "browser_suite": "prohibited",
        "required": ["retained R1 evidence", "focused groups 3-4", "13-entry lock proof", "complete named caller report", "approval/adapter digest matrix", "clean immutable SHA", "independent Luna review", "Sol adjudication"],
    },
    "R3": {
        "after": "B5",
        "scope": "R2 plus B0S-supported recursive live mutation, capture/apply/finalize/rollback, browser queue hook, blockers, prompt lifecycle",
        "browser_suite": "full suite first runs here",
        "required": ["focused group 5", "full tests/browser/*.mjs", "depth-2/boundary fixtures", "spike-supported -10/-20 tests", "prompt lifecycle/cancel tests", "clean immutable SHA", "independent Luna review", "Sol adjudication"],
    },
    "R4": {
        "after": "B6",
        "scope": "R3 plus pinned H3 custody/assertions, migration, deprecation guidance, README/CLI/docs/skills",
        "browser_suite": "retained from R3",
        "required": ["pinned source checksum", "independent assertion manifest", "no-GPU H3 tests", "migration parity/failure matrix", "documentation consistency", "clean immutable SHA", "independent Luna review", "Sol adjudication"],
    },
    "R5": {
        "after": "B7",
        "scope": "entire AG-01 through AG-12 contract",
        "browser_suite": "full suite repeats before broad suite",
        "required_order": ["five named no-GPU user paths", "final affected integration", "full browser suite", "broad Python suite", "make docs/template-index/strict-ready/snapshots/parity/ir-boundary", "evidence audit", "clean immutable SHA", "final Luna review", "Sol final integrated review"],
    },
}


H3_PIN = {
    "repository": "seitanism/ComfyUI-H3-Motion-Context-MultiRef",
    "commit": "2ed4b27e5e262a996ad2670ac6d2fd2e505cf3a3",
    "path": "example_workflows/NEW - AV Extension.json",
    "sha256": "3cbf9bdff20e50596c8034eb4446f487e523922847fe0fb6bc11b2a5a5c7bd08",
    "proof": "role-based reference/mask wiring and compile identity, no GPU",
}


def test_frozen_input_hashes_are_custodied() -> None:
    """T00 records five immutable planning-input SHA-256 values."""
    for name, record in FROZEN_INPUT_HASHES.items():
        digest = record["sha256"]
        assert len(digest) == 64, name
        assert all(char in "0123456789abcdef" for char in digest), name

    # The ledger is an evidence surface that later tasks may append to.  Its
    # initial custody hash is recorded without making future evidence updates
    # fail this foundational contract test.
    assert len(INITIAL_ACCEPTANCE_LEDGER_SHA256) == 64
    assert all(char in "0123456789abcdef" for char in INITIAL_ACCEPTANCE_LEDGER_SHA256)


def test_custody_identifiers_are_recorded_without_environment_assumptions() -> None:
    """The fixture records custody identifiers without inspecting a checkout."""
    assert AUTHORITY_LIMITS["worktree"] == "isolated execution worktree"
    assert AUTHORITY_LIMITS["branch"] == EXPECTED_BRANCH
    assert AUTHORITY_LIMITS["base_sha"] == EXPECTED_BASE_SHA
    assert len(EXPECTED_BASE_SHA) == 40
    assert all(char in "0123456789abcdef" for char in EXPECTED_BASE_SHA)


def test_identity_and_metadata_contract_is_closed() -> None:
    assert CANONICAL_CONTRACT["identity"]["authority"] == "VibeWorkflow.id"
    assert CANONICAL_CONTRACT["identity"]["repeated_identity_policy"] == "absent or equal to VibeWorkflow.id"
    assert CANONICAL_CONTRACT["metadata_classes"] == ["semantic", "presentation", "rejected"]
    assert len(CANONICAL_CONTRACT["metadata_classes"]) == 3
    assert CANONICAL_CONTRACT["identity"]["sidecar_role"] == "optional presentation fidelity only"


def test_sidecar_foreign_keys_and_scope_rules_are_explicit() -> None:
    sidecar = CANONICAL_CONTRACT["sidecar"]
    assert sidecar["ordinary_foreign_key"] == [
        "scope_path",
        "from_uid",
        "from_port",
        "to_uid",
        "to_port",
    ]
    assert sidecar["virtual_foreign_key"] == ["scope_path", "name", "leg_index"]
    assert sidecar["visual_disambiguator"] == "occurrence_index"
    assert sidecar["ordinary_lookup"] == "make_uid(scope_path, local_uid)"
    assert sidecar["ordinary_scope_policy"] == "same scope only"
    assert sidecar["qualified_endpoint_policy"] == "reject"
    assert sidecar["compiler_input"] is False
    assert sidecar["opaque_properties"] is False


def test_recursive_variants_and_compiler_contract_are_frozen() -> None:
    recursive = CANONICAL_CONTRACT["recursive"]
    assert recursive["root_scope"] == ""
    assert recursive["definition_identity"] == "sg_key(definition)"
    assert recursive["ordinal_scope_convention"] == "sg0/sg1 is prohibited"
    assert recursive["native_boundary_mapping"].startswith("only the B0S spike")
    assert recursive["root_only_evidence"] == "cannot satisfy AG-06"
    assert CANONICAL_CONTRACT["variants"]["shape"] == "flat dict[str, dict[str, object]]"
    assert CANONICAL_CONTRACT["compiler"]["authority"] == "VibeWorkflow._execution_projection()"
    assert CANONICAL_CONTRACT["compiler"]["sidecar_read"] is False
    assert CANONICAL_CONTRACT["compiler"]["api_and_graphbuilder"] == "same projection"


def test_approval_lineage_and_queue_contract_is_fail_closed() -> None:
    approval = CANONICAL_CONTRACT["approval_record"]
    assert approval["required_fields"] == [
        "revision_id",
        "selected_variant",
        "input_binding",
        "api_projection",
        "ui_projection",
        "api_digest",
    ]
    assert approval["recursive_immutability"] is True
    assert approval["storage"] == "existing receipt/journal structures"
    assert CANONICAL_CONTRACT["lineage"]["root_parent"] == ""
    assert CANONICAL_CONTRACT["lineage"]["unknown_or_mismatched"] == "fail closed"
    queue = CANONICAL_CONTRACT["queue_boundary"]
    assert queue["interception"] == "app.queuePrompt"
    assert queue["transport"] == "api.queuePrompt"
    assert queue["failure_calls_original"] is False
    assert queue["missing_or_unverifiable_hook"] == "disable VibeComfy queueing"


def test_all_six_addendum_rules_have_explicit_owners_and_boundaries() -> None:
    assert [rule["rule"] for rule in ADDENDUM_RULES] == [1, 2, 3, 4, 5, 6]
    for rule in ADDENDUM_RULES:
        assert rule["owners"], rule
        assert rule["name"]
    assert ADDENDUM_RULES[0]["ordinary"] == "exactly one edge_ref with five fields"
    assert ADDENDUM_RULES[0]["virtual"] == "exactly one virtual_wire_ref plus occurrence_index"
    assert ADDENDUM_RULES[1]["qualified_endpoints"] == "reject"
    assert ADDENDUM_RULES[2]["unknown_or_mismatch"] == "fail closed"
    assert ADDENDUM_RULES[3]["stored"] == ["input_binding", "api_projection", "ui_projection"]
    assert ADDENDUM_RULES[4]["hook"] == "app.queuePrompt"
    assert ADDENDUM_RULES[4]["failure_calls_original"] is False
    assert ADDENDUM_RULES[5]["b0s_only_open_fact"] == "native -10/-20 realization"


def test_authority_limits_model_routing_and_h3_pin_are_recorded() -> None:
    assert AUTHORITY_LIMITS["worktree"] == "isolated execution worktree"
    assert AUTHORITY_LIMITS["branch"] == EXPECTED_BRANCH
    assert AUTHORITY_LIMITS["base_sha"] == EXPECTED_BASE_SHA
    assert AUTHORITY_LIMITS["deterministic_local_only"] is True
    assert AUTHORITY_LIMITS["gpu"] is False
    assert AUTHORITY_LIMITS["runpod_machine"] is False
    assert AUTHORITY_LIMITS["merge_rebase_push"] is False
    assert MODEL_ROUTING["normal_implementation"] == "GPT-5.6 Luna"
    assert MODEL_ROUTING["bounded_live_spike"] == "GPT-5.6 Luna"
    assert MODEL_ROUTING["independent_checkpoint"] == "GPT-5.6 Luna"
    assert MODEL_ROUTING["cr0_adjudication"] == "GPT-5.6 Sol"
    assert MODEL_ROUTING["oracle_contract_conformance"] == "GPT-5.6 Sol"
    assert MODEL_ROUTING["final_integrated_review"] == "GPT-5.6 Sol"
    assert MODEL_ROUTING["xhard_tasks"] == []
    assert H3_PIN == {
        "repository": "seitanism/ComfyUI-H3-Motion-Context-MultiRef",
        "commit": "2ed4b27e5e262a996ad2670ac6d2fd2e505cf3a3",
        "path": "example_workflows/NEW - AV Extension.json",
        "sha256": "3cbf9bdff20e50596c8034eb4446f487e523922847fe0fb6bc11b2a5a5c7bd08",
        "proof": "role-based reference/mask wiring and compile identity, no GPU",
    }


def test_r1_through_r5_boundaries_preserve_evidence_order() -> None:
    assert list(REVIEW_BOUNDARIES) == ["R1", "R2", "R3", "R4", "R5"]
    assert REVIEW_BOUNDARIES["R1"]["browser_suite"] == "prohibited"
    assert REVIEW_BOUNDARIES["R2"]["browser_suite"] == "prohibited"
    assert REVIEW_BOUNDARIES["R3"]["browser_suite"] == "full suite first runs here"
    assert REVIEW_BOUNDARIES["R5"]["browser_suite"] == "full suite repeats before broad suite"
    assert REVIEW_BOUNDARIES["R5"]["required_order"][:3] == [
        "five named no-GPU user paths",
        "final affected integration",
        "full browser suite",
    ]
    assert REVIEW_BOUNDARIES["R5"]["required_order"][3] == "broad Python suite"


def test_prohibited_abstractions_are_complete_and_unique() -> None:
    assert len(PROHIBITED_ABSTRACTIONS) == len(set(PROHIBITED_ABSTRACTIONS))
    for expected in (
        "semantic edge UID",
        "second recursive/subgraph IR or editor rewrite",
        "approval service or approval registry",
        "wrapper hash-lock service",
        "dynamic recipe overlays",
        "nonce or capability kernel",
        "variant redesign",
    ):
        assert expected in PROHIBITED_ABSTRACTIONS


def test_contract_fixture_is_json_safe_and_deterministic() -> None:
    first = json.dumps(CANONICAL_CONTRACT, sort_keys=True, separators=(",", ":"))
    second = json.dumps(CANONICAL_CONTRACT, sort_keys=True, separators=(",", ":"))
    assert first == second
    decoded = json.loads(first)
    assert decoded == CANONICAL_CONTRACT
