# Law 5 — leftover structural-read allow-list

Law 5: after ingest, `VibeWorkflow` is the sole graph authority. The two
named doors (`vibecomfy/ingest/normalize.py`, `vibecomfy/porting/emit/ui.py`)
may inspect and mutate LiteGraph / envelope `nodes`, `links`, and
`widgets_values`. Four pass-through adapters may serialize whole payloads
but may not inspect structure.

This note is the B1 amendment: the checker reports remaining **real**
LiteGraph / envelope walkers instead of hiding them in a 56-file
"inventory" that pretended to be zero.

## What is not a leftover walker

The scanner no longer flags key-name collisions that are not graph
structure:

- IR compile dicts (`prepared["nodes"]` in emit_prepare / emit_ready)
- CLI / report census fields (`data["nodes"]` in analyze / sources)
- Layout-section node-id lists and Comfy websocket event fields
  (`data.get("nodes")`)

Product-path inspection (`inspect_graph`) now enters through the named
ingest doors and projects from IR via `inspect_workflow`.
`ingest/summarize.py` does the same for corpus dicts.

## What remains

`STRUCTURAL_READ_ALLOWLIST` in `scripts/check_ir_boundary.py` is the
exact leftover set. Each file has a one-line justification there.

Those files still **read** LiteGraph or envelope keys. They are **not**
graph mutation authority: they do not write `nodes` / `links` /
`widgets_values`, they do not replace the doors, and they are not
`working_ui`. Layout, reorganise, widget-shape, and most agent-edit
canvas walkers stay here until a later pass routes them through IR.

The KPI is exact equality, not `<=`:

```text
structural_read_paths() == STRUCTURAL_READ_ALLOWLIST
ci_violations() == ()
```

Empty allow-list is the target. Additions require editing the checker
and this note.
