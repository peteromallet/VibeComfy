from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys

from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.analysis.node_coverage import build_workflow_coverage
from vibecomfy.commands._output import emit
from vibecomfy.commands._index_files import IndexReadError, print_index_error, read_index_json
from vibecomfy.node_packs import KNOWN_NODE_PACKS, resolve_node_packs, unresolved_class_types
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.registry import load_workflow_reference
from vibecomfy.registry.pack_resolver import PackResolverError, resolve_pack
from vibecomfy.schema import SchemaIndexError, get_authoring_schema_provider, get_schema_provider, schema_for, schemas_for, socket_types_compatible
import vibecomfy.node_packs_install as node_packs_install
from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile, write_lockfile


def _cmd_nodes_list(args: argparse.Namespace) -> int:
    path = Path("node_index.json")
    if not path.exists():
        print("node_index.json not found; run `vibecomfy sources sync`")
        return 1
    try:
        rows = read_index_json(path, default=[])
    except IndexReadError as exc:
        print_index_error(exc)
        return 1
    return emit(rows[: args.limit], json=args.json, text_renderer=lambda selected: "\n".join(str(row) for row in selected))


def _cmd_nodes_spec(args: argparse.Namespace) -> int:
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", args.class_type, re.I):
        return _cmd_nodes_spec_subgraph(args)
    provider = get_authoring_schema_provider(object_info_cache_path=args.object_info_cache)
    try:
        schema = provider.get_schema(args.class_type)
    except SchemaIndexError as exc:
        print(f"{exc}; run `vibecomfy sources sync` to rebuild indexes.")
        return 1
    if schema is None:
        print(
            f"node schema not found for {args.class_type!r}; run `vibecomfy sources sync`, "
            "start a runtime with /object_info, or install the custom node source locally"
        )
        return 1
    print(json.dumps(asdict(schema), indent=2, sort_keys=True))
    return 0


