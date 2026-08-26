"""``vibecomfy schemas`` — object_info cache management and coverage validation."""

import argparse
import ast
import hashlib
import json as json_module
import os
import shutil
import subprocess
import sys
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
    """``schemas validate-coverage <template>`` / ``--manifest <path>``.

    Template positional keeps its historical exit 0 for back-compat. With
    ``--manifest`` gaps exit 1 and the payload carries ``ensure_command``.
    Both modes reuse ``missing_live_captures`` (stub/unattested counts as gap).
    """
    from vibecomfy.schema.ensure_capture import format_schema_gap, missing_live_captures
    from vibecomfy.porting.object_info import consume as consume_module

    manifest_arg = getattr(args, "manifest", None)
    template_arg = getattr(args, "template", None)
    is_manifest = bool(manifest_arg)
    # Exactly one source required when --manifest is in use; template-only
    # keeps backward compatibility (template is required positional).
    if is_manifest:
        if template_arg:
            msg = "provide exactly one of: <template> or --manifest PATH"
            if getattr(args, "json", False):
                return emit({"error": msg}, json=True, text_renderer=lambda _: None)
            print(msg, file=__import__("sys").stderr)
            return 1
        manifest_path = Path(manifest_arg)
        if not manifest_path.is_file():
            if getattr(args, "json", False):
                return emit({"error": f"Manifest not found: {manifest_path}"}, json=True, text_renderer=lambda _: None)
            print(f"Manifest not found: {manifest_path}", file=__import__("sys").stderr)
            return 1
        try:
            class_types, warnings = _manifest_gated_classes(manifest_path)
        except ValueError as exc:
            if getattr(args, "json", False):
                return emit({"error": str(exc)}, json=True, text_renderer=lambda _: None)
            print(str(exc), file=__import__("sys").stderr)
            return 1
        unique = sorted(set(class_types))
        cache_root = Path(consume_module.CACHE_DIR)
        missing = missing_live_captures(unique, cache_dir=cache_root)
        covered = [ct for ct in unique if ct not in set(missing)]
        all_cached = set(consume_module.list_classes() if hasattr(consume_module, "list_classes") else [])
        # Fallback to list_classes import if consume lacks it (patched in tests)
        if not all_cached:
            try:
                from vibecomfy.porting.object_info.consume import list_classes
                all_cached = set(list_classes())
            except Exception:
                all_cached = set()
        ensure_command = format_schema_gap(manifest_path, missing) if missing else f"vibecomfy schemas ensure --manifest {manifest_path}"
        payload: dict[str, Any] = {
            "manifest": str(manifest_path),
            "classes_found": len(unique),
            "covered": len(covered),
            "missing": len(missing),
            "covered_classes": covered,
            "missing_classes": missing,
            "ensure_command": ensure_command,
            "warnings": warnings,
            "cache_classes_total": len(all_cached),
        }
        if not getattr(args, "json", False):
            print(f"Manifest: {manifest_path}")
            print(f"Classes found: {len(unique)}  |  covered: {len(covered)}  |  missing: {len(missing)}")
            if covered:
                print(f"  Covered: {', '.join(covered)}")
            if missing:
                print(f"  Missing:  {', '.join(missing)}")
            for w in warnings:
                print(f"warning: {w}")
            if missing:
                print(ensure_command)
            print(f"Cache: {len(all_cached)} classes indexed")
            return 1 if missing else 0
        emit(payload, json=True, text_renderer=lambda _: None)
        return 1 if missing else 0
    # --- template path (back-compat: exit 0 even when missing) --------------
    template_path = Path(template_arg) if template_arg else None
    if template_path is None or not template_path.is_file():
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
    payload = {
        "template": str(template_path),
        "classes_found": len(unique),
        "covered": len(covered),
        "missing": len(missing),
        "covered_classes": covered,
        "missing_classes": missing,
        "cache_classes_total": len(all_cached),
    }
    if not getattr(args, "json", False):
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


def _import_scenario_obligations():
    """Import the harness obligation module (single source of gated-class truth)."""
    try:
        from tests.live_agentic_harness import scenario_obligations as mod
        return mod
    except ImportError:
        pass
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from tests.live_agentic_harness import scenario_obligations as mod

    return mod


