# Provenance-driven splice: the right narrow bet, not general additive editing

## Verdict

**Build it, but narrow the claim and the first implementation.** A provenance-driven splice is the best next construction bet for an explicit “restore what I removed” request with trustworthy, identity-preserving history. It is materially easier and more reliable than asking an LLM to author positional widgets and links over several turns. It is **not** yet a general solution for quality multi-node additive edits, and the proposed `peer_class + socket` fallback makes the scope look safer than it is.

The winning v0 is an **exact-history restore splice**: select one source node demonstrably absent from the current graph, require its original peers to survive with stable identities and open original slots, replay named values and exact source endpoints through the existing edit transaction, and fail closed otherwise. That is a useful, durable subset of m4. Inferring peers by class/socket when identities do not survive is m2 role binding and should be a later capability.

## 1. Construction is the right bet, conditionally

The mechanical advantage is real. `_resolve_add_node` already canonicalizes aliases, rejects socket fields as literals, and validates values against a resolved schema (`vibecomfy/porting/edit/apply_resolve_add.py:40-168`). `_apply_add_node` then materializes the node, orders inputs by schema, creates incoming links, and places it deterministically (`vibecomfy/porting/edit/apply_mutate.py:219-305`). This removes precisely the LLM failure mode seen in cases 05/08: invented positional vectors, provisional socket order, and half-built branches.

But “the provenance source contains the exact removed node” is too strong. In case 05, current provenance recomputation finds three named historical values—`lora`, `strength`, and `low_mem_load`—while the campaign golden stores a compact one-element widget vector (`out/demo-candidate-factory/20260727-provenance-fixed/cases/e37d74df126b/source/golden.ui.json:634-667`). The current constructor expands schema defaults before emission (`vibecomfy/porting/emit/ui.py:1263-1323`), while the oracle requires equal positional-widget length and values (`vibecomfy/demo_factory/predicates.py:91-105`). With A3 reverted, a semantically correct splice can still miss the restoration oracle. The known live enum also does not contain the historical LoRA filename, and edit validation treats an enum miss as an error (`vibecomfy/porting/edit/apply_values.py:22-35`). Therefore case 05 is not a guaranteed immediate green: compact-shape semantics and stale asset-enum policy remain prerequisites or explicit fail-closed outcomes.

So this is the right construction bet, not a magic quality bet. It determinizes **how** to build after source-instance and placement decisions are proven.

## 2. It sidesteps the frozen-research boundary

The splice does not need to mutate `research.json`. Research completes before implementation (`vibecomfy/executor/core.py:1962-2025`), but `_run_implement` forwards provenance slices into the agent-edit payload (`vibecomfy/executor/core.py:1192-1201`) and `handle_agent_edit` hydrates them directly into `state.executor_precedent_slices` (`vibecomfy/comfy_nodes/agent/edit_entrypoint.py:179-187`). A candidate constructed during implementation returns independently through `state.ui_payload`; the executor extracts the returned graph/candidate at `vibecomfy/executor/core.py:1376-1399`.

The clean injection point is inside `_stage_agent_batch_repl`, immediately after schema hydration and `EditSession` creation (`vibecomfy/comfy_nodes/agent/edit_batch_loop_intro.py:669-673`), before the first provider turn. There is no existing first-class “accept candidate graph” hook, however. Directly assigning a graph would bypass landed-operation evidence, batch exit state, response eligibility, and queue validation; the orchestration only queue-validates changed, landed candidates in the appropriate exit modes (`vibecomfy/comfy_nodes/agent/edit_orchestration.py:132-173`).

For v0, compile the splice into a synthetic initial batch and run `session.apply_batch`. That path already snapshots and rolls back a failed batch atomically (`vibecomfy/porting/edit/_parse_execute.py:50-135`) and binds a newly minted node to a symbolic graph name (`:254-287`). A pure typed tuple needs additional handle semantics because `AddNodeOp.inputs` covers incoming links, while outgoing `UpsertLinkOp`s must reference the newly minted UID; `_apply_add_node` currently mints it internally (`apply_mutate.py:223-250`). This is real work, but it is an implementation-boundary issue—not the frozen-research wall that blocked A2.

## 3. Peer rebinding: promising examples, insufficient contract

On the two concrete cases, the numbers are:

- **Class alone:** unambiguous for 1 of 2 deleted nodes.
- **Class plus an open, type-compatible peer input:** unambiguous for 2 of 2.
- **General claim:** unsupported by this sample.

