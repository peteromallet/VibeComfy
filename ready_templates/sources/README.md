# Ready Template Build Inputs

Hivemind is the canonical public workflow store. This directory contains only
the pinned source snapshots needed to build and verify the curated Python
adapters in `ready_templates/`. A snapshot is generated from a pinned
Hivemind or upstream revision; it is not an independently maintained workflow
catalogue and must not be used for bulk discovery.

For ordinary community work, search Hivemind and pull the selected revision
into the local `workflows/` ingestion store. Add a snapshot here only as part
of an explicit ready-template promotion.

## Layout

| Path | Purpose |
|---|---|
| `official/` | Generated snapshots of pinned official sources used by adapters. |
| `custom_nodes/` | Generated snapshots of pinned custom-node/community sources used by adapters. |
| `input/` | Small media fixtures referenced by adapter build/verification runs. Keep paths stable because pinned source JSON may refer to them directly. |
| `manifests/` | Corpus metadata such as coverage tiers and ready-template regeneration provenance. |

## Path Contracts

Workflow IDs and paths are index-backed. Moving or renaming a source JSON file
can change its indexed path and break coverage manifests, regeneration records,
tests, or docs that point at the old location.

Safe changes:

- add new JSON workflows under the appropriate existing subtree
- add documentation or manifests that do not change existing paths
- update `input/FIXTURES.md` when fixture media changes

Coordinated changes:

- moving JSON workflows between directories
- renaming JSON workflow files
- moving `manifests/` or `input/`

After source changes, refresh and check the generated indexes:

```bash
python -m vibecomfy.cli sources sync
python -m vibecomfy.cli workflows list --json
python -m vibecomfy.cli analyze corpus --json
```