def _manifest_gated_classes(manifest_path: Path) -> tuple[list[str], list[str]]:
    """Gated classes needing captures for a comparison manifest (``entries[].id``).

    Reuses the harness obligation loader and its ``_GATED_CLASS_RE`` — never a
    copy. Classes come from each entry's source workflow plus its declared
    schema-evidence requirements. Returns ``(classes, warnings)``.
    """
    mod = _import_scenario_obligations()
    try:
        manifest = json_module.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json_module.JSONDecodeError) as exc:
        raise ValueError(f"unreadable comparison manifest {manifest_path}: {exc}") from exc
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"comparison manifest {manifest_path} has no entries list")
    classes: set[str] = set()
    warnings: list[str] = []
    for item in entries:
        scenario_id = str(item.get("id") or "").strip() if isinstance(item, dict) else ""
        if not scenario_id:
            warnings.append("manifest entry without an id was skipped")
            continue
        obligation = mod.load_scenario_obligation(scenario_id)
        if obligation is None:
            warnings.append(f"no locked descriptor for scenario {scenario_id!r}; skipped")
            continue
        classes.update(
            c for c in obligation.custom_node_classes if mod._GATED_CLASS_RE.search(c)
        )
        classes.update(
            str(req.get("class_type"))
            for req in obligation.schema_evidence_requirements
            if req.get("class_type")
        )
    return sorted(classes), warnings


def _resolve_pack_ref(class_type: str):
    """Registry lookup → first candidate ``PackRef`` carrying a clone URL.

    Registry REST metadata only; provisional ``/nodes/.../schema`` responses are
    never persisted as cache truth.
    """
    from vibecomfy.registry import pack_resolver

    ref = None
    try:
        resolution = pack_resolver.resolve_missing_nodes(class_type)
    except Exception:  # noqa: BLE001 — resolver failures degrade to resolve_pack below
        resolution = None
    if resolution is not None:
        for candidate in getattr(resolution, "candidates", ()) or ():
            candidate_ref = getattr(candidate, "ref", None)
            if candidate_ref is not None and getattr(candidate_ref, "url", None):
                ref = candidate_ref
                break
    if ref is None:
        try:
            direct = pack_resolver.resolve_pack(class_type)
        except Exception as exc:
            raise LookupError(
                f"registry lookup found no pack with a source URL for {class_type!r}: {exc}"
            ) from exc
        ref = next((r for r in [direct.ref, *direct.candidates] if getattr(r, "url", None)), None)
        if ref is None:
            raise LookupError(
                f"registry resolved {class_type!r} but no candidate carries a source URL"
            )
    return ref