def _cmd_nodes_compatible_with(args: argparse.Namespace) -> int:
    provider = get_authoring_schema_provider(object_info_cache_path=getattr(args, "object_info_cache", None))
    if getattr(args, "to_class", None) is None:
        payload = _compatible_socket_search(provider, args.type_or_from_class, socket_role=args.socket_role)
        if getattr(args, "json", False):
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"compatible {args.socket_role} sockets for {args.type_or_from_class}: {payload['compatible_count']}")
            for match in payload["matches"][:25]:
                print(f"- {match['class_type']}.{match['socket']} ({match['socket_type']})")
        return 0
    if getattr(args, "to_input", None) is None:
        print("to_input is required when checking a concrete node endpoint", file=sys.stderr)
        return 2
    from_schema = provider.get_schema(args.type_or_from_class)
    to_schema = provider.get_schema(args.to_class)
    from_output = str(getattr(args, "from_output", "0"))
    to_input = str(args.to_input)
    output_type = _schema_output_type(from_schema, from_output)
    input_type = _schema_input_type(to_schema, to_input)
    compatible = socket_types_compatible(output_type, input_type)
    payload = {
        "from_class": args.type_or_from_class,
        "from_output": from_output,
        "from_output_type": output_type,
        "to_class": args.to_class,
        "to_input": to_input,
        "to_input_type": input_type,
        "compatible": compatible,
        "known": output_type is not None and input_type is not None,
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        verdict = "compatible" if compatible else "incompatible"
        print(f"{args.type_or_from_class}.{from_output} -> {args.to_class}.{to_input}: {verdict}")
        print(f"output_type={output_type or 'unknown'} input_type={input_type or 'unknown'}")
    return 0 if compatible else 1


def _schema_output_type(schema: object | None, output: str) -> str | None:
    outputs = getattr(schema, "outputs", None) or []
    try:
        index = int(output)
    except (TypeError, ValueError):
        index = None
    if index is not None and 0 <= index < len(outputs):
        value = getattr(outputs[index], "type", None)
        return str(value) if value is not None else None
    for item in outputs:
        if getattr(item, "name", None) == output:
            value = getattr(item, "type", None)
            return str(value) if value is not None else None
    return None


def _schema_input_type(schema: object | None, input_name: str) -> str | None:
    spec = (getattr(schema, "inputs", {}) or {}).get(input_name)
    value = getattr(spec, "type", None)
    return str(value) if value is not None else None


def _compatible_socket_search(provider: object, socket_type: str, *, socket_role: str) -> dict[str, object]:
    schemas = schemas_for(provider) or {}
    matches: list[dict[str, object]] = []
    for class_type, schema in sorted(schemas.items()):
        if socket_role == "input":
            for input_name, spec in (getattr(schema, "inputs", None) or {}).items():
                candidate_type = getattr(spec, "type", None)
                if candidate_type is not None and socket_types_compatible(socket_type, candidate_type):
                    matches.append(
                        {
                            "class_type": str(class_type),
                            "socket": str(input_name),
                            "socket_role": "input",
                            "socket_type": str(candidate_type) if candidate_type is not None else None,
                        }
                    )
        else:
            for output_index, output in enumerate(getattr(schema, "outputs", None) or []):
                candidate_type = getattr(output, "type", None)
                if candidate_type is not None and socket_types_compatible(candidate_type, socket_type):
                    matches.append(
                        {
                            "class_type": str(class_type),
                            "socket": str(getattr(output, "name", None) or output_index),
                            "socket_role": "output",
                            "socket_type": str(candidate_type) if candidate_type is not None else None,
                        }
                    )
    return {
        "type": socket_type,
        "as": socket_role,
        "classes": sorted({str(match["class_type"]) for match in matches}),
        "matches": matches,
        "compatible_count": len(matches),
        "provider": type(provider).__name__,
    }


def _cmd_nodes_spec_subgraph(args: argparse.Namespace) -> int:
    candidates: list[Path] = []
    source = getattr(args, "source", None)
    if source:
        candidates.append(Path(source))
    else:
        candidates.extend(Path("workflow_corpus").rglob("*.json"))
    for path in candidates:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        definitions = raw.get("definitions") if isinstance(raw, dict) else None
        subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
        if isinstance(subgraphs, dict):
            iterable = subgraphs.values()
        elif isinstance(subgraphs, list):
            iterable = subgraphs
        else:
            iterable = ()
        for subgraph in iterable:
            if not isinstance(subgraph, dict) or str(subgraph.get("id")) != args.class_type:
                continue
            class_counts: dict[str, int] = {}
            for node in subgraph.get("nodes") or ():
                if isinstance(node, dict):
                    class_type = str(node.get("type") or node.get("class_type") or "Unknown")
                    class_counts[class_type] = class_counts.get(class_type, 0) + 1
            payload = {
                "uuid": args.class_type,
                "name": subgraph.get("name"),
                "inputs": subgraph.get("inputs") or [],
                "outputs": subgraph.get("outputs") or [],
                "inner_node_count": len(subgraph.get("nodes") or []),
                "inner_node_class_types": dict(sorted(class_counts.items())),
                "inner_graph": {"edges": subgraph.get("links") or []},
                "source": str(path),
            }
            return emit(payload, json=getattr(args, "json", False), text_renderer=lambda data: data["name"] or data["uuid"])
    print(f"subgraph UUID not found: {args.class_type}", file=sys.stderr)
    return 1


def _cmd_nodes_install_plan(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(args.path, schema_provider=schema_provider, allow_scratchpad=True)
    try:
        missing_classes = node_packs_install.missing_class_types_for_workflow(workflow)
        packs, unresolved = node_packs_install.missing_packs_for_workflow(workflow)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = build_nodes_install_plan_payload(args.path, missing_classes, packs, unresolved)
    return _print_install_plan(payload, json_output=args.json)


def build_nodes_install_plan_payload(path: str, missing_classes, packs, unresolved) -> dict[str, object]:
    return {
        "path": path,
        "packs": [
            {
                "name": pack.name,
                "repo": pack.repo,
                "pip_packages": list(pack.pip_packages),
                "classes": sorted(missing_classes & pack.classes),
            }
            for pack in packs
        ],
        "unresolved_class_types": unresolved,
        "missing_class_types": sorted(missing_classes),
    }


def _print_install_plan(payload: dict[str, object], *, json_output: bool) -> int:
    packs = payload["packs"]
    unresolved = payload["unresolved_class_types"]
    missing_classes = payload["missing_class_types"]
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if unresolved else 0
    if not missing_classes:
        print("No missing custom node classes detected from local node_index.json.")
        return 0
    if packs:
        print("Suggested custom node packs:")
        for pack in packs:
            classes = ", ".join(pack["classes"])
            packages = f" (pip: {', '.join(pack['pip_packages'])})" if pack["pip_packages"] else ""
            print(f"- {pack['name']}: {pack['repo']}{packages}")
            print(f"  classes: {classes}")
    if unresolved:
        print("Unmapped node classes:")
        for class_type in unresolved:
            print(f"- {class_type}")
        return 1
    return 0


def _cmd_nodes_install(args: argparse.Namespace) -> int:
    try:
        result = node_packs_install.install_pack(name=args.name, repo=args.repo, force=args.force)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
    print(f"{result.name}: {result.status}{detail}")
    if result.error:
        print(result.error, file=sys.stderr)
    return 0 if result.status in {"installed", "refreshed"} else 1


def _cmd_nodes_lookup(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_pack(args.query)
    except PackResolverError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = {
        "query": resolution.query,
        "query_type": resolution.query_type,
        "pack": resolution.ref.to_dict(),
        "candidates": [candidate.to_dict() for candidate in resolution.candidates],
        "cache_hit": resolution.cache_hit,
        "endpoint": resolution.endpoint,
    }
    return emit(payload, json=args.json, text_renderer=lambda data: data["pack"]["slug"])


def _cmd_nodes_refresh_template(args: argparse.Namespace) -> int:
    path = Path(args.file)
    original = path.read_text(encoding="utf-8")
    workflow = load_workflow_reference(str(path), allow_scratchpad=True)
    classes = {str(node.class_type) for node in workflow.nodes.values()}
    refs = []
    for entry in read_lockfile():
        class_set = set(getattr(entry, "class_set", ()) or ())
        if classes & class_set:
            refs.append(entry)
    slugs = sorted({getattr(entry, "slug", None) or entry.name for entry in refs})
    replacement = original
    if "custom_node_refs=" not in replacement:
        marker = "    output_prefix="
        insert = f"    custom_node_refs={slugs!r},\n"
        lines = replacement.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.startswith(marker):
                lines.insert(index + 1, insert)
                replacement = "".join(lines)
                break
    diff = "".join(difflib.unified_diff(original.splitlines(True), replacement.splitlines(True), fromfile=str(path), tofile=str(path)))
    status = "dry-run" if args.dry_run else "updated"
    if not args.dry_run:
        path.write_text(replacement, encoding="utf-8")
    payload = {"status": status, "custom_nodes": slugs, "diff": diff if args.diff else ""}
    return emit(payload, json=args.json, text_renderer=lambda data: data["status"])


def _cmd_nodes_ensure(args: argparse.Namespace) -> int:
    path = args.template or args.workflow
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(path, schema_provider=schema_provider, allow_scratchpad=True)
    try:
        missing_classes = node_packs_install.missing_class_types_for_workflow(workflow)
        packs, unresolved = node_packs_install.missing_packs_for_workflow(workflow)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.dry_run:
        payload = build_nodes_install_plan_payload(path, missing_classes, packs, unresolved)
        return _print_install_plan(payload, json_output=False)
    if not missing_classes:
        print("No missing custom node classes detected from local node_index.json.")
        return 0
    if unresolved:
        print("Unmapped node classes:")
        for class_type in unresolved:
            print(f"- {class_type}")
        return 1
    for pack in packs:
        result = node_packs_install.install_pack(name=pack.name)
        detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
        print(f"{result.name}: {result.status}{detail}")
        if result.error:
            print(result.error, file=sys.stderr)
        if result.status not in {"installed", "refreshed"}:
            return 1
    print(
        "Nodepacks installed/refreshed. If a vibecomfy session is active, "
        "call session.reload_for_nodepack_change(...) or restart it."
    )
    return 0


def _cmd_nodes_lock(args: argparse.Namespace) -> int:
    lockfile_path = Path(getattr(args, "path", "custom_nodes.lock"))
    entries = read_lockfile(lockfile_path)
    locked: list[LockEntry] = []
    for entry in entries:
        pack_dir = _installed_nodepack_dir(entry.name)
        git_commit_sha = entry.git_commit_sha
        if entry.semantic_label and pack_dir is not None:
            git_commit_sha = _git_head(pack_dir) or git_commit_sha
        source_sha256 = dict(entry.source_sha256)
        if getattr(args, "with_source_sha256", False) and pack_dir is not None:
            source_sha256 = _source_sha256(pack_dir)
        locked.append(
            LockEntry(
                name=entry.name,
                git_commit_sha=git_commit_sha,
                url=entry.url,
                semantic_label=entry.semantic_label,
                source_sha256=source_sha256,
            )
        )
    write_lockfile(locked, lockfile_path)
    print(f"Wrote {lockfile_path} ({len(locked)} nodepacks)")
    return 0


def _cmd_nodes_restore(args: argparse.Namespace) -> int:
    entries = read_lockfile(Path(args.lockfile))
    ok = True
    for entry in entries:
        result = node_packs_install.restore_pack(entry)
        detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
        print(f"{result.name}: {result.status}{detail}")
        if result.error:
            print(result.error, file=sys.stderr)
        ok = ok and result.status in {"installed", "refreshed"}
    return 0 if ok else 1


def _installed_nodepack_dir(name: str) -> Path | None:
    candidate = node_packs_install.DEFAULT_INSTALL_ROOT / name
    return candidate if candidate.is_dir() else None


def _git_head(pack_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _source_sha256(pack_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for source in sorted(pack_dir.rglob("*.py")):
        if ".git" in source.parts:
            continue
        rel = source.relative_to(pack_dir).as_posix()
        hashes[rel] = hashlib.sha256(source.read_bytes()).hexdigest()
    return hashes


def _cmd_nodes_coverage(args: argparse.Namespace) -> int:
    """Schema completeness report for a workflow's class types."""
    schema_provider = get_schema_provider("auto")
    try:
        loaded = load_port_source(args.workflow, schema_provider=schema_provider)
    except Exception as exc:
        print(f"Failed to load workflow: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    lock_path = Path(args.lockfile) if getattr(args, "lockfile", None) else Path("custom_nodes.lock")
    coverage = build_workflow_coverage(
        loaded.workflow,
        schema_provider=schema_provider,
        lock_path=lock_path,
    )
    if args.json:
        print(json.dumps(coverage.to_json(), indent=2, sort_keys=True))
    else:
        print(_format_coverage(coverage))
    return 0


def _format_coverage(coverage) -> str:
    lines = []
    for entry in coverage.per_class:
        icon = {"typed_wrapper": "✅ typed wrapper", "raw_call": "⚡ raw_call", "missing_lock": "❌ missing_lock"}.get(
            entry["coverage"], f"? {entry['coverage']}"
        )
        lines.append(f"{entry['class_type']:40s} {entry['pack']:30s} {icon}")
    lines.append("")
    lines.append(f"Coverage: {coverage.typed_wrapper}/{coverage.total} ({coverage.to_json()['coverage_pct']}%)")
    lines.append(f"Falls through to raw_call: {coverage.raw_call}")
    lines.append(f"Missing from custom_nodes.lock: {coverage.missing_lock}")
    return "\n".join(lines)


def _cmd_nodes_drift(args: argparse.Namespace) -> int:
    """Schema-drift detector for a custom-node pack."""
    pack_name: str = args.pack
    from_ref: str | None = getattr(args, "from_ref", None)
    to_ref: str | None = getattr(args, "to_ref", None)

    # Resolve pack dir
    pack_dir = node_packs_install.DEFAULT_INSTALL_ROOT / pack_name
    if not pack_dir.is_dir():
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "message": f"Pack directory not found: {pack_dir}. Install the pack first with `vibecomfy nodes install {pack_name}`.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Pack unavailable: {pack_name}")
            print(f"  Directory not found: {pack_dir}")
            print(f"  Install with: vibecomfy nodes install {pack_name}")
        return 0

    # Check git
    if not (pack_dir / ".git").is_dir():
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "message": f"Pack directory {pack_dir} is not a git repository.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Pack unavailable: {pack_name}")
            print(f"  {pack_dir} is not a git repository")
        return 0

    # Resolve refs
    if from_ref is None:
        from_ref = "HEAD~1"
    if to_ref is None:
        to_ref = "HEAD"

    # Get schema snapshots
    from_python = _extract_pack_python_api(pack_dir, from_ref)
    to_python = _extract_pack_python_api(pack_dir, to_ref)

    if from_python is None or to_python is None:
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "from_ref": from_ref,
            "to_ref": to_ref,
            "message": "Could not extract Python API from one or both refs.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Schema diff unavailable for {pack_name}: {from_ref}..{to_ref}")
        return 0

    # Diff classes
    from_classes = _parse_class_defs(from_python)
    to_classes = _parse_class_defs(to_python)

    added = set(to_classes) - set(from_classes)
    removed = set(from_classes) - set(to_classes)
    modified: list[dict[str, Any]] = []

    for cls_name in set(from_classes) & set(to_classes):
        if from_classes[cls_name] != to_classes[cls_name]:
            modified.append({
                "class": cls_name,
                "from_inputs": from_classes[cls_name],
                "to_inputs": to_classes[cls_name],
            })

    # Find affected templates
    affected_templates: list[str] = []
    all_modified_classes = {m["class"] for m in modified} | added | removed
    if all_modified_classes:
        try:
            snapshot = build_corpus_snapshot()
            for tpl in snapshot.templates_list:
                tpl_path = Path(tpl["path"])
                if tpl_path.is_file():
                    source = tpl_path.read_text(encoding="utf-8")
                    for ct in all_modified_classes:
                        if f"'{ct}'" in source or f'"{ct}"' in source:
                            affected_templates.append(tpl["id"])
                            break
        except Exception:
            pass

    payload = {
        "pack": pack_name,
        "from_ref": from_ref,
        "to_ref": to_ref,
        "added_classes": sorted(added),
        "removed_classes": sorted(removed),
        "modified_classes": modified,
        "affected_templates": sorted(set(affected_templates)),
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Schema diff: {pack_name} {from_ref}..{to_ref}")
        print(f"Added classes: {sorted(added) if added else '(none)'}")
        print(f"Removed classes: {sorted(removed) if removed else '(none)'}")
        if modified:
            print("Modified classes:")
            for m in modified:
                print(f"  {m['class']}: inputs changed")
        else:
            print("Modified classes: (none)")
        if affected_templates:
            print(f"\nAffected templates (use modified classes):")
            for tid in sorted(set(affected_templates)):
                print(f"  {tid}")
        else:
            print("\nAffected templates: (none)")
    return 0


def _extract_pack_python_api(pack_dir: Path, ref: str) -> str | None:
    """Extract combined Python source from all .py files at a git ref."""
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "ls-tree", "-r", "--name-only", ref],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    py_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]
    if not py_files:
        return None

    combined: list[str] = []
    for py_file in py_files[:50]:  # limit to prevent huge output
        try:
            r = subprocess.run(
                ["git", "-C", str(pack_dir), "show", f"{ref}:{py_file}"],
                check=True,
                capture_output=True,
                text=True,
            )
            combined.append(r.stdout)
        except (OSError, subprocess.CalledProcessError):
            continue

    return "\n".join(combined) if combined else None


def _parse_class_defs(source: str) -> dict[str, dict[str, Any]]:
    """Parse INPUT_TYPES-like class definitions from Python source."""
    classes: dict[str, dict[str, Any]] = {}
    # Find class definitions and their INPUT_TYPES
    class_pattern = re.compile(r"class\s+(\w+)\s*[:\(]")
    inputs_pattern = re.compile(r"INPUT_TYPES\s*\(\s*\)\s*:\s*\n?\s*return\s*\{[^}]*\}")

    for cls_match in class_pattern.finditer(source):
        cls_name = cls_match.group(1)
        # Try to find INPUT_TYPES after the class
        rest = source[cls_match.end():]
        next_class = class_pattern.search(rest)
        section = rest[:next_class.start()] if next_class else rest

        # Extract required inputs
        required = re.findall(r'"required"\s*:\s*\{([^}]*)\}', section, re.DOTALL)
        if required:
            classes[cls_name] = {"has_required_inputs": True}
        else:
            classes[cls_name] = {"has_required_inputs": False}

    return classes


def _build_nodes_audit_payload(args: argparse.Namespace) -> dict[str, object]:
    """Build the audit payload dict without printing — shared by audit + reconcile."""
    from vibecomfy.commands.port import build_port_check_payload

    port_args = argparse.Namespace(
        workflow=args.workflow,
        json=True,
        head_check_models=getattr(args, "head_check_models", False),
        strict_ready_template=getattr(args, "strict_ready_template", False),
        runtime_object_info=False,
        object_info_cache=getattr(args, "object_info_cache", None),
        no_object_info_cache=False,
        server_url=None,
    )
    try:
        payload, report = build_port_check_payload(port_args)
    except Exception as exc:
        return {
            "audit_version": "1.0.0",
            "workflow": args.workflow,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }

    schema_provider = get_schema_provider("auto")
    try:
        workflow = load_workflow_reference(
            args.workflow, schema_provider=schema_provider, allow_scratchpad=True
        )
        _packs, _unresolved = node_packs_install.missing_packs_for_workflow(workflow)
    except (FileNotFoundError, ValueError):
        _packs, _unresolved = [], []

    _installed_pack_classes: set[str] = set()
    for pack in _packs:
        _installed_pack_classes |= set(pack.classes)
    _all_known_classes: set[str] = set()
    for pack in KNOWN_NODE_PACKS:
        _all_known_classes |= set(pack.classes)

    error_diagnostics = [d for d in payload.get("diagnostics", []) if d.get("severity") == "error"]
    classified: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()

    for diag in error_diagnostics:
        class_type = str(diag.get("class_type") or "")
        code = str(diag.get("code", ""))
        node_id = str(diag.get("node_id") or "")
        message = str(diag.get("message", ""))

        dedup_key = (class_type, code)
        if dedup_key in seen_keys and class_type:
            continue
        if class_type:
            seen_keys.add(dedup_key)

        bucket, rationale, pack_name = _classify_diagnostic(
            class_type=class_type,
            code=code,
            node_id=node_id,
            message=message,
            installed_pack_classes=_installed_pack_classes,
            all_known_classes=_all_known_classes,
            schema_provider=schema_provider,
            payload=payload,
        )
        classified.append(
            {
                "class_type": class_type or None,
                "node_id": node_id or None,
                "code": code,
                "classification": bucket,
                "rationale": rationale,
                "pack": pack_name,
            }
        )

    custom_analysis = payload.get("metadata", {}).get("custom_node_analysis", {})
    missing_classes = set(custom_analysis.get("missing_runtime_class_types", []))
    for class_type in sorted(missing_classes):
        dedup_key = (class_type, "unresolved_runtime_class")
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        bucket, rationale, pack_name = _classify_diagnostic(
            class_type=class_type,
            code="unresolved_runtime_class",
            node_id="",
            message=f"unknown class: {class_type}",
            installed_pack_classes=_installed_pack_classes,
            all_known_classes=_all_known_classes,
            schema_provider=schema_provider,
            payload=payload,
        )
        classified.append(
            {
                "class_type": class_type,
                "node_id": None,
                "code": "unresolved_runtime_class",
                "classification": bucket,
                "rationale": rationale,
                "pack": pack_name,
            }
        )

    return {
        "audit_version": "1.0.0",
        "workflow": args.workflow,
        "source_hash": payload.get("source_hash"),
        "total_classified": len(classified),
        "classifications": classified,
        "summary": {
            "pack-not-installed": sum(
                1 for c in classified if c["classification"] == "pack-not-installed"
            ),
            "pack-installed-but-stale-schema": sum(
                1 for c in classified if c["classification"] == "pack-installed-but-stale-schema"
            ),
            "widget-alias-missing": sum(
                1 for c in classified if c["classification"] == "widget-alias-missing"
            ),
            "model-registry-gap": sum(
                1 for c in classified if c["classification"] == "model-registry-gap"
            ),
            "community-node-unknown": sum(
                1 for c in classified if c["classification"] == "community-node-unknown"
            ),
        },
    }


def _cmd_nodes_audit(args: argparse.Namespace) -> int:
    """Audit unresolved nodes in a workflow and classify each into a resolution bucket.

    Runs the existing port-check pipeline and classifies every error-level
    diagnostic into exactly one of five categories, reusing install-plan pack
    resolution and schema-index lookups — no new discovery mechanism.
    """
    audit_payload = _build_nodes_audit_payload(args)
    if audit_payload.get("status") == "error":
        if args.json:
            print(json.dumps(audit_payload, indent=2, sort_keys=True))
        else:
            print(f"nodes audit failed: {audit_payload.get('error')}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(audit_payload, indent=2, sort_keys=True))
    else:
        _print_audit_text(audit_payload)
    return 1 if audit_payload.get("classifications", []) else 0


def _classify_diagnostic(
    *,
    class_type: str,
    code: str,
    node_id: str,
    message: str,
    installed_pack_classes: set[str],
    all_known_classes: set[str],
    schema_provider: object,
    payload: dict[str, object],
) -> tuple[str, str, str | None]:
    """Classify a single diagnostic into one of five buckets.

    Returns (bucket, rationale, pack_name_or_none).
    """
    # --- widget-alias-missing --------------------------------------------
    if code in ("widget_alias_unresolved", "compiled_widget_input_missing", "unknown_input"):
        return (
            "widget-alias-missing",
            f"Widget alias or input resolution gap for {class_type or node_id}: {message}",
            None,
        )

    # --- model-registry-gap ----------------------------------------------
    if code in ("value_not_in_enum",):
        return (
            "model-registry-gap",
            f"Model enum gap for {class_type or node_id}: {message}",
            None,
        )

    # Model-related diagnostics (asset analysis)
    if "model" in code.lower() or "model" in message.lower():
        for asset_code in (
            "missing_model_url",
            "unreachable_model_url",
            "model_asset_unknown",
            "ltx_audio_vae_wrong_loader",
        ):
            if code == asset_code or asset_code in code:
                return (
                    "model-registry-gap",
                    f"Model asset gap for {class_type or node_id}: {message}",
                    None,
                )

    # --- class-type resolution -------------------------------------------
    if code in ("unresolved_runtime_class", "unknown_class_type", "opaque_component_class_type",
                 "opaque_component_node_class", "unmaterialized_node_class") or (
        not class_type and code in ("api_compile_failed",)
    ):
        if not class_type:
            return (
                "community-node-unknown",
                f"No class type for diagnostic {code}: {message}",
                None,
            )

        # 1. Check if class is in any known pack
        matching_packs = resolve_node_packs({class_type})
        if matching_packs:
            pack_name = matching_packs[0].name
            if class_type in installed_pack_classes:
                return (
                    "pack-installed-but-stale-schema",
                    f"Class {class_type!r} is in pack {pack_name!r} (installed) but schema is missing or stale.",
                    pack_name,
                )
            return (
                "pack-not-installed",
                f"Class {class_type!r} is in pack {pack_name!r} but the pack is not installed.",
                pack_name,
            )

        # 2. Check if class has a schema entry
        try:
            schema = schema_for(schema_provider, class_type)
        except Exception:
            schema = None
        if schema is not None:
            # Has schema — check for widget / model sub-issues
            widget_diags = [
                d for d in payload.get("diagnostics", [])
                if d.get("class_type") == class_type
                and d.get("code") in ("widget_alias_unresolved", "compiled_widget_input_missing", "unknown_input")
            ]
            model_diags = [
                d for d in payload.get("diagnostics", [])
                if d.get("class_type") == class_type
                and d.get("code") in ("value_not_in_enum",)
            ]
            if widget_diags:
                return (
                    "widget-alias-missing",
                    f"Class {class_type!r} has schema but widget aliases are unresolved.",
                    None,
                )
            if model_diags:
                return (
                    "model-registry-gap",
                    f"Class {class_type!r} has schema but model enum values are missing.",
                    None,
                )
            return (
                "pack-installed-but-stale-schema",
                f"Class {class_type!r} has a schema entry but is still flagged as unresolved — schema may be stale.",
                None,
            )

        # 3. Completely unknown
        return (
            "community-node-unknown",
            f"Class {class_type!r} is not found in any known pack or schema registry.",
            None,
        )

    # --- environment / template-shape diagnostics (not node resolution) ---
    if code.startswith("strict_ready_") or code in (
        "headless_preview_override_not_supported",
        "optional_acceleration_requires_unavailable_package",
        "metadata_environment_warning",
    ):
        return (
            "community-node-unknown",
            f"Environment or template shape issue: {message}",
            None,
        )

    # --- fallback for unrecognised codes ---------------------------------
    if class_type:
        return (
            "community-node-unknown",
            f"Unclassified diagnostic {code!r} for {class_type!r}: {message}",
            None,
        )
    return (
        "community-node-unknown",
        f"Unclassified diagnostic {code!r}: {message}",
        None,
    )


def _print_audit_text(audit_payload: dict[str, object]) -> None:
    """Text renderer for ``nodes audit`` output."""
    summary = audit_payload.get("summary", {})
    classifications = audit_payload.get("classifications", [])
    if isinstance(classifications, list):
        print(f"nodes audit: {audit_payload.get('workflow')}")
        print(f"  source_hash: {audit_payload.get('source_hash')}")
        print(f"  total classified: {audit_payload.get('total_classified')}")
        print()
        for bucket in (
            "pack-not-installed",
            "pack-installed-but-stale-schema",
            "widget-alias-missing",
            "model-registry-gap",
            "community-node-unknown",
        ):
            count = summary.get(bucket, 0) if isinstance(summary, dict) else 0
            print(f"  {bucket}: {count}")
        print()
        for item in classifications:
            if isinstance(item, dict):
                print(
                    f"  [{item.get('classification')}] {item.get('class_type') or item.get('node_id')}"
                )
                print(f"    {item.get('rationale')}")


def _cmd_nodes_reconcile(args: argparse.Namespace) -> int:
    """Propose remediations for each audit classification row — no mutation.

    Runs the audit pipeline, then maps every classification to a durable
    remediation action whose detail strings reference only verified-existing
    CLI commands or concrete file-edit locations.
    """
    from vibecomfy.node_packs import _STATIC_NODE_PACKS as static_packs

    audit_payload = _build_nodes_audit_payload(args)
    if audit_payload.get("status") == "error":
        reconcile_payload: dict[str, object] = {
            "reconcile_version": "1.0.0",
            "workflow": args.workflow,
            "status": "error",
            "error": audit_payload.get("error"),
        }
        if args.json:
            print(json.dumps(reconcile_payload, indent=2, sort_keys=True))
        else:
            print(f"nodes reconcile failed: {audit_payload.get('error')}", file=sys.stderr)
        return 1

    static_pack_names = {pack.name for pack in static_packs}

    classifications = audit_payload.get("classifications", [])
    if not isinstance(classifications, list):
        classifications = []

    remediations: list[dict[str, object]] = []

    for row in classifications:
        if not isinstance(row, dict):
            continue
        bucket = str(row.get("classification", ""))
        class_type = str(row.get("class_type") or "")
        code = str(row.get("code", ""))
        rationale = str(row.get("rationale", ""))
        pack_name = str(row.get("pack") or "")
        message = rationale  # fallback detail source

        remediation = _build_remediation(
            bucket=bucket,
            class_type=class_type,
            code=code,
            message=message,
            pack_name=pack_name,
            static_pack_names=static_pack_names,
            workflow_path=args.workflow,
        )
        remediation["classification"] = bucket
        remediation["class_type"] = class_type or None
        remediation["code"] = code
        remediations.append(remediation)

    reconcile_payload = {
        "reconcile_version": "1.0.0",
        "workflow": args.workflow,
        "source_hash": audit_payload.get("source_hash"),
        "total_remediations": len(remediations),
        "remediations": remediations,
        "summary": {
            "declare-pack": sum(1 for r in remediations if r.get("action") == "declare-pack"),
            "install-pack": sum(1 for r in remediations if r.get("action") == "install-pack"),
            "refresh-schema": sum(1 for r in remediations if r.get("action") == "refresh-schema"),
            "register-widget-alias": sum(1 for r in remediations if r.get("action") == "register-widget-alias"),
            "register-model": sum(1 for r in remediations if r.get("action") == "register-model"),
            "defer-as-out-of-scope": sum(1 for r in remediations if r.get("action") == "defer-as-out-of-scope"),
        },
    }

    if args.json:
        print(json.dumps(reconcile_payload, indent=2, sort_keys=True))
    else:
        _print_reconcile_text(reconcile_payload)

    return 0


def _build_remediation(
    *,
    bucket: str,
    class_type: str,
    code: str,
    message: str,
    pack_name: str,
    static_pack_names: set[str],
    workflow_path: str,
) -> dict[str, object]:
    """Map an audit classification bucket to a structured remediation action.

    Every ``detail`` string references only verified-existing CLI commands
    (``vibecomfy nodes install``, ``vibecomfy nodes refresh-template``) or
    concrete file-edit locations (``vibecomfy/node_packs.py``,
    ``vibecomfy/registry/models.yaml``, the ``widget_aliases`` module).
    No phantom subcommands are ever emitted.
    """
    if bucket == "pack-not-installed":
        if pack_name and pack_name in static_pack_names:
            return {
                "action": "install-pack",
                "detail": f"vibecomfy nodes install {pack_name}",
                "pack": pack_name,
            }
        elif pack_name:
            return {
                "action": "declare-pack",
                "detail": f"add CustomNodePack entry in vibecomfy/node_packs.py for {pack_name}",
                "pack": pack_name,
            }
        else:
            return {
                "action": "declare-pack",
                "detail": "add CustomNodePack entry in vibecomfy/node_packs.py",
                "pack": None,
            }

    if bucket == "pack-installed-but-stale-schema":
        return {
            "action": "refresh-schema",
            "detail": f"vibecomfy nodes refresh-template {workflow_path}",
            "pack": pack_name or None,
        }

    if bucket == "widget-alias-missing":
        # Extract widget_N info from the message if possible
        widget_ref = _extract_widget_ref(class_type, message)
        return {
            "action": "register-widget-alias",
            "detail": f"add {widget_ref} mapping in the widget_aliases module",
            "pack": None,
        }

    if bucket == "model-registry-gap":
        return {
            "action": "register-model",
            "detail": "add enum entry in vibecomfy/registry/models.yaml",
            "pack": None,
        }

    # community-node-unknown or anything else
    return {
        "action": "defer-as-out-of-scope",
        "detail": "community-node-unknown; document exception",
        "pack": None,
    }


def _extract_widget_ref(class_type: str, message: str) -> str:
    """Extract a human-readable ``<class>.<widget_N>`` reference from a rationale message."""
    import re as _re

    # Try to find widget_N or unknown_input references
    widget_match = _re.search(r"widget_\d+", message)
    if widget_match:
        widget_id = widget_match.group(0)
        if class_type:
            return f"{class_type}.{widget_id}->field"
        return f"{widget_id}->field"

    if class_type:
        return f"{class_type}.<unknown_widget>->field"
    return "<unknown_class>.<unknown_widget>->field"


def _print_reconcile_text(payload: dict[str, object]) -> None:
    """Text renderer for ``nodes reconcile`` output."""
    summary = payload.get("summary", {})
    remediations = payload.get("remediations", [])
    if isinstance(remediations, list):
        print(f"nodes reconcile: {payload.get('workflow')}")
        print(f"  source_hash: {payload.get('source_hash')}")
        print(f"  total remediations: {payload.get('total_remediations')}")
        print()
        for action in (
            "declare-pack",
            "install-pack",
            "refresh-schema",
            "register-widget-alias",
            "register-model",
            "defer-as-out-of-scope",
        ):
            count = summary.get(action, 0) if isinstance(summary, dict) else 0
            print(f"  {action}: {count}")
        print()
        for item in remediations:
            if isinstance(item, dict):
                print(
                    f"  [{item.get('action')}] {item.get('class_type') or '(no class)'}"
                )
                print(f"    {item.get('detail')}")


def register(subparsers) -> None:
    nodes = subparsers.add_parser("nodes")
    nodes_sub = nodes.add_subparsers(dest="subcmd", required=True)
    nodes_list = nodes_sub.add_parser("list")
    nodes_list.add_argument("--limit", type=int, default=200)
    nodes_list.add_argument("--json", action="store_true")
    nodes_list.set_defaults(func=_cmd_nodes_list)
    nodes_spec = nodes_sub.add_parser("spec")
    nodes_spec.add_argument("class_type")
    nodes_spec.add_argument(
        "--object-info-cache",
        help="Use a captured ComfyUI /object_info JSON file, for example one fetched from a RunPod runtime.",
    )
    nodes_spec.set_defaults(func=_cmd_nodes_spec)
    nodes_compatible = nodes_sub.add_parser("compatible-with", help="Find or check schema socket compatibility.")
    nodes_compatible.add_argument("type_or_from_class")
    nodes_compatible.add_argument("to_class", nargs="?")
    nodes_compatible.add_argument("to_input", nargs="?")
    nodes_compatible.add_argument("--as", dest="socket_role", choices=("input", "output"), default="output")
    nodes_compatible.add_argument("--from-output", default="0")
    nodes_compatible.add_argument("--object-info-cache")
    nodes_compatible.add_argument("--json", action="store_true")
    nodes_compatible.set_defaults(func=_cmd_nodes_compatible_with)
    nodes_install = nodes_sub.add_parser("install-plan")
    nodes_install.add_argument("path")
    nodes_install.add_argument("--json", action="store_true")
    nodes_install.set_defaults(func=_cmd_nodes_install_plan)
    nodes_install_pack = nodes_sub.add_parser("install")
    nodes_install_pack.add_argument("name", nargs="?")
    nodes_install_pack.add_argument("--repo")
    nodes_install_pack.add_argument("--force", action="store_true", default=False)
    nodes_install_pack.set_defaults(func=_cmd_nodes_install)
    nodes_lookup = nodes_sub.add_parser("lookup")
    nodes_lookup.add_argument("query")
    nodes_lookup.add_argument("--json", action="store_true")
    nodes_lookup.set_defaults(func=_cmd_nodes_lookup)
    nodes_refresh = nodes_sub.add_parser("refresh-template")
    nodes_refresh.add_argument("file")
    nodes_refresh.add_argument("--dry-run", action="store_true")
    nodes_refresh.add_argument("--diff", action="store_true")
    nodes_refresh.add_argument("--json", action="store_true")
    nodes_refresh.set_defaults(func=_cmd_nodes_refresh_template)
    nodes_ensure = nodes_sub.add_parser("ensure")
    ensure_source = nodes_ensure.add_mutually_exclusive_group(required=True)
    ensure_source.add_argument("--template")
    ensure_source.add_argument("--workflow")
    nodes_ensure.add_argument("--dry-run", action="store_true")
    nodes_ensure.set_defaults(func=_cmd_nodes_ensure)
    nodes_lock = nodes_sub.add_parser("lock")
    nodes_lock.add_argument("--path", default="custom_nodes.lock")
    nodes_lock.add_argument("--with-source-sha256", action="store_true", default=False)
    nodes_lock.set_defaults(func=_cmd_nodes_lock)
    nodes_restore = nodes_sub.add_parser("restore")
    nodes_restore.add_argument("--lockfile", default="custom_nodes.lock")
    nodes_restore.set_defaults(func=_cmd_nodes_restore)

    nodes_coverage = nodes_sub.add_parser("coverage", help="Schema completeness report for a workflow's class types.")
    nodes_coverage.add_argument("workflow")
    nodes_coverage.add_argument("--json", action="store_true")
    nodes_coverage.add_argument("--lockfile", default="custom_nodes.lock", help="Path to custom_nodes.lock")
    nodes_coverage.set_defaults(func=_cmd_nodes_coverage)

    nodes_drift = nodes_sub.add_parser("drift", help="Schema-drift detector for a custom-node pack.")
    nodes_drift.add_argument("pack", help="Custom node pack name (e.g. ComfyUI-KJNodes)")
    nodes_drift.add_argument("--from", dest="from_ref", help="Source git ref (default: HEAD~1)")
    nodes_drift.add_argument("--to", dest="to_ref", help="Target git ref (default: HEAD)")
    nodes_drift.add_argument("--json", action="store_true")
    nodes_drift.set_defaults(func=_cmd_nodes_drift)

    nodes_audit = nodes_sub.add_parser("audit", help="Audit unresolved nodes in a workflow and classify into resolution buckets.")
    nodes_audit.add_argument("--workflow", required=True, help="Path to workflow JSON, scratchpad .py, or ready-template id (e.g. image/z_image).")
    nodes_audit.add_argument("--json", action="store_true")
    nodes_audit.add_argument("--object-info-cache")
    nodes_audit.add_argument("--strict-ready-template", action="store_true", default=False)
    nodes_audit.add_argument("--head-check-models", action="store_true", default=False)
    nodes_audit.set_defaults(func=_cmd_nodes_audit)

    nodes_reconcile = nodes_sub.add_parser("reconcile", help="Propose remediations for each audit classification row — no mutation.")
    nodes_reconcile.add_argument("--workflow", required=True, help="Path to workflow JSON, scratchpad .py, or ready-template id (e.g. image/z_image).")
    nodes_reconcile.add_argument("--json", action="store_true")
    nodes_reconcile.add_argument("--object-info-cache")
    nodes_reconcile.add_argument("--strict-ready-template", action="store_true", default=False)
    nodes_reconcile.add_argument("--head-check-models", action="store_true", default=False)
    nodes_reconcile.set_defaults(func=_cmd_nodes_reconcile)
