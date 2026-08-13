# Area 5 — Group member-ID reconciliation
- emit_ui_json (ui.py:2666-2681): caller_groups = list(groups) if given else deepcopy(wf.groups); emitted_groups = caller_groups + engine_groups. NO member-id remapping; emitted node id = id_remap[node_id] (LiteGraph ints).
- layout_store.store_from_ui_json REKEYS group member int LiteGraph ids → UIDs on ingest (:429-439; test confirms [1,2]->['uid-1','uid-2']).
- wf.groups members are RAW SOURCE ids (LiteGraph ints from source UI; _vibe_groups deep-copies verbatim, normalize.py:404-415). Coherence today depends entirely on callers supplying groups= in the target ID space.
- 7 groups= call sites beyond _export.py: test_porting_normalize_ingest.py:759; test_porting_ui_emitter.py:2167,2720; test_ui_layout.py:1558; check_b02:267,298 (via _emit wrapper :230-235). Production caller: only commands/port/_export.py:460-476 (groups=sidecar_groups from store.get('groups')).
- build_subgraph_groups (layout/groups.py:60-114) produces engine groups WITHOUT 'nodes' member list (title/bounding/color only; matches by properties.vibecomfy_uid).
- Dropping the groups= kwarg (Batch D+E) REQUIRES a member-id remap: map wf.groups member ids (raw source ints or UIDs) → emitted LiteGraph int ids inside emit, else port-export loses group membership coherence.