def _clone_pin(clone_dir: Path, fallback_url: str | None) -> tuple[str, str]:
    """Pin evidence from the clone itself: (remote URL, HEAD commit)."""

    def _git(*argv: str) -> str | None:
        try:
            proc = subprocess.run(
                ["git", "-C", str(clone_dir), *argv],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.strip() or None

    url = _git("remote", "get-url", "origin") or fallback_url or ""
    commit = _git("rev-parse", "HEAD") or ""
    return url, commit


def _on_demand_provider():
    """LRU-bounded sandbox provider supplying ``_ensure_clone`` / ``_enforce_cap``."""
    from vibecomfy.schema.on_demand import OnDemandInstallSchemaProvider

    return OnDemandInstallSchemaProvider()


_EXTRACT_EXHAUSTED_DETAIL = (
    "extraction produced no schema from any available rung "
    "(rung 1: static AST; rung 2: stubbed-subprocess INPUT_TYPES — always on "
    "for this command). Rung 3 (embedded comfy-as-library) is not yet available: "
    "deferred Batch B."
)


def _embedded_note(comfy_version: str | None) -> str:
    if comfy_version:
        return f" Pinned comfy version {comfy_version} applies once rung 3 lands."
    return (
        " When it lands it will require --comfy-version or env "
        "VIBECOMFY_EMBEDDED_COMFY_VERSION; neither is set."
    )


def _capture_missing_classes(
    missing_classes: list[str],
    *,
    cache_root: Path,
    provider,
    comfy_version: str | None,
) -> dict[str, Any]:
    """Per gap class: registry → ephemeral sandbox clone → ladder → persist.

    Never writes hollow/stub schemas: a class whose extraction yields nothing
    is reported as a failure instead of being closed with guessed data.
    """
    from vibecomfy.schema import extract as extract_module
    from vibecomfy.schema.ensure_capture import persist_on_demand_pack

    failures: list[dict[str, str]] = []
    extracted: list[dict[str, Any]] = []
    by_slug: dict[str, dict[str, Any]] = {}
    for class_type in missing_classes:
        try:
            ref = _resolve_pack_ref(class_type)
        except LookupError as exc:
            failures.append({"class_type": class_type, "step": "resolve", "detail": str(exc)})
            continue
        slug = getattr(ref, "slug", None) or getattr(ref, "registry_id", None) or "pack"
        group = by_slug.setdefault(slug, {"ref": ref, "classes": []})
        group["classes"].append(class_type)

    for slug, group in sorted(by_slug.items()):
        ref = group["ref"]
        classes = sorted(group["classes"])
        clone_dir = provider._ensure_clone(ref)
        if clone_dir is None:
            failures.append(
                {
                    "class_type": ", ".join(classes),
                    "step": "clone",
                    "detail": (
                        f"could not shallow-clone {getattr(ref, 'url', None)!r} into the "
                        "LRU schema sandbox"
                    ),
                }
            )
            continue
        result = extract_module.extract_pack_schemas(
            clone_dir,
            pack_name=slug,
            allow_import=True,  # rung 2 cannot be turned off on this command
            import_timeout=120,
        )
        # NO allow_embedded kwarg: rung 3 does not exist until deferred Batch B;
        # passing it would TypeError.
        if not result.entries or result.method not in ("ast", "import"):
            detail = "; ".join(result.failures) or "empty extract result"
            failures.append(
                {
                    "class_type": ", ".join(classes),
                    "step": "extract",
                    "detail": _EXTRACT_EXHAUSTED_DETAIL + _embedded_note(comfy_version)
                    + f" [{detail}]",
                }
            )
            continue
        repo_url, commit = _clone_pin(clone_dir, getattr(ref, "url", None))
        persist_on_demand_pack(
            pack_slug=slug,
            registry_pack_version=getattr(ref, "version", None) or "",
            repo=repo_url,
            locked_commit=commit,
            extraction_rung=result.method,
            entries=result.entries,
            cache_dir=cache_root,
        )
        provider._enforce_cap()  # LRU preserved; nothing permanent installed
        extracted.append({"pack": slug, "method": result.method})

    return {"failures": failures, "packs_extracted": extracted}


def _cmd_schemas_ensure(args: argparse.Namespace) -> int:
    """``schemas ensure <template>`` / ``schemas ensure --manifest <path>``.

    Ensures every needed class has an attested live capture: gaps come from
    ``missing_live_captures`` (stub/unattested rows count as gaps), and each
    gap is filled via registry resolve → ephemeral LRU-bounded clone → the
    extraction ladder → ``persist_on_demand_pack`` with honest provenance tier.
    Fail closed: any unfillable gap exits non-zero naming the class, the failed
    step, and the exact retry command. No-op when all classes are attested.
    """
    template_arg = getattr(args, "template", None)
    manifest_arg = getattr(args, "manifest", None)
    if bool(template_arg) == bool(manifest_arg):
        message = "provide exactly one of: <template> positional argument or --manifest PATH"
        if args.json:
            emit({"error": message}, json=True, text_renderer=lambda _: None)
        else:
            print(message, file=__import__("sys").stderr)
        return 1

    comfy_raw = (getattr(args, "comfy_version", None) or os.environ.get("VIBECOMFY_EMBEDDED_COMFY_VERSION") or "").strip()
    comfy_version = _validate_comfy_version(comfy_raw) if comfy_raw else None

    is_manifest = bool(manifest_arg)
    source_path = Path(manifest_arg if is_manifest else template_arg)
    if not source_path.is_file():
        kind = "Manifest" if is_manifest else "Template"
        payload = {"error": f"{kind} not found", kind.lower(): str(source_path)}
        if args.json:
            emit(payload, json=True, text_renderer=lambda _: None)
        else:
            print(f"{kind} not found: {source_path}", file=__import__("sys").stderr)
        return 1

    warnings: list[str] = []
    if is_manifest:
        try:
            class_types, warnings = _manifest_gated_classes(source_path)
        except ValueError as exc:
            payload = {"error": str(exc)}
            if args.json:
                emit(payload, json=True, text_renderer=lambda _: None)
            else:
                print(str(exc), file=__import__("sys").stderr)
            return 1
    else:
        class_types = _extract_class_types_from_template(source_path)

    unique = sorted(set(class_types))

    from vibecomfy.porting.object_info import consume as consume_module
    from vibecomfy.schema.ensure_capture import format_schema_gap, format_template_gap, missing_live_captures

    cache_root = Path(consume_module.CACHE_DIR)
    missing = missing_live_captures(unique, cache_dir=cache_root)
    covered = [ct for ct in unique if ct not in set(missing)]
    retry_command = (
        format_schema_gap(source_path, missing)
        if is_manifest
        else format_template_gap(source_path, missing)
    )
    # Ensure retry_command ends with the exact ensure invocation (helper
    # already does). Normalise to just the command when missing list is
    # embedded as prefix: extract tail after last '; run ' if present.
    if "; run " in retry_command:
        retry_command = retry_command.split("; run ")[-1]

    payload: dict[str, Any] = {
        "template" if not is_manifest else "manifest": str(source_path),
        "classes_found": len(unique),
        "covered_classes": covered,
        "missing_classes": missing,
        "warnings": warnings,
        "embedded_comfy_version": comfy_version,
        "retry_command": retry_command,
    }

    if not missing:
        payload.update(
            {
                "missing": 0,
                "packs_needed": [],
                "packs_extracted": [],
                "failures": [],
                "action": "noop",
            }
        )
        if args.json:
            return emit(payload, json=True, text_renderer=lambda _: None)
        print(f"{('Manifest' if is_manifest else 'Template')}: {source_path}")
        print(f"Classes: {len(unique)}  |  covered: {len(covered)}  |  missing: 0")
        print("All class schemas already captured — nothing to do.")
        return 0

    outcome = _capture_missing_classes(
        missing,
        cache_root=cache_root,
        provider=_on_demand_provider(),
        comfy_version=comfy_version,
    )
    consume_module.reset_cache()
    still_missing = missing_live_captures(unique, cache_dir=cache_root)

    failures = outcome["failures"]
    exit_code = 1 if failures or still_missing else 0
    payload.update(
        {
            "missing": len(missing),
            "packs_needed": sorted({r["pack"] for r in outcome["packs_extracted"]}),
            "packs_extracted": outcome["packs_extracted"],
            "failures": failures,
            "still_missing": still_missing,
            "action": "failed" if exit_code else "extracted",
        }
    )

    if args.json:
        emit(payload, json=True, text_renderer=lambda _: None)
        return exit_code

    label = "Manifest" if is_manifest else "Template"
    print(f"{label}: {source_path}")
    print(f"Classes: {len(unique)}  |  covered: {len(covered)}  |  missing: {len(missing)}")
    for warning in warnings:
        print(f"warning: {warning}")
    for report in outcome["packs_extracted"]:
        print(f"  - {report['pack']}: method={report['method']}")
    for failure in failures:
        print(f"FAILURE [{failure['step']}] {failure['class_type']}: {failure['detail']}")
    if still_missing:
        print(f"Still missing live capture: {', '.join(still_missing)}")
    if exit_code:
        print(f"Retry with: {retry_command}")
    return exit_code



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
    validate.add_argument("template", nargs="?", default=None, help="Path to narrative template (.py) — or pass --manifest")
    validate.add_argument(
        "--manifest",
        default=None,
        metavar="PATH",
        help="Comparison manifest (entries[].id): gated classes are those declared for each scenario",
    )
    validate.add_argument("--json", action="store_true", help="Output as JSON")
    validate.set_defaults(func=_cmd_schemas_validate_coverage)

    # --- schemas ensure ---------------------------------------------------
    ensure = schemas_sub.add_parser(
        "ensure",
        help="Ensure class schemas for a template or comparison manifest are captured",
    )
    ensure.add_argument(
        "template",
        nargs="?",
        default=None,
        help="Path to narrative template (.py) — or pass --manifest instead",
    )
    ensure.add_argument(
        "--manifest",
        default=None,
        metavar="PATH",
        help=(
            "Comparison manifest (entries[].id): discover gated classes via each "
            "scenario's locked descriptor and ensure every one has an attested live capture"
        ),
    )
    ensure.add_argument("--json", action="store_true", help="Output as JSON")
    ensure.add_argument(
        "--comfy-version",
        default=None,
        metavar="VERSION",
        help=(
            "Rung 3 pin (or env VIBECOMFY_EMBEDDED_COMFY_VERSION). Unused today: "
            "rung 3 is not yet available (deferred Batch B)"
        ),
    )
    ensure.add_argument(
        "--no-embedded",
        action="store_true",
        help=(
            "Accepted no-op placeholder: rung 3 (embedded) is not yet available. "
            "Rung 2 cannot be disabled on this command"
        ),
    )
    ensure.set_defaults(func=_cmd_schemas_ensure)
