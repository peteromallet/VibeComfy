"""Sidecar layout store. M2 envelope (Step 5a) supersedes the frozen M1.5 schema.

The M1.5 sidecar was a flat ``{"layout_version": 1, "nodes": {uid: {pos, size}}}``.
M2 replaces it with a versioned envelope that round-trips the full editor state
needed to reconstruct a workflow losslessly:

    {
      "store_version": 2,
      "vibecomfy_version": "<str>",
      "schema_hash": "<blake2b of the entry/section key shape>",
      "entries": {                       # per-uid node geometry + verbatim blob
        "<uid>": {
          "pos": [x, y],                 # canonicalized via snap_pos (T3)
          "size": [w, h],
          "flags": {...},
          "color": "<str|null>",
          "bgcolor": "<str|null>",
          "properties": {...}            # verbatim
        }
      },
      "groups": [...],                   # graph-level
      "extra": {"ds": {...}},            # canvas drag/scale state under extra.ds
      "lastRerouteId": <int|null>,
      "definitions": {...},              # subgraph inner-node ids/pos
      "virtual_wires": {                 # Get/Set/Reroute virtual edges
        "<uid>": {"type": <str>, "channel": <str>, "endpoints": [...]}
      }
    }

The sidecar lives alongside the converted .py file with the suffix
``.layout.json`` (e.g. ``flat.py`` -> ``flat.layout.json``).

Graceful-absence behaviors from M1.5 are preserved: ``write_layout`` skips nodes
with an empty uid or with no captured ``pos``; ``read_layout`` returns ``{}`` for
an absent or unreadable sidecar.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from vibecomfy.porting.canonical_coords import snap_pos, snap_size
from vibecomfy.porting.scope import compose_scope_path, sg_key
from vibecomfy.porting.uid import make_uid, mint_local_uid

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

STORE_VERSION = 2

# Stable description of the envelope shape; hashed into ``schema_hash`` so a
# reader can detect a schema drift independent of the version integer.
_ENTRY_KEYS = ("pos", "size", "flags", "color", "bgcolor", "properties")
_SECTION_KEYS = (
    "entries",
    "groups",
    "extra",
    "lastRerouteId",
    "definitions",
    "virtual_wires",
)


def _schema_hash() -> str:
    payload = json.dumps(
        {"entry_keys": list(_ENTRY_KEYS), "section_keys": list(_SECTION_KEYS)},
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.blake2b(payload, digest_size=8).hexdigest()


def sidecar_path_for(py_path: Path) -> Path:
    """Return the sidecar layout path for a given .py file path.

    flat.py -> flat.layout.json
    """
    return py_path.with_suffix(".layout.json")


def _vibecomfy_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("vibecomfy")
        except PackageNotFoundError:
            return "0"
    except Exception:
        return "0"


def _build_entry(ui: dict) -> dict[str, Any]:
    """Build a per-uid entry from a node's captured ``_ui`` blob.

    ``pos`` is canonicalized (T3) so repeated round-trips are idempotent and
    bit-stable. ``size`` is canonicalized when present.
    """
    entry: dict[str, Any] = {"pos": snap_pos(ui["pos"])}
    size = ui.get("size")
    entry["size"] = snap_size(size) if size is not None else None
    entry["flags"] = ui.get("flags")
    entry["color"] = ui.get("color")
    entry["bgcolor"] = ui.get("bgcolor")
    properties = ui.get("properties")
    entry["properties"] = properties if isinstance(properties, dict) else {}
    return entry


def _iter_subgraph_defs(definitions: Any) -> Iterable[dict]:
    """Yield individual subgraph definition dicts from a ``definitions`` blob.

    Tolerant of the shapes ComfyUI emits: ``{"subgraphs": [...]}``, a plain
    ``{uuid: def}`` mapping, a single def dict (has its own ``nodes``), or a
    bare list of defs.
    """
    if isinstance(definitions, dict):
        subgraphs = definitions.get("subgraphs")
        if isinstance(subgraphs, list):
            for sg in subgraphs:
                if isinstance(sg, dict):
                    yield sg
            return
        if isinstance(definitions.get("nodes"), list):
            yield definitions
            return
        for sg in definitions.values():
            if isinstance(sg, dict):
                yield sg
        return
    if isinstance(definitions, list):
        for sg in definitions:
            if isinstance(sg, dict):
                yield sg


def _assemble_definition_entries(
    definitions: Any, scope_chain: tuple[str, ...]
) -> dict[str, dict]:
    """Mint scoped uids over the subgraph-inner skeleton and build geometry entries.

    For each subgraph definition we derive an ``sg_key`` (T8), extend the scope
    chain, and key every inner node by ``make_uid(scope_path, local_uid)`` where
    ``local_uid`` resolves ``properties['vibecomfy_uid']`` via ``mint_local_uid``
    (falling back to the inner integer id). Recurses into nested definitions so
    the scope_path is the full chain of sg_keys (SD1). A raw litegraph inner node
    already exposes the same pos/size/flags/color/bgcolor/properties keys that
    ``_build_entry`` reads.
    """
    entries: dict[str, dict] = {}
    for sg_def in _iter_subgraph_defs(definitions):
        chain = (*scope_chain, sg_key(sg_def))
        scope_path = compose_scope_path(chain)
        for node in sg_def.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            if node.get("pos") is None:
                continue
            local_uid = mint_local_uid(node, str(node.get("id")))
            uid = make_uid(scope_path, local_uid)
            entries[uid] = _build_entry(node)
        nested = sg_def.get("definitions")
        if nested:
            entries.update(_assemble_definition_entries(nested, chain))
    return entries


def write_layout(py_path: Path, wf: VibeWorkflow) -> Path:
    """Serialize the full M2 layout envelope for ``wf`` to the sidecar file.

    Per-uid node geometry is captured from each node's ``metadata['_ui']``.
    Nodes with an empty uid or no captured ``pos`` are skipped (M1.5 behavior).
    Graph-level sections are read from ``wf.metadata`` when present and otherwise
    serialized as empty/absent. Returns the sidecar path written.
    """
    entries: dict[str, dict] = {}
    for node in wf.nodes.values():
        uid = node.uid
        if not uid:
            continue
        ui = node.metadata.get("_ui")
        if not isinstance(ui, dict):
            continue
        if ui.get("pos") is None:
            continue
        entries[uid] = _build_entry(ui)

    meta = getattr(wf, "metadata", {}) or {}
    layout_meta = meta.get("_layout") if isinstance(meta.get("_layout"), dict) else {}

    # Subgraph-inner nodes: mint scoped uids over the captured definitions
    # skeleton (T10 furniture) and add their geometry entries keyed by uid (SD1).
    definitions = meta.get("definitions")
    if definitions:
        entries.update(_assemble_definition_entries(definitions, ()))

    def _section(key: str, default: Any) -> Any:
        # Prefer an explicit _layout section, then a top-level metadata key.
        if key in layout_meta:
            return layout_meta[key]
        if key in meta:
            return meta[key]
        return default

    extra = _section("extra", None)
    if not isinstance(extra, dict):
        extra = {}
    if "ds" not in extra:
        ds = _section("ds", None)
        if ds is not None:
            extra = {**extra, "ds": ds}

    envelope = {
        "store_version": STORE_VERSION,
        "vibecomfy_version": _vibecomfy_version(),
        "schema_hash": _schema_hash(),
        "entries": entries,
        "groups": _section("groups", []) or [],
        "extra": extra,
        "lastRerouteId": _section("lastRerouteId", None),
        "definitions": _section("definitions", {}) or {},
        "virtual_wires": _section("virtual_wires", {}) or {},
    }

    # gc the .py sidecar (T7, default-on): prune any per-uid entry / virtual wire
    # whose uid is not part of the live set (surviving node entries + captured
    # furniture). A fresh build keys only live geometry, so this is a no-op in the
    # common path but enforces the contract that the sidecar never carries dead
    # geometry for a uid that no longer exists.
    live_uids = set(envelope["entries"]) | set(envelope["virtual_wires"])
    gc(envelope, live_uids)

    sidecar = sidecar_path_for(py_path)
    sidecar.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return sidecar


def migrate_store(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a legacy v1 flat layout schema to the current M2 envelope.

    The frozen M1.5 sidecar was a flat
    ``{"layout_version": 1, "nodes": {uid: {pos, size, ...}}}``. This lifts each
    v1 node into a per-uid envelope ``entry`` (preserving pos/size, canonicalized
    via T3 snapping, plus any flags/color/bgcolor/properties present). Data that
    is already a v2 envelope — or an unrecognized shape — is returned unchanged
    (no-op), so the function is safe to invoke unconditionally on load.
    """
    if not isinstance(data, dict):
        return data
    if data.get("store_version") == STORE_VERSION:
        return data
    if data.get("layout_version") != 1:
        return data

    nodes = data.get("nodes")
    entries: dict[str, dict] = {}
    if isinstance(nodes, dict):
        for uid, node in nodes.items():
            if not isinstance(node, dict):
                continue
            pos = node.get("pos")
            size = node.get("size")
            properties = node.get("properties")
            entries[str(uid)] = {
                "pos": snap_pos(pos) if pos is not None else None,
                "size": snap_size(size) if size is not None else None,
                "flags": node.get("flags"),
                "color": node.get("color"),
                "bgcolor": node.get("bgcolor"),
                "properties": properties if isinstance(properties, dict) else {},
            }

    return {
        "store_version": STORE_VERSION,
        "vibecomfy_version": _vibecomfy_version(),
        "schema_hash": _schema_hash(),
        "entries": entries,
        "groups": [],
        "extra": {},
        "lastRerouteId": None,
        "definitions": {},
        "virtual_wires": {},
    }