Case 05 has one surviving `WanVideoModelLoader`, and its `lora` input is open (`.../e37d74df126b/broken/broken.ui.json:205-245`). Case 01 has two `SamplerCustomAdvanced` peers: node 4829’s `sigmas` input is occupied (`.../760468474fe5/broken/broken.ui.json:925-988`), while node 4971’s is open (`:1456-1519`). Vacancy makes the endpoint unique.

However, the source has two `ManualSigmas` nodes with different schedules and identical edge signatures. `collect_type_instances` deliberately returns all same-class instances (`vibecomfy/executor/provenance.py:51-88`). Worse, `_incident_edges` records the **removed node’s** socket, not the peer’s socket: outgoing edges call `_output_socket_name(node, origin_slot)`, incoming edges call `_input_socket_name(node, target_slot)`, and peer ID, peer slot, and link type are discarded (`vibecomfy/executor/provenance.py:191-246`). Thus case 01 is not uniquely solvable from the stated slice key; it becomes unique only after observing that source node 4985 is absent and the corresponding surviving consumer slot is vacant.

Enrich the edge contract with `peer_node_id`, both endpoint slot indexes/names, link type, and scope. The MVP should require stable peer IDs. Class/socket/vacancy matching is a later fallback; repeated branches or multiple open compatible inputs immediately reintroduce unavoidable m2 role inference.

One verification caveat: the saved campaign `research.json` files still show empty edge arrays (case 05 at `.../e37d74df126b/attempts/001/research.json:2427`; case 01 at `.../760468474fe5/attempts/001/research.json:10206`). The counts above come from recomputing with the current post-#3 loader. Regenerate the artifacts before calling edge transport end-to-end verified.

## 4. Estimate and fastest de-risking cut

The proposed **3–5 days** is credible for a happy-path prototype. It is not enough for a regression-safe candidate lane. My estimate is **7–10 working days** for the strict MVP, approximately the upper end of the proposed 1–1.5 weeks:

1. enrich and test source-instance/edge fidelity, including regeneration of the stale saved campaign research artifacts: 1–2 days;
2. exact missing-node selection and fail-closed stable-peer eligibility: 1–2 days;
3. synthetic-batch construction plus candidate/batch bookkeeping and normal validation: 2–3 days;
4. compact-widget/asset-enum decisions, adversarial ambiguity tests, and campaign regressions: 2–3 days.

Allow **2–3 weeks** if v0 includes class/socket rebinding without stable IDs, multiple incident edges, bypass removal, or a native typed handle API. Those additions are where the scoped bet starts becoming m2+m4.

The fastest proof is cases 05 and 01 plus negative twins: duplicate eligible peers, occupied target slot, stale breadcrumb, two absent same-class source instances, enum-missing historical asset, and a splice whose final branch fails queue/postcondition validation. Success means deterministic construction or deterministic refusal—not merely two green campaign cases.

## 5. Anti-gaming

This stays on the right side of `PLAN.md` §6 **only as an explicitly labelled provenance-restore capability**. Historical source values and edges are admissible evidence when the user asked to restore prior behavior; the constructor must not inspect the campaign’s `source/golden.ui.json`, oracle locus, or expected widget length, and must not hard-code classes, filenames, or schedules (`docs/failure-analysis/v2/PLAN.md:67-75`).

The slip risk is metric laundering: automatically using a breadcrumb on every additive request, then reporting exact-restore wins as general additive-edit quality. Require explicit restore intent, a trustworthy graph-linked source lineage (preferably hashed), schema/type validation, asset-availability diagnostics, and ambiguity refusal. Keep a separate no-provenance novel-addition suite. Also treat defaults and compact omission uniformly; changing serialization to match the hidden witness would cross the line.

## 6. Better bet and sequencing

Do **not** curate the suite toward case-01-shaped targets, and do not make another research-binding fix the prerequisite. The higher-leverage sequence is:

1. strengthen the provenance edge/source-instance contract;
2. ship the strict exact-history restore splice at the editor injection point;
3. validate the resulting candidate through existing transaction, queue, and intent gates;
4. add class/socket/vacancy fallback only with an explicit ambiguity score;
5. retain full m2 role binding plus native typed handles/atomic multi-link construction as general m4.

This scoped lane should recover case 01-shaped and case 05-shaped deletions reliably when assets and serialization agree. It will not solve case 09-like stage selection or case 08-like active-path construction by itself. The **single biggest risk** is silently choosing the wrong source instance or peer in a repeated branch: the output can be structurally valid, publishable, and aesthetically worse. Fail-open matching kills the bet; fail-closed stable-identity restoration makes it worthwhile.
