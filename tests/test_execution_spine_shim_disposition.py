"""T5.5 execution-spine shim retirement: frozen S70↔owner disposition manifest.

Freezes the complete disposition of every execution-spine shim row found by the
T5.5 census (workflow-execution-spine-consolidation plan card T5.5, gate G5),
reconciled against the structural-cleanup master plan's repository-wide ``S70``
census contract (§14.1/§S70).  ``S78`` can consume this module to prove zero
unclassified rows.

Row contract:
- exactly one owner: this card (``"T5.5"``) or one exact structural-cleanup
  card ``S71``–``S77``;
- exactly one disposition:
  ``delete_now`` | ``collapse_into_owner`` | ``migrate_then_delete`` |
  ``retain_temporary`` | ``out_of_scope_structural_card``;
- retained rows name the consumer evidence, the compatibility test that fails
  if the shim is removed or changes, an explicit removal condition, and an
  authority note proving the shim cannot grant admission/replay authority;
- deleted rows must stay deleted: their symbols are asserted absent from the
  named source files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

DISPOSITIONS = {
    "delete_now",
    "collapse_into_owner",
    "migrate_then_delete",
    "retain_temporary",
    "out_of_scope_structural_card",
}
OWNER_RE = re.compile(r"^(T5\.5|S7[1-7])$")


# ── the frozen manifest itself ────────────────────────────────────────────────

T55_DISPOSITION = (
    # ── deleted by this card ────────────────────────────────────────────────
    {
        "id": "T5.5-DS-01",
        "surface": "tests/live_agentic_harness/intent_judge.py # _verify_delta_replay_legacy_removed",
        "kind": "dead legacy stub (home-made UI-widget walker marker)",
        "owner": "T5.5",
        "disposition": "delete_now",
        "consumer_evidence": (
            "grep repo-wide: zero references; superseded by _verify_delta_replay "
            "(Law 3: judge verifies accepted Δ via interpret(pre,Δ)/diff)"
        ),
        "compat_test": ["tests/test_live_agentic_harness_guard_contract.py"],
        "removal_condition": "",
        "authority_note": "stub was pragma no-cover documentation only; no behavior path",
    },
    {
        "id": "T5.5-DS-02",
        "surface": (
            "vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py # "
            "_iter_legacy_field_changes,_infer_delta_ops_from_legacy_field_changes"
        ),
        "kind": "legacy delta/candidate projection (pre-delta FieldChange → upsert_link inference)",
        "owner": "T5.5",
        "disposition": "delete_now",
        "consumer_evidence": (
            "grep vibecomfy/ tests/ scripts/ tools/: only definition, internal call, and __all__ "
            "self-references; not in session freeze (private_imported_by_name 23); canonical Δ is "
            "accepted_batch-only via _load_turn_delta_ops which documents 'FieldChange inference "
            "are not consulted'"
        ),
        "compat_test": ["tests/test_comfy_nodes_agent_backend_spine.py"],
        "removal_condition": "",
        "authority_note": (
            "removal tightens authority: accepted_batch becomes the only durable Δ reader; "
            "no supported consumer could route through the inferred path"
        ),
    },
    {
        "id": "T5.5-DS-03",
        "surface": "vibecomfy/comfy_nodes/agent/_frag_transform_stages.py # docstring 'frozen 472-name __all__'",
        "kind": "stale census-count ledger comment (S70 known census question)",
        "owner": "T5.5",
        "disposition": "delete_now",
        "consumer_evidence": (
            "master plan S70: comments/tests disagreed 472 vs 441; live freeze is 440 after B3 "
            "retired _stage_apply_delta; corrected to cite cleanup_surface_manifest.json"
        ),
        "compat_test": ["tests/test_cleanup_surface_manifest.py"],
        "removal_condition": "",
        "authority_note": "docstring-only; PINNED_EDIT_EXPORT_COUNT=440 unchanged",
    },
    # ── retained temporarily, owned by this card ────────────────────────────
    {
        "id": "T5.5-RS-01",
        "surface": "vibecomfy/executor/core.py:90-160 # handle_agent_edit/classify_failure/... forwards + _legacy_host_ports + _default_host_ports",
        "kind": "monkeypatch forwarding delegates over ExecutorHostPorts",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": (
            "tests/structural_harness/actors.py + actors_agent_judgment.py mock.patch "
            "vibecomfy.executor.core.{handle_agent_edit,run_classify_turn,run_reply_turn,"
            "run_agent_research_stage}; tests/test_executor_host_boundary.py monkeypatches "
            "executor_core._default_host_ports and injects host_ports"
        ),
        "compat_test": [
            "tests/test_executor_host_boundary.py",
            "tests/test_executor_flows.py",
        ],
        "removal_condition": (
            "structural S72c executes E61/E64 port census: migrate structural-harness actors to "
            "injected ExecutorHostPorts, then delete the module-level forwards and "
            "_legacy_host_ports"
        ),
        "authority_note": (
            "delegates forward into the same ExecutorHostPorts built once; operation admission "
            "stays admit_operation (porting.edit.admit) — a patched host function cannot mint "
            "an accepted delta or replay proof"
        ),
    },
    {
        "id": "T5.5-RS-02",
        "surface": "vibecomfy/executor/contracts.py:115-144 # _ORCHESTRATION_MODE_ALIASES full→staged, two_step→threaded (+ staged wire omission core.py:3627-3641)",
        "kind": "wire-boundary mode alias + byte-compatible omission",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": (
            "served/headless clients still send full/two_step; frozen canonicalization in "
            "tests/test_pipeline_mode_surface.py::test_headless_mode_boundary_canonicalizes_aliases "
            "and ::test_headless_default_preserves_staged_compatibility_omission"
        ),
        "compat_test": [
            "tests/test_pipeline_mode_surface.py",
        ],
        "removal_condition": (
            "S74b removes the alias map after served clients stop sending full/two_step and the "
            "staged omission window closes; resolve happens once at ExecutorRequest ingress, so "
            "no fork exists below orchestration"
        ),
        "authority_note": "alias resolves to the two canonical modes before any deliberation; cannot create a third mode or bypass run_executor",
    },
    {
        "id": "T5.5-RS-03",
        "surface": "tests/live_agentic_harness/intent_judge.py:988-1004 # canonical_diff seed fallback [T5.5-LS-01]",
        "kind": "harness-side legacy-artifact fallback (judge grading lens)",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": (
            "r5 regression fixtures lacking T5.1 lineage manifests still grade through "
            "diff(pre_wf, post_wf); inline ledger marker T5.5-LS-01 at :992"
        ),
        "compat_test": [
            "tests/test_live_agentic_assessor_score_honesty.py",
            "tests/test_semantic_assessor.py",
        ],
        "removal_condition": "RC12b comparison fixtures regenerated with typed T5.1 lineage manifests",
        "authority_note": (
            "harness-grading only: the seed never enters accepted_batch, admission, or replay; "
            "semantic assessor separately refuses legacy delta_ops projections by design"
        ),
    },
    {
        "id": "T5.5-RS-04",
        "surface": "vibecomfy/comfy_nodes/agent/routes.py:69,980-997 + executor_durable.py:421-422 # underscored durable-turn wrapper-on-wrapper aliases",
        "kind": "wrapper-on-wrapper preserving routes monkeypatch location",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": (
            "tests/test_routes_session_sanitization.py patch.object(routes_mod, "
            "'_maybe_write_executor_only_durable_turn') x6 + direct calls; "
            "tests/test_comfy_nodes_agent_backend_spine.py:11206+ calls routes._maybe_write..."
        ),
        "compat_test": [
            "tests/test_routes_session_sanitization.py",
            "tests/test_comfy_nodes_agent_backend_spine.py",
        ],
        "removal_condition": (
            "S72c/S73 migrate those consumers to the public maybe_write_executor_only_durable_turn, "
            "then delete routes._maybe_write... def, executor_durable.py:421-422 aliases, and the "
            "routes.py:69 chat-artifact alias"
        ),
        "authority_note": "pure delegation to the same executor_durable implementation; both layers write identical artifacts; no second commit path exists",
    },
    {
        "id": "T5.5-RS-05",
        "surface": "vibecomfy/comfy_nodes/agent/_frag_session_bundle.py:286-335 # VIBECOMFY_AGENT_EDIT_LEGACY deprecation warning + ignored legacy protocol env vars",
        "kind": "deprecated env-var compatibility warn (fail-closed ignore)",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": (
            "tests/test_comfy_nodes_agent_edit.py:1374-1394 asserts the warning fires and legacy "
            "public-protocol env selection is refused; product protocol always batch_repl "
            "(_agent_edit_contract :335)"
        ),
        "compat_test": ["tests/test_comfy_nodes_agent_edit.py"],
        "removal_condition": (
            "S75 deletes the warn helper + env scan when deployments no longer set "
            "VIBECOMFY_AGENT_EDIT_LEGACY and the forbidden freeze test is migrated with them; "
            "edit.__all__ entry removal requires regenerating cleanup_surface_manifest.json "
            "through that plan's integration path"
        ),
        "authority_note": "legacy env can only select between refusing contracts; it never activates an alternate mutation authority",
    },
    {
        "id": "T5.5-RS-06",
        "surface": 'vibecomfy/comfy_nodes/agent/provider.py:1136,1378,1447,1711 # "legacy_deepseek_fallback_enabled": False audit stamp',
        "kind": "always-False dead diagnostic flag (retired deepseek fallback)",
        "owner": "T5.5",
        "disposition": "migrate_then_delete",
        "consumer_evidence": (
            "asserted False by tests/test_comfy_nodes_agent_backend_spine.py:4096 and "
            "tests/test_comfy_nodes_agent_edit.py:11146 (both outside this card's file allowance)"
        ),
        "compat_test": [
            "tests/test_comfy_nodes_agent_backend_spine.py",
            "tests/test_comfy_nodes_agent_edit.py",
        ],
        "removal_condition": (
            "S71 migrates the two assertions off the flag, then deletes all four stamping sites"
        ),
        "authority_note": "constant False; gates nothing; purely historical audit metadata",
    },
    {
        "id": "T5.5-RS-07",
        "surface": "vibecomfy/porting/edit/__init__.py:8-106 (+ executor/, ingest/, comfy_nodes/agent/ package inits) # lazy __getattr__ public façades used by spine callers",
        "kind": "lazy re-export façade (headless import / cycle-break purpose per master plan §14.1)",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": (
            "tests/test_porting_edit_kernel.py:8 imports ClaimReferenceError/EditSession/"
            "apply_edit_tool_call/close_terminal_checkpoint through the façade; executor core "
            "imports close_terminal_checkpoint; eager import safety not yet proven"
        ),
        "compat_test": [
            "tests/test_porting_edit_kernel.py",
            "tests/test_api_surface.py",
        ],
        "removal_condition": (
            "S73 may collapse to eager exports only after fresh-process headless-import checks "
            "prove no ComfyUI pull-in; otherwise retain as documented public surface"
        ),
        "authority_note": "names resolve to the single canonical owners (admit/checkpoint/session); façade adds no second implementation",
    },
    {
        "id": "T5.5-RS-08",
        "surface": "vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1-217 # EditBatchReplDeps invocation-time globals() resolution (B37 seam)",
        "kind": "monkeypatch/cycle dependency-resolution seam (71-name deps bag)",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": (
            "edit.py:517-545 _stage_agent_batch_repl delegate is frozen patched_via_edit_module "
            "(cleanup_surface_manifest); tests/test_edit_batch_repl_dependencies.py freezes the "
            "field set/no-singleton/missing-name error"
        ),
        "compat_test": [
            "tests/test_edit_batch_repl_dependencies.py",
            "tests/test_cleanup_surface_manifest.py",
        ],
        "removal_condition": (
            "S75 replaces the globals() bag with typed capabilities when the B37 typed-capability "
            "card lands; the builder stays until every host field has a typed port"
        ),
        "authority_note": "deps resolve to the same _frag_* functions; mutation authority still flows through admit_operation + verify_apply",
    },
    {
        "id": "T5.5-RS-09",
        "surface": "vibecomfy/porting/edit/checkpoint.py:847 # _ops_from_durable_payload reads deltas OR accepted_batch",
        "kind": "dual-key durable payload reader (pre-T2.2 checkpoints)",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": (
            "persisted terminal checkpoints written before the accepted-batch freeze carry deltas; "
            "projector recovery tested in tests/test_terminal_checkpoint.py:27-160"
        ),
        "compat_test": ["tests/test_terminal_checkpoint.py"],
        "removal_condition": (
            "S74b drops the deltas key once persisted checkpoints are outside the recovery window "
            "(contract 5: accepted_batch sole mutation authority)"
        ),
        "authority_note": "reader projects evidence only; it cannot synthesize ops — parse failure yields undetermined, never a fabricated batch",
    },
    {
        "id": "T5.5-RS-10",
        "surface": "vibecomfy/porting/edit/constants.py:17-25 # decode_channel_side_payload legacy sequence form",
        "kind": "stored accepted-batch side-channel adapter (widget-name sequence → {widgets, order})",
        "owner": "T5.5",
        "disposition": "retain_temporary",
        "consumer_evidence": "stored accepted-batch payloads from earlier turns replay through interpreter/session mixins; in-file deprecation comment L22-25",
        "compat_test": ["tests/test_porting_edit_delta_contract.py"],
        "removal_condition": "S74b removes the sequence branch when stored accepted-batch fixtures are regenerated in current form",
        "authority_note": "decodes already-admitted op payloads for replay; admits nothing new",
    },
    # ── out of scope here: exact structural-card owners ─────────────────────
    {
        "id": "T5.5-XS-01",
        "surface": "session.accept_turn session.py:3911-4063 + contracts.ACCEPT_TO_FINALIZE_BRIDGE contracts.py:109-138 + routes /accept routes.py:1770",
        "kind": "route bridge (accept-to-finalize) with idle counter",
        "owner": "S74",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "routes.py binds accept_turn wrapper (:56-57,:1653); live browsers POST /finalize; "
            "counter accept_bridge_v2_count records usage; deletion_condition encoded in metadata"
        ),
        "compat_test": ["tests/test_comfy_nodes_agent_session.py"],
        "removal_condition": "bridge counter unused for one agreed release cycle → delete accept_turn, /accept route, metadata, counter (encoded in ACCEPT_TO_FINALIZE_BRIDGE)",
        "authority_note": "V1 accept is fail-closed read-only via classify_legacy_migration_v1; cannot mutate turns",
    },
    {
        "id": "T5.5-XS-02",
        "surface": "vibecomfy/comfy_nodes/agent/contracts.py:678-730 build_legacy_agent_edit_v1 (+ _frag_response_contract/_legacy_failure_response, executor_response._executor_compatibility_fields)",
        "kind": "v1 wire alias stamping adapter (apply_allowed/queue_allowed/candidate_graph/graph/apply_eligibility)",
        "owner": "S74",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "called by FailureEnvelope.to_dict, ensure_agent_edit_response_contract, response "
            "builders; browser normalizer reads aliases under allowLegacy; governed by "
            "tests/fixtures/agent_edit/compatibility_ledger.md allowlist scanner"
        ),
        "compat_test": [
            "tests/test_agent_edit_compatibility_ledger.py",
            "tests/browser/payload_contracts.test.mjs",
        ],
        "removal_condition": "MIG-G2 window: frontend eligibility/candidate projections go canonical (allowLegacy=false fixtures) then adapter deletes",
        "authority_note": "aliases are stamped AFTER canonical assembly; apply authorization derives from derive_gates/eligibility, not from the alias booleans",
    },
    {
        "id": "T5.5-XS-03",
        "surface": "candidate_transaction.py:94-122 _LEGACY_STATE_ADAPTER + classify_legacy_migration_v1 re-export + _frag_chat.py:205-387 v1 aggregate readers + session V1 TurnState readers",
        "kind": "legacy state migration classifier/readers (V1/V2)",
        "owner": "S74",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "_artifact_store.load_candidate_transaction_with_migration :150-161, "
            "_turn_state_machine :229-245, _frag_chat rehydrate; registry owns classifier "
            "(projection_registry_v1:1112)"
        ),
        "compat_test": ["tests/test_comfy_nodes_agent_transaction_storage.py"],
        "removal_condition": "S74a removes V1 readers when every supported persisted session is migrated or aged out (fixtures regenerated)",
        "authority_note": "classification forces applyable=False/canvas=False/queue=False on legacy aggregates — strictly removes authority",
    },
    {
        "id": "T5.5-XS-04",
        "surface": "web/prepared_authority_v1.js migrateLegacyCandidateAuthorityV0Legacy + agent_apply_flow.js:1210 legacy_candidate_read_only + scoped_session_storage.js:82-88 one-shot migration + agent_lifecycle_commit.js legacyChanges projection + journal_durable_v1.js LEGACY_UNDO_CACHE_ENTRY_V1",
        "kind": "browser migration adapters (persisted/deployed compatibility)",
        "owner": "S74",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "frozen by tests/browser/legacy_authority_migration.test.mjs (valid v0_legacy migrates, "
            "unknown fail closed) and tests/browser/agent_lifecycle_commit.test.mjs "
            "(normalizeCommitFieldChangesFromSubmit incl. legacyChanges)"
        ),
        "compat_test": [
            "tests/browser/legacy_authority_migration.test.mjs",
            "tests/browser/agent_lifecycle_commit.test.mjs",
        ],
        "removal_condition": "S74c deletes each adapter when no persisted localStorage/journal/session rehydrate carries the legacy shape (per-file triggers in architecture ledger)",
        "authority_note": "migration is one-way digest-preserving into candidate_authority_v1; Apply of aggregate-free candidates is blocked read-only — adapters cannot grant authority",
    },
    {
        "id": "T5.5-XS-05",
        "surface": "porting/edit/ops.py:15,767,822-830 allow_legacy_list flat-V2 bridge + web/canonical_delta.js:468-481 allowLegacyList mirror",
        "kind": "delta wire-shape bridge (flat arrays → CanonicalDeltaEnvelope(legacy_bridge='flat_v2_ops'))",
        "owner": "S74",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "tests/test_agent_edit_artifact_replay.py:557-573 freezes allow_legacy_list; "
            "normalize_delta_v1 refuses legacy_bridge as authority ('diagnostics only')"
        ),
        "compat_test": ["tests/test_agent_edit_artifact_replay.py"],
        "removal_condition": "S74b retires the bridge after producers emit {schema_version, ops} everywhere (in-file deprecation L12-17)",
        "authority_note": "legacy_bridge envelopes are diagnostics-only: normalize_delta_v1 rejects them from authority paths; whole-candidate authority impossible",
    },
    {
        "id": "T5.5-XS-06",
        "surface": "ingest/normalize.py widget_{idx} materialization + node_kwargs._translate_widget LEGACY API JSON dual-key + widget_slots unused_widget_N→control_after_generate + lint positional aliases",
        "kind": "positional widget_N compatibility machinery (read/emit boundary)",
        "owner": "S74",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "schema-less offline ingest and LEGACY API JSON still carry positional vectors; "
            "editable_surface.is_positional_alias refuses minting widget_0/output_0 and "
            "_interpret rejects sealing widget_N ops as durable edits"
        ),
        "compat_test": ["tests/test_schema.py", "tests/test_ir_laws.py"],
        "removal_condition": (
            "S74b (with G53/G63 WIDGET_SCHEMA ownership) removes positional fallbacks once "
            "WIDGET_SCHEMA covers affected classes; new positional authority is forbidden by G1/T5.5 law"
        ),
        "authority_note": "positional names never become durable edit vocabulary: interpret seals widget_N ops out and compact_resolver forbids emitting them",
    },
    {
        "id": "T5.5-XS-07",
        "surface": "schema/types.py:17,27,33,40,48 slim InputSpec/OutputSpec/NodeSchema/SchemaIndexError/SchemaProvider duplicates vs provider.py rich copies",
        "kind": "duplicate type definitions across façades",
        "owner": "S73",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "package __init__ exports provider copies; types.py copies consumed by "
            "candidate_transaction SchemaSnapshotError path and tests/test_executor_lookup_tools.py:38"
        ),
        "compat_test": ["tests/test_api_surface.py", "tests/test_schema.py"],
        "removal_condition": "S73 consolidates duplicate aliases onto provider.py owners and re-points types.py imports",
        "authority_note": "snapshot anti-ambient machinery (ambient_lookup_forbidden) lives in types.py and stays regardless",
    },
    {
        "id": "T5.5-XS-08",
        "surface": "porting/emitter.py:99-111 forwards + emit/entrypoints.format_as_python compat wrapper + emit_kwargs lazy emitter re-imports",
        "kind": "wrapper-on-wrapper preserving emitter monkeypatch locations",
        "owner": "S75",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "tools/format_as_python delegation frozen by tests/test_porting_emitter.py:797-805 and "
            "tests/test_porting_edit_session.py:743-952"
        ),
        "compat_test": ["tests/test_porting_emitter.py"],
        "removal_condition": "S75 migrates monkeypatch sites to entrypoints, then deletes emitter forwards and the format_as_python compat wrapper",
        "authority_note": "emission only; emitted artifacts never authorize Apply",
    },
    {
        "id": "T5.5-XS-09",
        "surface": "commands/port/__init__.py:3-12 split-godfile monkeypatch façade",
        "kind": "monkeypatch location façade (CLI port handlers)",
        "owner": "S75",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": "tests/test_cli_port.py setattr on vibecomfy.commands.port.* providers",
        "compat_test": ["tests/test_cli_port.py"],
        "removal_condition": "S75 moves patches onto owning modules then deletes the façade",
        "authority_note": "CLI emission path only",
    },
    {
        "id": "T5.5-XS-10",
        "surface": "comfy_nodes/_server_compat.import_prompt_server:16 host-layout shim",
        "kind": "host dependency-hiding import shim (PromptServer lookup)",
        "owner": "S72",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": "comfy_nodes/__init__.py:223 and routes.py:2149 obtain PromptServer through it",
        "compat_test": ["tests/test_comfy_backend.py"],
        "removal_condition": "S72d replaces host/global lookups with an injected host port; delete when checkout-style ComfyUI layouts stop being probed",
        "authority_note": "locates the host server object; grants no edit authority",
    },
    {
        "id": "T5.5-XS-11",
        "surface": "templates._at:251 deprecated positional alias + finalize free-function:535 + registry/ready_template bind_* PendingDeprecation",
        "kind": "authoring-surface deprecated aliases",
        "owner": "S73",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "hand-authored templates use _at/finalize; templates.py + registry/ready.py call the "
            "bind_* helpers; frozen by tests/test_api_surface.py templates __all__"
        ),
        "compat_test": ["tests/test_api_surface.py", "tests/test_ready_template_helpers.py"],
        "removal_condition": "S73 eliminates duplicate aliases after hand-authored template corpus migrates to node()/wf.finalize",
        "authority_note": "authoring DSL sugar; no execution-spine semantics",
    },
    {
        "id": "T5.5-XS-12",
        "surface": "comfy_backend.read_vendored_commit:209 removed-submodule shim",
        "kind": "removed-vendored-source compatibility reader",
        "owner": "S71",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": "check_comfy_compatibility:257 consumes it; tests/test_comfy_backend.py freezes + monkeypatches",
        "compat_test": ["tests/test_comfy_backend.py"],
        "removal_condition": "S71 deletes once callers rely solely on VersionMatrix/live ComfyUI version probes",
        "authority_note": "version reporting only",
    },
    {
        "id": "T5.5-XS-13",
        "surface": "vibecomfy/nodes/*.py 19 generated thin-wrapper modules + generator tools/generate_node_shims.py + tests/test_node_shims.py",
        "kind": "generated-regenerated shims",
        "owner": "S77",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "G1–G5 spine paths do not import class wrappers (only ingest/sources.py uses "
            "nodes.index indexer); ready-template emission generates from them"
        ),
        "compat_test": ["tests/test_node_shims.py"],
        "removal_condition": "S77 cleans via generator (--check/--output-dir, determinism, .py/.pyi pairs); never hand-edited",
        "authority_note": "generated wrappers construct nodes through templates.node; no spine authority",
    },
    {
        "id": "T5.5-XS-14",
        "surface": "vibecomfy_roundtrip.js shell mirrors chatMessages/turns/turnDetailSnapshots (~3974-4882) + panel wrappers",
        "kind": "frontend shell delegates with explicit delete-after-selector comments",
        "owner": "S76",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": "top-level panel entry point loaded by ComfyUI; roundtrip_smoke/agent_status_poller tests",
        "compat_test": ["tests/browser/roundtrip_smoke.test.mjs"],
        "removal_condition": "S76 removes shell wrappers once canonical selectors/view models replace panel state fields",
        "authority_note": "render/lifecycle presentation only; Apply gating lives backend-side",
    },
    {
        "id": "T5.5-XS-15",
        "surface": "_compile/__init__.py star-re-export + porting/helper_resolve.py REMOVE-M4 re-exports + node_packs/patches/testing/registry lazy package inits",
        "kind": "lazy/star re-export façades outside the spine",
        "owner": "S73",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": "ingest/normalize.py, porting/convert.py, emit/ui.py consume compile internals; lazy packs avoid startup cycles (comments at each site)",
        "compat_test": ["tests/test_api_surface.py"],
        "removal_condition": "S73 groups re-exports by supported family and drops REMOVE-M4 helpers; eager conversion only with proven-safe headless imports",
        "authority_note": "name indirection only",
    },
    {
        "id": "T5.5-XS-16",
        "surface": "runtime.get_agent_status:1686-1705 + provider.get_agent_status:1970-1986 compatibility status wrappers + _load_arnold_runtime optional-runtime candidates:1172-1201",
        "kind": "status wrapper + optional-dep late loader",
        "owner": "S72",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "browser status poller (tests/browser/agent_status_poller.test.mjs and "
            "chat_rehydration/pipeline_mode_surface/payload_contracts) plus "
            "tests/test_comfy_nodes_agent_backend_spine.py consume the status shape; "
            "_load_arnold_runtime is the sole optional-runtime import gate at six "
            "provider.py call sites (:1337/:1404/:1706/:1843/:1915)"
        ),
    },
    {
        "id": "T5.5-XS-17",
        "surface": "session.py storage/journal/lock forwarding façades :863-1331 + star-imports :4568-4580 + T-047 load_candidate_transaction wrappers :4589-4601 + _frag_*/_artifact_store/_turn_state_machine late-bound host lookups (T-039/T-044/T-046)",
        "kind": "extracted-module reverse façade + late imports preserving session monkeypatch visibility",
        "owner": "S72",
        "disposition": "out_of_scope_structural_card",
        "consumer_evidence": (
            "tests/test_comfy_nodes_agent_backend_spine.py:10324+ patches session.write_state_atomic "
            "and _turn_state_machine MUST late-bind it; session surface frozen 23/31/23 by "
            "cleanup_surface_manifest"
        ),
        "compat_test": [
            "tests/test_cleanup_surface_manifest.py",
            "tests/test_comfy_nodes_agent_backend_spine.py",
        ],
        "removal_condition": "S72a session delegate inversion after B33–B35: extracted modules take typed ports, reverse lookups and star-imports delete",
        "authority_note": "forwarding reaches the same storage/journal implementations; accept/reject authority unchanged",
    },
)
DELETED_ROWS = [row for row in T55_DISPOSITION if row["disposition"] == "delete_now"]
RETAINED_ROWS = [row for row in T55_DISPOSITION if row["disposition"].startswith(("retain", "migrate", "collapse"))]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


# ── manifest integrity ────────────────────────────────────────────────────────


@pytest.mark.parametrize("row", T55_DISPOSITION, ids=lambda r: r["id"])
def test_row_has_complete_contract(row) -> None:
    assert OWNER_RE.match(row["owner"]), row["id"]
    assert row["disposition"] in DISPOSITIONS, row["id"]
    assert row["surface"], row["id"]
    assert row["kind"], row["id"]
    assert row["consumer_evidence"], row["id"]
    if row["owner"] == "T5.5":
        if row["disposition"] == "delete_now":
            assert row["compat_test"], row["id"]
        else:
            assert row["compat_test"], row["id"]
            assert row["removal_condition"], row["id"]
            assert row["authority_note"], row["id"]
    else:
        assert row["disposition"] == "out_of_scope_structural_card", row["id"]


def test_manifest_ids_are_unique() -> None:
    ids = [row["id"] for row in T55_DISPOSITION]
    assert len(ids) == len(set(ids))


def test_zero_unclassified_rows() -> None:
    unclassified = [
        row["id"]
        for row in T55_DISPOSITION
        if not OWNER_RE.match(row["owner"]) or row["disposition"] not in DISPOSITIONS
    ]
    assert unclassified == []


def test_every_structural_card_owner_is_exact() -> None:
    cards = {row["owner"] for row in T55_DISPOSITION if row["owner"] != "T5.5"}
    assert cards <= {"S71", "S72", "S73", "S74", "S75", "S76", "S77"}


# ── deleted rows stay deleted ─────────────────────────────────────────────────


@pytest.mark.parametrize("row", DELETED_ROWS, ids=lambda r: r["id"])
def test_deleted_symbols_absent(row) -> None:
    src_path, _, symbols = row["surface"].partition("#")
    text = _source(src_path.strip())
    for symbol in symbols.split(","):
        assert symbol.strip() not in text, f"{symbol.strip()} resurrected in {src_path}"


def test_intent_judge_legacy_walker_stub_removed_but_canonical_verifier_kept() -> None:
    """Dirty-file resolution §2a: legacy stub removed; Law-3 verifier remains."""
    text = _source("tests/live_agentic_harness/intent_judge.py")
    assert "_verify_delta_replay_legacy_removed" not in text
    assert "def _verify_delta_replay(" in text
    assert "T5.5-LS-01" in text  # inline retained-shim ledger marker survives


def test_cleanup_surface_count_resolution_is_440() -> None:
    """S70 census question resolved: frozen agent-edit surface is 440 names."""
    import json

    manifest = json.loads(
        (ROOT / "tests/fixtures/agent_edit/cleanup_surface_manifest.json").read_text(encoding="utf-8")
    )
    assert len(manifest["edit"]["__all__"]) == 440


def test_no_stale_472_name_comment_in_production_tree() -> None:
    """Dirty-file resolution §2b companion: stale count comment corrected."""
    offender = ROOT / "vibecomfy/comfy_nodes/agent/_frag_transform_stages.py"
    assert "472-name" not in offender.read_text(encoding="utf-8")


# ── retained rows: surface + compatibility tests exist ────────────────────────


@pytest.mark.parametrize("row", RETAINED_ROWS, ids=lambda r: r["id"])
def test_retained_row_compat_tests_exist(row) -> None:
    for rel in row["compat_test"]:
        assert (ROOT / rel).exists(), f"{row['id']}: missing compat test {rel}"


@pytest.mark.parametrize(
    ("row_id", "src", "marker"),
    [
        (
            "T5.5-RS-01",
            "vibecomfy/executor/core.py",
            "# Compatibility forwarding names: existing integrations and tests patch these",
        ),
        ("T5.5-RS-02", "vibecomfy/executor/contracts.py", "_ORCHESTRATION_MODE_ALIASES"),
        ("T5.5-RS-03", "tests/live_agentic_harness/intent_judge.py", "seed\": \"canonical_diff"),
        ("T5.5-RS-04", "vibecomfy/comfy_nodes/agent/routes.py", "_maybe_write_executor_only_durable_turn"),
        ("T5.5-RS-05", "vibecomfy/comfy_nodes/agent/_frag_session_bundle.py", "_warn_legacy_contract_once"),
        ("T5.5-RS-06", "vibecomfy/comfy_nodes/agent/provider.py", '"legacy_deepseek_fallback_enabled": False'),
        ("T5.5-RS-07", "vibecomfy/porting/edit/__init__.py", "def __getattr__"),
        (
            "T5.5-RS-08",
            "vibecomfy/comfy_nodes/agent/edit_batch_repl.py",
            "EditBatchReplDeps",
        ),
        (
            "T5.5-RS-09",
            "vibecomfy/porting/edit/checkpoint.py",
            "_ops_from_durable_payload",
        ),
        ("T5.5-RS-10", "vibecomfy/porting/edit/constants.py", "decode_channel_side_payload"),
    ],
)
def test_retained_surface_marker_present(row_id: str, src: str, marker: str) -> None:
    assert marker in _source(src), f"{row_id}: surface marker missing in {src}"


def test_accept_to_finalize_bridge_removal_condition_still_encoded() -> None:
    """Out-of-scope S74a row: bridge metadata still carries its deletion trigger."""
    text = _source("vibecomfy/comfy_nodes/agent/contracts.py")
    assert "ACCEPT_TO_FINALIZE_BRIDGE" in text
    assert "accept_bridge_v2_count" in text
    assert "deletion_condition" in text