def gc(data: dict[str, Any], live_uids: Iterable[str]) -> dict[str, Any]:
    """Prune per-uid sections to the set of currently live uids.

    Entries (and the uid-keyed ``virtual_wires`` section) whose uid is no longer
    present in ``live_uids`` are dropped; live entries are retained verbatim.
    Default-on for the ``.py`` sidecar so a converted module never accumulates
    geometry for nodes that no longer exist. Non-envelope data is returned
    unchanged. Mutates ``data`` in place and returns it.
    """
    if not isinstance(data, dict):
        return data
    live = {str(u) for u in live_uids}
    entries = data.get("entries")
    if isinstance(entries, dict):
        data["entries"] = {uid: entry for uid, entry in entries.items() if uid in live}
    virtual_wires = data.get("virtual_wires")
    if isinstance(virtual_wires, dict):
        data["virtual_wires"] = {
            uid: wire for uid, wire in virtual_wires.items() if uid in live
        }
    return data


def read_store(py_path: Path) -> dict[str, Any]:
    """Load the full sidecar envelope for ``py_path``.

    Returns the parsed envelope dict, or ``{}`` if the sidecar is absent or
    unreadable. A legacy v1 flat sidecar is migrated to the current envelope on
    load (T6).
    """
    sidecar = sidecar_path_for(py_path)
    if not sidecar.exists():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return migrate_store(data)


def read_layout(py_path: Path) -> dict[str, dict]:
    """Load per-uid node geometry from the sidecar.

    Returns ``{uid: entry}`` from the envelope's ``entries`` section, or ``{}``
    if the sidecar is absent/unreadable. Each entry exposes at least ``pos`` and
    ``size`` (M1.5 callers read those two keys).
    """
    store = read_store(py_path)
    if not store:
        return {}
    entries = store.get("entries")
    return entries if isinstance(entries, dict) else {}


__all__ = [
    "STORE_VERSION",
    "gc",
    "migrate_store",
    "read_layout",
    "read_store",
    "sidecar_path_for",
    "write_layout",
]
