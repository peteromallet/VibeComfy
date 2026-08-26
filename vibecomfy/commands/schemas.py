"""``vibecomfy schemas`` — object_info cache management and coverage validation."""

from __future__ import annotations

import argparse
import ast
import hashlib
import shutil
import json as json_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecomfy.commands._output import emit
from vibecomfy.porting.object_info.consume import get_class, list_classes
from vibecomfy.porting.object_info.serialize import CACHE_DIR, CacheIdentity, build_cache, refresh_from_source
from vibecomfy.schema import RuntimeSchemaProvider


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _extract_class_types_from_template(template_path: str | Path) -> list[str]:
    """Parse a narrative template and return every class type used in node calls.

    The ``_node`` helper signature is::

        _node(wf, class_type: str, _id: str, ...)
        _at(wf, _id: str, class_type: str, ...)
        raw_call(wf, class_type: str, _id: str, ...)

    We extract the second positional argument (a string literal).
    """
    source = Path(template_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_types: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if isinstance(func, ast.Name) and func.id in {"_node", "node", "raw_call"}:
            class_arg_index = 0 if func.id == "raw_call" and node.args and isinstance(node.args[0], ast.Constant) else 1
        elif isinstance(func, ast.Name) and func.id == "_at":
            class_arg_index = 2
        elif isinstance(func, ast.Attribute):
            if func.attr == "_node":
                class_arg_index = 1
            elif func.attr == "_at":
                class_arg_index = 2
            else:
                continue
        else:
            continue

        if len(node.args) > class_arg_index:
            arg = node.args[class_arg_index]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                class_types.append(arg.value)

    return class_types


# ---------------------------------------------------------------------------
# subcommand: refresh
# ---------------------------------------------------------------------------


def _cmd_schemas_refresh(args: argparse.Namespace) -> int:
    """``schemas refresh --source <path>``"""
    if args.server_url:
        provider = RuntimeSchemaProvider(server_url=args.server_url)
        object_info = provider.object_info()
        source = Path("out/cache") / "object_info.schemas-refresh.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(json_module.dumps(object_info, indent=2, sort_keys=True), encoding="utf-8")
        result = refresh_from_source(str(source))
        result["source"] = str(source)
        result["server_url"] = args.server_url
    else:
        if args.source is None:
            print("--source is required unless --server-url is supplied", file=__import__("sys").stderr)
            return 2
        result = refresh_schema_cache_from_source(args.source)
    identity = f"{result.get('pack_version', result.get('version', 'unknown'))} / {result.get('source_kind', 'unknown')}"
    confidence = "authoritative" if result.get("authoritative", False) else "non-authoritative"
    msg = (
        f"Cache refreshed: {result['classes_indexed']} classes "
        f"across {result['packs_written']} packs → {result['cache_dir']} "
        f"[{confidence}; identity {identity}]"
    )
    return emit(result, json=args.json, text_renderer=lambda _: msg)


def _cmd_schemas_regen_core(args: argparse.Namespace) -> int:
    """``schemas regen-core`` — introspect core ComfyUI schemas and stamp them."""
    comfy_version = _validate_comfy_version(args.comfy_version)
    object_info = _introspect_core_object_info(args)
    source = Path("out/cache") / f"object_info.comfy-core.{comfy_version}.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json_module.dumps(object_info, indent=2, sort_keys=True), encoding="utf-8")

    pack_version = comfy_version
    class_count, pack_count = build_cache(
        source,
        version=pack_version,
        cache_dir=CACHE_DIR,
        identity=CacheIdentity(
            pack_slug="comfy-core",
            pack_version=pack_version,
            evidence_identity=f"comfy-core:{comfy_version}",
            source_kind="runtime_core_object_info",
        ),
        full_pack_refresh={"comfy-core"},
    )
    result: dict[str, Any] = {
        "status": "ok",
        "classes_indexed": class_count,
        "packs_written": pack_count,
        "cache_dir": str(CACHE_DIR),
        "source": str(source),
        "pack_slug": "comfy-core",
        "version": pack_version,
        "pack_version": pack_version,
        "evidence_identity": f"comfy-core:{comfy_version}",
        "source_kind": "runtime_core_object_info",
        "authoritative": True,
        "comfy_version": comfy_version,
        "warning": _REGEN_CORE_UNSANDBOXED_WARNING,
    }
    msg = (
        f"Core schema cache regenerated for ComfyUI {comfy_version}: "
        f"{class_count} classes across {pack_count} pack(s) -> {CACHE_DIR}"
    )
    return emit(result, json=args.json, text_renderer=lambda _: msg)


def refresh_schema_cache_from_source(source: str | Path) -> dict[str, Any]:
    source_path = Path(source)
    if source_path.is_dir() and (source_path / "index.json").is_file():
        return _copy_structured_cache(source_path)
    if source_path.name == "index.json" and source_path.parent.is_dir():
        return _copy_structured_cache(source_path.parent)
    if source_path.is_file():
        data = json_module.loads(source_path.read_text(encoding="utf-8"))
        if _looks_like_structured_pack_cache(data):
            return _copy_single_structured_cache_file(source_path, data)
    result = refresh_from_source(str(source_path))
    result["source"] = str(source_path)
    return result


_REGEN_CORE_UNSANDBOXED_WARNING = (
    "WARNING: this command imports and introspects ComfyUI core code. "
    "Introspection executes third-party Python code and is not sandboxed."
)


def _validate_comfy_version(value: str) -> str:
    version = str(value or "").strip()
    if not version:
        raise ValueError("--comfy-version is required")
    if any(char.isspace() for char in version) or "/" in version or "\\" in version:
        raise ValueError("--comfy-version must be a single filesystem-safe version token")
    return version


def _introspect_core_object_info(args: argparse.Namespace) -> dict[str, Any]:
    provider = getattr(args, "object_info_provider", None)
    runner = getattr(args, "object_info_runner", None)
    if provider is not None:
        payload = provider()
    elif runner is not None:
        payload = runner(_validate_comfy_version(args.comfy_version))
    elif args.source:
        payload = json_module.loads(Path(args.source).read_text(encoding="utf-8"))
    elif args.server_url:
        payload = RuntimeSchemaProvider(server_url=args.server_url).object_info()
    else:
        from vibecomfy.porting.object_info.core_regen import capture_core_object_info

        payload = capture_core_object_info(_validate_comfy_version(args.comfy_version))
    if not isinstance(payload, dict):
        raise ValueError("object_info provider must return a JSON object")
    return payload

def _load_provenance(cache_root: Path | None = None) -> dict[str, Any]:
    prov_path = (cache_root or CACHE_DIR) / "provenance.json"
    try:
        provenance = (
            json_module.loads(prov_path.read_text(encoding="utf-8"))
            if prov_path.is_file()
            else {}
        )
    except (OSError, json_module.JSONDecodeError):
        provenance = {}
    return provenance if isinstance(provenance, dict) else {}


def _write_provenance(provenance: dict[str, Any], cache_root: Path | None = None) -> None:
    root = cache_root or CACHE_DIR
    root.mkdir(parents=True, exist_ok=True)
    (root / "provenance.json").write_text(
        json_module.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _prune_stale_index_rows(index: dict[str, Any]) -> list[str]:
    """Drop index rows whose mapped cache file no longer exists.

    RRSYN2-3: regenerating the index after an ingest must not leave rows
    pointing at a replaced/removed capture (e.g. a stale AceStep pack file
    replaced by a real capture under a new pinned name).
    """
    stale = [
        class_type
        for class_type, filename in index.items()
        if not isinstance(filename, str)
        or not (CACHE_DIR / filename).is_file()
    ]
    for class_type in stale:
        del index[class_type]
    return stale


def _attest_ingested_capture(
    filename: str,
    source_file: Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Record/refresh the provenance attestation for one ingested pack.

    RRSYN2-3: an ingested capture without a provenance row can never pass
    the authoritative preflight (``_provenance_row`` requires a repo or a
    locked commit), so the refresh path regenerates provenance together
    with the index: sha256 over the exact payload bytes, class count,
    owning pack identity, and any attestation carried by ``_cache_metadata``
    (repo / locked_commit / captured_at).  Ingestion time is recorded as
    ``ingested_at`` — never as the capture time, which only a real capture
    can attest.
    """
    provenance = _load_provenance()
    packs = provenance.get("packs")
    if not isinstance(packs, dict):
        packs = {}
    meta = data.get("_cache_metadata")
    meta = meta if isinstance(meta, dict) else {}
    pack_identity = (
        str(meta.get("pack") or "")
        or next(
            (
                str(value.get("pack") or "")
                for value in data.values()
                if isinstance(value, dict) and value.get("pack")
            ),
            "",
        )
        or source_file.stem.split("@", 1)[0]
    )
    # Batch-review RR2: the entry is built FRESH — capture-identity fields
    # come ONLY from the newly ingested payload's own ``_cache_metadata``
    # attestation.  A replacement payload under an existing filename must
    # never inherit the previous revision's repo / locked_commit /
    # captured_at: stale authority on unattested bytes violates the
    # provenance law, so absent fields are removed and the ingest stays
    # non-authoritative.
    entry = {
        "pack": pack_identity,
        "classes": len([key for key in data if key != "_cache_metadata"]),
        "schema_sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
    }
    for key in ("repo", "locked_commit"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            entry[key] = value.strip()
    captured_at = meta.get("captured_at") or meta.get(
        "capture_time"
    )
    if isinstance(captured_at, str) and captured_at.strip():
        entry["captured_at"] = captured_at.strip()
    entry["ingested_at"] = datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    )
    entry["ingested_from"] = str(source_file)
    packs[filename] = entry
    provenance["packs"] = packs
    provenance["class_count"] = len(
        json_module.loads((CACHE_DIR / "index.json").read_text(encoding="utf-8"))
    )
    _write_provenance(provenance)
    return entry


def _copy_structured_cache(source_dir: Path) -> dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in source_dir.glob("*.json"):
        shutil.copy2(path, CACHE_DIR / path.name)
        copied += 1
    index_path = CACHE_DIR / "index.json"
    index = json_module.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, dict):
        index = {}
    # RRSYN2-3: regenerate — prune rows whose capture file is gone, then
    # keep provenance.class_count consistent with the rewritten index.
    pruned = _prune_stale_index_rows(index)
    if pruned:
        index_path.write_text(
            json_module.dumps(index, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    provenance = _load_provenance()
    provenance["class_count"] = len(index)
    _write_provenance(provenance)
    return {
        "status": "ok",
        "classes_indexed": len(index),
        "stale_rows_pruned": len(pruned),
        "packs_written": max(0, copied - 1),
        "cache_dir": str(CACHE_DIR),
        "version": "structured-cache",
        "pack_version": "structured-cache",
        "source": str(source_dir),
        "authoritative": False,
        "source_kind": "structured_cache_copy",
    }


def _copy_single_structured_cache_file(source_file: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Ingest ONE pinned pack capture into the authoritative cache.

    RRSYN2-3: this is the path ``schemas refresh --source <capture>.json``
    uses for real pinned captures.  It regenerates the index rows AND the
    provenance attestation (payload digest, class count, capture identity)
    so an ingested capture is preflight-authoritative instead of silently
    unattested.  No workflow-observation fallback exists here by design.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / source_file.name
    shutil.copy2(source_file, target)
    index_path = CACHE_DIR / "index.json"
    if index_path.is_file():
        index = json_module.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(index, dict):
            index = {}
    else:
        index = {}
    # Batch-review RR2: same-filename replacement must REGENERATE index
    # membership — drop EVERY row mapped to the target file (its old classes
    # may be gone from the new payload) before adding exactly the captured
    # classes.  Pruning only missing-file rows would leave the index (and
    # provenance.class_count) attesting classes absent from the payload.
    superseded = [
        class_type
        for class_type, mapped in index.items()
        if mapped == target.name
    ]
    for class_type in superseded:
        del index[class_type]
    for class_type in data:
        if class_type != "_cache_metadata":
            index[str(class_type)] = target.name
    pruned = _prune_stale_index_rows(index)
    index_path.write_text(json_module.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    entry = _attest_ingested_capture(target.name, source_file, data)
    return {
        "status": "ok",
        "classes_indexed": entry["classes"],
        "stale_rows_pruned": len(pruned) + len(superseded),
        "provenance": entry,
        "packs_written": 1,
        "cache_dir": str(CACHE_DIR),
        "version": "structured-cache",
        "pack_version": "structured-cache",
        "source": str(source_file),
        "authoritative": bool(entry.get("repo") or entry.get("locked_commit")),
        "source_kind": "structured_cache_copy",
    }



def _looks_like_structured_pack_cache(data: Any) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    entries = [value for key, value in data.items() if key != "_cache_metadata"]
    return bool(entries) and all(isinstance(value, dict) and "inputs" in value and "outputs" in value for value in entries)

# ---------------------------------------------------------------------------
# subcommand: validate-coverage
# ---------------------------------------------------------------------------


def _cmd_schemas_validate_coverage(args: argparse.Namespace) -> int:
    """``schemas validate-coverage <template>``"""
    template_path = Path(args.template)
    if not template_path.is_file():
        print(f"Template not found: {template_path}", file=__import__("sys").stderr)
        return 1

    class_types = _extract_class_types_from_template(template_path)
    all_cached = set(list_classes())
    unique = sorted(set(class_types))
    covered: list[str] = []
    missing: list[str] = []

    for ct in unique:
        if get_class(ct) is not None:
            covered.append(ct)
        else:
            missing.append(ct)

    payload: dict[str, Any] = {
        "template": str(template_path),
        "classes_found": len(unique),
        "covered": len(covered),
        "missing": len(missing),
        "covered_classes": covered,
        "missing_classes": missing,
        "cache_classes_total": len(all_cached),
    }

    if not args.json:
        print(f"Template: {template_path}")
        print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: {len(missing)}")
        if covered:
            print(f"  Covered: {', '.join(covered)}")
        if missing:
            print(f"  Missing:  {', '.join(missing)}")
        print(f"Cache: {len(all_cached)} classes indexed")
        return 0

    return emit(payload, json=True, text_renderer=lambda _: None)


# ---------------------------------------------------------------------------
# subcommand: ensure
# ---------------------------------------------------------------------------


def _cmd_schemas_ensure(args: argparse.Namespace) -> int:
    """``schemas ensure <template>`` — ensure all class schemas are cached.

    Parses class types from the template, diffs against the object_info cache,
    maps missing classes to known node packs, and triggers pack extraction
    (clone + extract) for any needed packs.  No-op when all classes are already
    cached.
    """
    template_path = Path(args.template)
    if not template_path.is_file():
        payload: dict[str, Any] = {
            "template": str(template_path),
            "error": "Template not found",
        }
        if args.json:
            return emit(payload, json=True, text_renderer=lambda _: None)
        print(f"Template not found: {template_path}", file=__import__("sys").stderr)
        return 1

    class_types = _extract_class_types_from_template(template_path)
    all_cached = set(list_classes())
    unique = sorted(set(class_types))
    missing_classes = [ct for ct in unique if ct not in all_cached]
    covered = [ct for ct in unique if ct in all_cached]

    # --- No-op when all classes are cached ---
    if not missing_classes:
        payload = {
            "template": str(template_path),
            "classes_found": len(unique),
            "covered": len(covered),
            "missing": 0,
            "covered_classes": covered,
            "missing_classes": [],
            "cache_classes_total": len(all_cached),
            "packs_needed": [],
            "packs_extracted": [],
            "action": "noop",
        }
        if args.json:
            return emit(payload, json=True, text_renderer=lambda _: None)
        print(f"Template: {template_path}")
        print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: 0")
        print("All class schemas already cached — nothing to do.")
        return 0

    # --- Map missing classes to the lazy node-pack catalog ---
    from vibecomfy.node_packs import resolve_node_packs

    packs_needed = resolve_node_packs(set(missing_classes))

    if not packs_needed:
        payload = {
            "template": str(template_path),
            "classes_found": len(unique),
            "covered": len(covered),
            "missing": len(missing_classes),
            "covered_classes": covered,
            "missing_classes": missing_classes,
            "cache_classes_total": len(all_cached),
            "packs_needed": [],
            "packs_extracted": [],
            "unresolved": missing_classes,
            "warning": (
                "Some missing classes could not be mapped to a known node pack. "
                "They may be built-in ComfyUI classes or from unregistered packs."
            ),
            "action": "partial",
        }
        if args.json:
            return emit(payload, json=True, text_renderer=lambda _: None)
        print(f"Template: {template_path}")
        print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: {len(missing_classes)}")
        print(f"Missing (unresolved): {', '.join(missing_classes)}")
        print("Warning: some missing classes could not be mapped to a known node pack.")
        return 1

    # --- Extract missing packs ---
    from tools.clone_and_extract_packs import (
        INDEX_PATH,
        load_index,
        process_pack,
    )

    index = load_index()
    original_index = dict(index)

    pack_names_needed = [p.name for p in packs_needed]
    reports = [process_pack(pack, index) for pack in packs_needed]

    # Write updated index if it changed
    if index != original_index:
        INDEX_PATH.write_text(
            json_module.dumps(dict(sorted(index.items())), indent=2) + "\n",
            encoding="utf-8",
        )

    packs_extracted = [
        {
            "name": r.name,
            "class_count": r.class_count,
            "method": r.method or "none",
            "cache_file": r.cache_file or "",
            "cloned": r.cloned,
            "sha7": r.sha7,
            "failures": r.failures,
            "warnings": r.warnings,
        }
        for r in reports
    ]

    payload: dict[str, Any] = {
        "template": str(template_path),
        "classes_found": len(unique),
        "covered": len(covered),
        "missing": len(missing_classes),
        "covered_classes": covered,
        "missing_classes": missing_classes,
        "cache_classes_total": len(all_cached),
        "packs_needed": pack_names_needed,
        "packs_extracted": packs_extracted,
        "action": "extracted",
    }

    if args.json:
        return emit(payload, json=True, text_renderer=lambda _: None)

    print(f"Template: {template_path}")
    print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: {len(missing_classes)}")
    print(f"Packs needed: {', '.join(pack_names_needed)}")
    for report in reports:
        print(f"  - {report.name}: {report.class_count} classes, method={report.method or 'none'}")
        if report.cache_file:
            print(f"    cache: {report.cache_file}")
        if report.warnings:
            for warning in report.warnings:
                print(f"    warning: {warning}")
        if report.failures:
            for failure in report.failures:
                print(f"    FAILURE: {failure}")

    return 0 if not any(r.failures and r.class_count == 0 for r in reports) else 1


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    schemas = subparsers.add_parser("schemas", help="Object_info cache management")

    schemas_sub = schemas.add_subparsers(dest="schemas_subcmd", required=True)

    # --- schemas refresh --------------------------------------------------
    refresh = schemas_sub.add_parser("refresh", help="Regenerate cache from object_info dump")
    refresh.add_argument("--source", help="Path to object_info JSON dump or structured object_info cache file/directory")
    refresh.add_argument("--json", action="store_true", help="Output as JSON")
    refresh.add_argument("--server-url", help="Fetch object_info from a live server URL before refreshing the cache")
    # Stubs for future runtime modes
    refresh.add_argument(
        "--runtime",
        choices=["embedded", "server", "runpod"],
        default=None,
        help="Future: fetch object_info from a live runtime (not implemented)",
    )
    refresh.set_defaults(func=_cmd_schemas_refresh)

    # --- schemas regen-core -----------------------------------------------
    regen_core = schemas_sub.add_parser(
        "regen-core",
        help="Regenerate authoritative ComfyUI core object_info cache",
        description=(
            "Regenerate the authoritative ComfyUI core object_info cache. "
            + _REGEN_CORE_UNSANDBOXED_WARNING
        ),
        epilog=_REGEN_CORE_UNSANDBOXED_WARNING,
    )
    regen_core.add_argument(
        "--comfy-version",
        required=True,
        help="ComfyUI version identity to stamp on the core object_info cache, e.g. 0.24.0.1",
    )
    regen_core.add_argument("--json", action="store_true", help="Output as JSON")
    regen_core.add_argument("--source", help=argparse.SUPPRESS)
    regen_core.add_argument(
        "--server-url",
        help="Fetch object_info from a live server URL instead of the default runtime provider",
    )
    regen_core.set_defaults(func=_cmd_schemas_regen_core)

    # --- schemas validate-coverage ----------------------------------------
    validate = schemas_sub.add_parser(
        "validate-coverage", help="Check which classes in a template have cache entries"
    )
    validate.add_argument("template", help="Path to narrative template (.py)")
    validate.add_argument("--json", action="store_true", help="Output as JSON")
    validate.set_defaults(func=_cmd_schemas_validate_coverage)

    # --- schemas ensure ---------------------------------------------------
    ensure = schemas_sub.add_parser(
        "ensure", help="Ensure all class schemas in a template are cached"
    )
    ensure.add_argument("template", help="Path to narrative template (.py)")
    ensure.add_argument("--json", action="store_true", help="Output as JSON")
    ensure.set_defaults(func=_cmd_schemas_ensure)
