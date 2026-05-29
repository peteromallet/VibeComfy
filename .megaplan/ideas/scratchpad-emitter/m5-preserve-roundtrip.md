# M5 — Position/furniture-faithful preserve (round-trip)  [premium tier — the headline]

## Outcome
The headline deliverable: re-emitting a workflow **keeps the node positions and editor furniture the
user arranged**, places only genuinely-new nodes (via M4's constrained engine, in sensible spots near
their wired neighbors), and degrades gracefully to clean fresh layout when there's nothing to preserve.
This is the feature the whole epic exists for. Losing a hand-arranged position is a **gate failure**,
not accepted best-effort.

Built on M2's durable uid + uid-keyed layout store, M3's furniture-emitting wired CLI, and M4's
constrained placement. Because identity is now a uid carried through the round-trip (not a recomputed
hash), preserve is correct **by construction** for any node that has been through VibeComfy once; the
structural hash is only a one-time bridge for legacy/never-seen nodes.

## The preserve mechanism (locked design)
- **Layout memory is M2's uid-keyed store** (sidecar by default; `--from <prev.json>` overrides; prior
  emitted JSON auto-discovered via breadcrumb as a fallback source). Re-emit = merge:
  `Python (structure) + store (layout/furniture) -> new UI JSON`.
- **Identity match, in order:** (1) `uid` exact (primary — extrinsic and assigned-once, carried in
  `properties["vibecomfy_uid"]` (survives editor saves, K1) and the `.py` `uid=` kwarg. Because it is
  NOT content-derived, a uid-matched node **keeps its position across widget edits and rewiring** — the
  Phase-B fatal-flaw fix; this is the common case and it is exact, not best-effort); (2) **legacy
  structural-hash bridge** ONLY for nodes that carry no uid at all (pre-VibeComfy JSON hand-edited
  outside ComfyUI) — hash of class_type + sorted incoming AND outgoing edge signature + topological
  position + widget values + public-input binding — and on a successful bridge match, **mint + persist a
  uid** so the next round-trip is exact; (3) on a hash that maps multiple current nodes to one prior
  (true duplicates — twin RandomNoise, cloned subgraphs), do a **stable assignment that minimizes
  position drift** (bipartite match on prior pos) rather than scatter; never auto-move a node with any
  prior-position candidate; (4) only if all fail -> new node.
- **Matched nodes keep prior `pos`/`size`/`mode`/`flags`/`color`/full `properties` and group membership**
  verbatim. New nodes -> M4 constrained placement anchored to a matched wired neighbor. Deleted nodes
  vanish. User-drawn groups are preserved as-is; engine-generated groups only fill ungrouped regions.
- **[Phase-C] Virtual wires (Get/SetNode/Reroute) preserve like any furniture** — matched by uid from
  M2's capture, restored to their prior positions. If a Python structural rewire orphaned a captured
  route (its endpoints changed), the wire degrades to a direct connection and is NAMED in the change
  report — never silently dropped.
- **Preserve is the DEFAULT** when a store/prior exists; `--fresh` forces M4 clean layout. With no
  store and no prior, fresh is the only option (the no-metadata path — must work).
- **Latest editor layout wins:** since M2 refreshes the store from each ingested editor JSON, the user's
  most recent drags are what preserve restores.

## [Sense-check 2026-05-30] REQUIRED before merge — semantic gate + refusal-spine + mechanism stance

A 3-model review (Codex + Claude + DeepSeek) of this epic vs the hardened strategy
(`docs/roadmap_agentic_comfyui.md` §0/§11, refined the same day) found that M5 preserves *furniture*
but its acceptance gate is *geometric only* — which can score green while the codec silently re-mangles
the structure of an UNTOUCHED node. These additions close that, and are **gate-blocking, not polish.**

**Mechanism stance (endorsed, do not relitigate).** M5's preserve is **"regenerate structure from the IR
through M3's one schema-codec + restore furniture from the uid-keyed store."** This is the chosen
non-fragility approach — NOT byte-for-byte replay. It is correct *because* the IR is the source of truth
(regeneration stays internally consistent even when a node's upstream changed, which verbatim replay gets
wrong — stale links) **provided the two gates below hold.** Roadmap §11 mechanism #1 (verbatim replay) is
demoted to an **optional fallback** for node classes the codec can't round-trip 100%; it is OUT of M5
anti-scope unless a specific class forces it (it would require reopening M2's slim-`_ui` capture).

1. **SEMANTIC acceptance gate on the preserved output (REQUIRED — not only the geometric layout-diff
   oracle).** The geometric oracle (Phase-D, `max Δpos==0 ∧ Δsize==0`) proves *furniture* fidelity; it is
   structurally blind to *semantic* drift on regenerated nodes. M5 must ALSO gate semantically: for the
   preserve/round-trip path, assert **`convert_ui_to_api(original) == convert_ui_to_api(emit(ingest(original)))`**
   on uid-matched (untouched) nodes, per-family. Reuse the existing M3 gate of record —
   `test_layer3_corpus_wide_convert_ui_to_api_gate` (`tests/test_porting_ui_emitter.py:967`,
   `canonical_equal` vs ComfyUI's own converter) — extended to run over the *preserved re-emit*, not just
   fresh emit. Both gates green = done; geometric-only = NOT done.
2. **Runtime corruption-detector / refusal-spine (REQUIRED — distinct from the change report).** The change
   summary (preserved/new/removed) *names* changes; it does not *prevent* unintended ones. Add the
   refusal-spine from roadmap §3 / §0 Step 5: before an APPLIED re-emit, diff `convert_ui_to_api(candidate)`
   vs `convert_ui_to_api(original)` on untouched regions and **abort to a typed REFUSED** on any change
   outside the intended delta (never ship it). Proven in `scripts/roundtrip_fidelity_spike.py` (T4:
   ALLOWs a clean edit, REFUSEs a control-slot-drop corruption). If M5 is too full, this may land in M6,
   but it must have a NAMED owner — today no milestone owns it.
   - **It consumes the §0 Step 0 signal:** a **system-computed, uid-keyed touched/untouched delta**
     (diff each node's current IR projection vs its ingest snapshot), **never agent-declared** (an
     over-broad declaration turns the detector into a no-op). M5 already snapshots identity on ingest;
     extend it to a field-level delta. This signal does not exist in the epic yet — assign it here.

## Polish (within this milestone, after preserve is correct)
- Role-colored titled group boxes; consistent palette across all emitted workflows.
- Optional deterministic crossing-reduction tie-break (positive-before-negative role precedence).

## Locked decisions (do not relitigate)
- uid first, hash bridge second (mint-on-bridge), stable-assignment on duplicates, new last.
- Matched nodes keep pos/size/mode/flags/color/group. Preserve is default; `--fresh` overrides.
- Preservation faithfulness for uid-matched nodes is a CONTRACT, not best-effort. Best-effort applies
  only to the legacy hash bridge, and any node it can't confidently match is named in the report.

## Subgraph inner-node preserve (K5)
- Inner subgraph nodes get their own identity too, but **NOT keyed on the subgraph UUID** — K5 confirmed
  ComfyUI regenerates the subgraph UUID on every editor save. Key inner-node preserve on
  **`(subgraph name + content-hash) : inner-source-id`**, stamping `properties.vibecomfy_uid` on inner
  nodes as M1 does at top level. Clone ambiguity is a non-issue: each clone is a distinct definition with
  exactly one instance (verified across the music-video monster's 10 defs).
- Treat M2's carried `metadata["definitions"]` as the authoritative inner-layout store; do not rebuild
  inner positions from the flattened IR (inner ids are renumbered at ingest).

## Open questions (resolve during planning)
- Topological-signature definition for the legacy hash (deterministic + stable under edits elsewhere).
- Conflict policy when both a store entry and a `--from` JSON disagree (default: store wins; `--from`
  is an explicit override of the store).
- Whether bypass/`mode` participates in the preserve merge as execution state (M3 owns the policy; M5
  must restore the user's bypass/mute state on matched nodes).

## [Phase-D] Additions (see WAY-THROUGH-2026-05-29.md #1/#9/#10/#11)
- **Scoped-path preserve matching:** match on the full `scope_path:local_uid` (M2); inner subgraph nodes
  matched within their definition scope, restored from `metadata["definitions"]`, never the flattened IR.
- **Layout-diff oracle = the falsifiable "faithful" gate (#11).** Build a Tier-0 pure function
  `layout_vector(ui_json) -> {uid:(pos,size,group,mode)}` + `layout_drift(before,after)`; the M5 acceptance
  gate is **`max Δpos == 0 ∧ Δsize == 0` over uid-matched nodes**. Land it RED on a synthetic "+8px on one
  matched node" fixture to prove falsifiability — the self-referential parity gate is geometry-blind and
  structurally cannot express this.
- **emit->re-emit ×N=50 convergence test** (hypothesis), random structural edit each cycle: bit-identical
  pos on uid-matched nodes + the change-report names ONLY edited nodes (cry-wolf guard).
- **Identity unification:** `vibecomfy_uid` is THE authoritative match/store/`uid=` key; **demote
  `ir_node_id` to execution-internal — stop writing it to `properties` (`ui_emitter.py:631`)** (a stale
  re-ingested value is exactly how positions get stolen); `vibecomfy_id` stays display-only. All under
  `properties["vibecomfy"]`.
- **Bypass firewall lands ATOMICALLY here:** compile drop(mode 2)/rewire(mode 4) + a `compile_invariance`
  contract test (byte-identical with/without uid+furniture) + a full `regenerate_snapshots.py --write`
  re-baseline + a real-ComfyUI bypass-equivalence test, all in one PR. Invariant: *byte-identical for
  graphs with no bypassed/muted nodes; matches ComfyUI drop/rewire otherwise.*

## Constraints
- Offline/deterministic. Wiring untouched: M3 object_info + isomorphism gates green after merge;
  `properties`/furniture ignored by `compile("api")` (verify).

## Done criteria
- **Position-fidelity oracle:** emit -> perturb positions in the store -> add a node in Python -> re-emit
  (default) -> every uid-matched node keeps its EXACT perturbed pos/size; only the new node is freshly
  placed (no overlap). uid-matched fidelity is asserted exact, not approximate.
- **Editor round-trip:** hand-edit positions in raw litegraph JSON -> `port convert` -> `port export
  --to ui` -> positions + groups + notes + bypass state preserved pixel-for-pixel for unchanged nodes.
- **Edit-invariance (the Phase-B fatal-flaw guard):** change a node's widget value AND rewire one of its
  edges in Python -> re-emit -> that node KEEPS its exact prior position (uid is extrinsic, not content-
  derived). A node insertion does NOT move the positions of its neighbors.
- **JSON-only collaboration:** user B receives ONLY the emitted `.json` (no sidecar, no `.py`) -> opens it
  -> re-exports -> positions preserved (the `.json` is self-describing; sidecar is not required).
- **[Phase-C] AI-agent edit-safety:** programmatically add/delete/rewire N nodes (so `_next_node_id`
  reuses integer ids) -> emit -> NO new node inherits a deleted node's position; existing nodes keep
  theirs. The agent analogue of edit-invariance; guards the worst-served persona.
- **[Phase-C] Virtual-wire round-trip:** a graph with Get/SetNode/Reroute, hand-arranged, round-trips
  with those nodes restored in place (structurally-unchanged case = exact; rewired case = degraded +
  reported).
- **Duplicate safety:** twin RandomNoise / cloned `samplers`+`samplers_8b36a85a` re-emit without swapping
  or both claiming one prior position.
- **Legacy resilience:** a pre-uid file round-trips via the hash bridge, gets uids minted, and the
  SECOND round-trip is exact; anything unmatched is named honestly in the report.
- **`--fresh`** reproduces M4's deterministic clean layout; no-metadata input still produces clean layout.
- Re-emit reports a change summary (preserved / new-auto-placed / removed, named).
- **[Sense-check] Semantic round-trip gate (REQUIRED):** on the preserve path, `convert_ui_to_api(original)
  == convert_ui_to_api(re-emit)` (canonical_equal) on uid-matched nodes, per-family — the M3 gate of
  record extended over the preserved output. Geometric layout-diff alone does NOT satisfy this.
- **[Sense-check] Refusal, not just report (REQUIRED, may defer owner to M6):** a synthetic unintended
  SEMANTIC change on an untouched node (e.g. a dropped `control_after_generate` slot → widget shift) is
  **REFUSED** before ship — proving the spine aborts, not merely names it. Land it RED first.

## Touchpoints
- `vibecomfy/porting/ui_emitter.py` (merge path), `vibecomfy/porting/layout/reconcile.py` (new — match +
  3-way merge), `vibecomfy/porting/layout_store.py` (read), `vibecomfy/commands/port.py` (`--fresh`,
  `--from`, preserve-by-default), `tests/test_position_fidelity.py` + preserve/duplicate/legacy tests.

## Anti-scope
- No new ingest capture (M2). No new layout primitives beyond reconcile (M4 owns placement).
- No productionization/docs (M6). Do not promise lossless preservation for the legacy hash bridge.
- No byte-for-byte verbatim node replay (roadmap §11 #1) — it's a demoted fallback needing M2 capture
  changes; M5 regenerates structure from IR and gates it semantically instead (see the Sense-check section).
