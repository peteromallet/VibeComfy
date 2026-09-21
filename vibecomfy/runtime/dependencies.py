"""Typed workflow runtime declarations and read-only compatibility checks.

The declaration is deliberately a small description, not a lockfile or solver.
It records the execution target a workflow was tested with and lets callers
compare that target before queueing. Installation remains owned by the
existing preparation seams.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from vibecomfy.contracts.runtime import RuntimeDependencyError, RuntimeRequirements


def inspect_external_runtime(server_url: str) -> dict[str, Any]:
    """Observe the server, never the CLI interpreter or its storage directory.

    Comfy only reports a subset of installed packages. An absent package in
    this response is unknown, not evidence that the server lacks it.
    """
    actual: dict[str, Any] = {
        "target_kind": "external", "managed": False,
        "evidence_source": "system_stats", "server_url": server_url,
        "packages_complete": False,
    }
    try:
        with urllib.request.urlopen(f"{server_url.rstrip('/')}/system_stats", timeout=2) as response:
            payload = json.load(response)
        system = payload["system"]
        if not isinstance(system, Mapping):
            raise ValueError("system_stats.system must be an object")
        packages = {
            row["name"]: row["installed"]
            for row in system.get("comfy_package_versions", [])
            if isinstance(row, Mapping) and row.get("name") and row.get("installed")
        }
        if system.get("pytorch_version"):
            packages["torch"] = system["pytorch_version"]
        argv = system.get("argv")
        argv = list(argv) if isinstance(argv, list) and all(isinstance(x, str) for x in argv) else None
        actual.update(
            comfy_version=system.get("comfyui_version"),
            comfy_commit=system.get("comfyui_commit"),
            python_version=str(system["python_version"]).split()[0] if system.get("python_version") else None,
            packages=packages, observed_argv=argv, launch_flags=argv,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        actual.update(target_probe="unverified", probe_error=str(exc))
    return actual


def normalize_runtime_requirements(
    runtime: RuntimeRequirements | Mapping[str, Any] | None,
    *,
    legacy_python_env: Mapping[str, Any] | None = None,
    legacy_comfy_commit: str | None = None,
) -> RuntimeRequirements | None:
    if isinstance(runtime, RuntimeRequirements):
        if legacy_python_env or legacy_comfy_commit:
            return RuntimeRequirements.from_dict(
                runtime.to_dict(),
                legacy_python_env=legacy_python_env,
                legacy_comfy_commit=legacy_comfy_commit,
            )
        return runtime
    return RuntimeRequirements.from_dict(
        runtime,
        legacy_python_env=legacy_python_env,
        legacy_comfy_commit=legacy_comfy_commit,
    )


def runtime_requirements_from_workflow(workflow: Any) -> RuntimeRequirements | None:
    requirements = getattr(workflow, "requirements", None)
    declared = getattr(requirements, "runtime", None)
    metadata = getattr(workflow, "metadata", {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    legacy_env = metadata.get("python_env")
    if legacy_env is not None and not isinstance(legacy_env, Mapping):
        raise RuntimeDependencyError("metadata.python_env must be a mapping")
    legacy_commit = metadata.get("comfy_commit")
    if legacy_commit is not None and not isinstance(legacy_commit, str):
        raise RuntimeDependencyError("metadata.comfy_commit must be a string")
    return normalize_runtime_requirements(
        declared,
        legacy_python_env=legacy_env,
        legacy_comfy_commit=legacy_commit,
    )


def inspect_runtime_target(
    *,
    runtime_root: str | Path | None = None,
    target: Mapping[str, Any] | None = None,
    python_executable: str | Path | None = None,
    package_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Read target facts without installing, importing custom nodes, or writing."""
    if target is not None:
        return {str(key): value for key, value in target.items()}
    explicit_executable = python_executable is not None
    executable = Path(python_executable) if explicit_executable else _managed_python(runtime_root)
    actual: dict[str, Any] = {
        "python_version": platform.python_version() if runtime_root is None else None,
        "packages": {} if runtime_root is None else None,
        # The caller's argv describes VibeComfy, not the Comfy process.
        "launch_flags": None,
    }
    observed_package_names = tuple(dict.fromkeys(("comfy", "comfyui", "torch", *(package_names or ()))))
    if executable is not None and executable.is_file():
        actual["python_executable"] = str(executable)
        try:
            completed = subprocess.run(
                [str(executable), "-c", _package_probe(observed_package_names)],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            payload = json.loads(completed.stdout)
            if isinstance(payload, Mapping):
                actual.update({"python_version": payload.get("python_version"), "packages": dict(payload.get("packages", {}))})
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            actual["target_probe"] = "unverified"
    elif runtime_root is None and not explicit_executable:
        actual["python_version"] = platform.python_version()
        actual["packages"] = {}
        for name in observed_package_names:
            try:
                actual["packages"][name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                pass
    else:
        # A managed root without its selected interpreter is not permission to
        # inspect the caller environment.  Keep the target explicitly
        # unverified so reuse fails closed for required material.
        actual["target_probe"] = "unverified"
    packages = actual.get("packages")
    actual["comfy_version"] = (
        packages.get("comfyui") or packages.get("comfy")
        if isinstance(packages, Mapping)
        else None
    )
    if runtime_root is not None:
        root = Path(runtime_root).expanduser().resolve(strict=False)
        actual["runtime_root"] = str(root)
        actual["comfy_commit"] = _comfyui_git_head_for_root(root)
    else:
        actual["comfy_commit"] = None
    return actual


def compare_runtime(
    requirements: RuntimeRequirements | Mapping[str, Any] | None,
    *,
    target: Mapping[str, Any] | None = None,
    runtime_root: str | Path | None = None,
    strict_external_launch_flags: bool = False,
) -> dict[str, Any]:
    """Compare a declaration with observed facts and return a JSON report."""
    if requirements is None:
        return {
            "declared": False,
            "ok": True,
            "status": "unverified",
            "checks": [],
            "mismatches": [],
            "warnings": [],
        }
    req = normalize_runtime_requirements(requirements)
    assert req is not None
    actual = inspect_runtime_target(
        runtime_root=runtime_root,
        target=target,
        package_names=[name for name, _constraint in req.packages],
    )
    external = actual.get("target_kind") == "external"
    if runtime_root is not None and not external:
        root = Path(runtime_root).expanduser().resolve(strict=False)
        if "models" not in actual:
            actual["models"] = _discover_models(root, req.models)
        if "custom_nodes" not in actual:
            actual["custom_nodes"] = _discover_custom_nodes(root)

    checks: list[dict[str, Any]] = []
    mismatches: list[str] = []

    def check(
        path: str,
        expected: Any,
        observed: Any,
        *,
        incompatible: bool = False,
        version_constraint: bool = False,
    ) -> None:
        if expected is None or expected in ((), {}, []):
            return
        if observed is None:
            status = "unverified"
        elif (version_constraint and _version_satisfies(str(observed), str(expected))) or observed == expected:
            status = "matching"
        else:
            status = "incompatible" if incompatible else "different"
        checks.append({
            "path": path,
            "expected": expected,
            "actual": observed,
            "status": status,
            "reason": {
                "matching": "observed value satisfies the declared requirement",
                "unverified": "target did not provide observable evidence",
                "different": "observed value differs from the declaration",
                "incompatible": "observed value violates the declaration",
            }.get(status, "dependency predicate was not satisfied"),
        })
        if status in {"different", "incompatible", "missing"}:
            mismatches.append(f"{path}: expected {expected!r}, actual {observed!r}")

    check("comfy_commit", req.comfy_commit, actual.get("comfy_commit"), incompatible=True)
    check("comfy_version", req.comfy_version, actual.get("comfy_version"), incompatible=True, version_constraint=True)
    check("python_version", req.python_version, actual.get("python_version"), incompatible=True, version_constraint=True)

    actual_packages = actual.get("packages") if isinstance(actual.get("packages"), Mapping) else {}
    for name, constraint in req.packages:
        observed = actual_packages.get(name)
        if observed is None:
            status = "missing" if isinstance(actual.get("packages"), Mapping) and actual.get("packages_complete", True) else "unverified"
        else:
            status = "matching" if _version_satisfies(str(observed), constraint) else "incompatible"
        checks.append({
            "path": f"packages.{name}",
            "expected": constraint,
            "actual": observed,
            "status": status,
            "reason": {
                "matching": "installed version satisfies the declared constraint",
                "missing": "target reported a complete package inventory without this package",
                "unverified": "target package inventory is incomplete or unavailable",
                "incompatible": "installed version violates the declared constraint",
            }.get(status, "package predicate was not satisfied"),
        })
        if status in {"missing", "incompatible"}:
            mismatches.append(f"packages.{name}: expected {constraint!r}, actual {observed!r}")

    if req.launch_flags:
        observed_flags = actual.get("launch_flags")
        if not isinstance(observed_flags, (list, tuple, set)):
            flag_status = "unverified"
        else:
            expected_flags = {str(flag) for flag in req.launch_flags}
            observed_flag_set = {str(flag) for flag in observed_flags}
            flag_status = "matching" if expected_flags <= observed_flag_set else "different"
        if flag_status == "different":
            if external:
                flag_status = "incompatible" if strict_external_launch_flags else "unverified"
            elif actual.get("managed") is True:
                flag_status = "incompatible"
        checks.append({
            "path": "launch_flags",
            "expected": list(req.launch_flags),
            "actual": observed_flags,
            "status": flag_status,
            "policy": "strict" if not external or strict_external_launch_flags else "external_observation",
            "reason": {
                "matching": "observed launch flags include every declared flag",
                "different": "observed launch flags do not include every declared flag",
                "incompatible": "managed or strict external target lacks declared launch flags",
                "unverified": "target did not provide an authoritative argv",
            }.get(flag_status, "launch flag predicate was not satisfied"),
        })
        if flag_status in {"different", "incompatible", "missing"}:
            mismatches.append(
                f"launch_flags: expected {list(req.launch_flags)!r}, actual {observed_flags!r}"
            )

    _compare_named_objects("models", req.models, actual.get("models"), checks, mismatches)
    _compare_named_objects("custom_nodes", req.custom_nodes, actual.get("custom_nodes"), checks, mismatches)
    statuses = {str(item["status"]) for item in checks}
    if not checks:
        status = "unverified"
    elif "missing" in statuses or "incompatible" in statuses:
        status = "incompatible"
    elif "different" in statuses:
        status = "different"
    elif "unverified" in statuses:
        status = "unverified"
    else:
        status = "matching"
    warnings = []
    if status != "matching":
        details = "; ".join(mismatches)
        if not details:
            details = "; ".join(
                f"{item['path']}: declared {item['expected']!r}, observed {item['actual']!r}"
                for item in checks if item.get("status") == "unverified"
            )
        warnings = [
            "Runtime dependency drift detected"
            + (f": {details}" if details else ".")
            + " Use --deps sync on a managed target or inspect the unverified fields before retrying."
        ]
    return {
        "declared": True,
        "ok": not ({"missing", "incompatible"} & statuses),
        "status": status,
        "compliance": (
            "compliant" if status == "matching"
            else "unverified" if status == "unverified"
            else "noncompliant"
        ),
        "checks": checks,
        "mismatches": mismatches,
        "warnings": warnings,
        "actual": actual,
        "declared_runtime": req.to_dict(),
    }


def sync_runtime(
    requirements: RuntimeRequirements | Mapping[str, Any] | None,
    *,
    runtime_root: str | Path | None = None,
    target: Mapping[str, Any] | None = None,
    offline: bool = False,
    installer: Callable[[list[str], bool], Any] | None = None,
    verify: Callable[[], Mapping[str, Any]] | None = None,
    launch_flags: Sequence[str] | None = None,
    sync_packages: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Synchronize selected declared packages through the existing pip seam.

    ``sync_packages`` scopes mutation; omitted means all mismatching declared
    packages.  The final report always rechecks the complete declaration.
    """
    req = normalize_runtime_requirements(requirements)
    if req is None:
        return {"declared": False, "ok": True, "status": "unverified", "checks": [], "mismatches": [], "warnings": [], "mode": "sync", "changes": [], "synced": False, "actions": []}
    managed_python = _managed_python(runtime_root)
    injected_test_target = target is not None and installer is not None
    if runtime_root is None and not injected_test_target:
        raise RuntimeDependencyError(
            "--deps sync requires an explicit VibeComfy-managed runtime_root"
        )
    root = Path(runtime_root).expanduser().resolve(strict=False) if runtime_root is not None else None
    if not injected_test_target and root is not None and not _managed_runtime_marker(root).is_file():
        raise RuntimeDependencyError(
            f"--deps sync requires a VibeComfy-managed runtime marker at {root / _MANAGED_MARKER}"
        )
    if managed_python is None and not injected_test_target:
        raise RuntimeDependencyError(
            "--deps sync requires an existing managed Python at runtime_root/.venv or runtime_root/venv"
        )
    declared_package_names = {
        str(name).casefold().replace("_", "-") for name, _constraint in req.packages
    }
    selected = (
        {str(name).casefold().replace("_", "-") for name in sync_packages}
        if sync_packages is not None
        else None
    )
    if selected is not None:
        unknown = sorted(selected - declared_package_names)
        if unknown:
            raise RuntimeDependencyError(
                "unknown runtime package(s) selected for synchronization: "
                + ", ".join(unknown)
                + "; choose from declared packages: "
                + (", ".join(sorted(declared_package_names)) or "<none>")
            )
    report = compare_runtime(req, target=target, runtime_root=runtime_root)
    if not report["declared"] or report["status"] == "matching":
        return {
            **report,
            "mode": "sync",
            "managed": {"runtime_root": str(root) if root is not None else None, "python_executable": str(managed_python) if managed_python is not None else None},
            "synced": False,
            "actions": [],
            "changes": [],
        }
    if offline:
        raise RuntimeDependencyError("runtime dependencies drifted and offline mode forbids synchronization")
    assert req is not None
    launch_status = _check_status(report, "launch_flags")
    if launch_status in {"different", "incompatible", "missing"} and launch_flags is None:
        raise RuntimeDependencyError(
            "managed launch flags drifted: "
            + "; ".join(
                item for item in report.get("mismatches", ()) if str(item).startswith("launch_flags:")
            )
            + "; restart the managed server with the declared flags"
        )
    actions: list[str] = []
    if (
        req.comfy_commit
        and _check_status(report, "comfy_commit") != "matching"
        and selected is None
    ):
        if runtime_root is None:
            raise RuntimeDependencyError("declared ComfyUI commit requires a managed runtime_root")
        comfy_root = Path(runtime_root).expanduser().resolve(strict=False) / "ComfyUI"
        if not (comfy_root / ".git").is_dir():
            raise RuntimeDependencyError(
                f"managed ComfyUI checkout is unavailable at {comfy_root}"
            )
        status = subprocess.run(
            ["git", "-C", str(comfy_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode != 0 or status.stdout.strip():
            raise RuntimeDependencyError(
                "managed ComfyUI checkout is dirty; refusing to replace user changes"
            )
        subprocess.run(
            ["git", "-C", str(comfy_root), "checkout", "--detach", req.comfy_commit],
            check=True,
        )
        actions.append(f"checkout ComfyUI {req.comfy_commit}")
    package_specs = [
        f"{name}{constraint}"
        for name, constraint in req.packages
        if _check_status(report, f"packages.{name}") != "matching"
        and (selected is None or name.casefold().replace("_", "-") in selected)
    ]
    if package_specs:
        action = installer or _install_packages
        try:
            if installer is not None:
                action(package_specs, offline)
            else:
                _install_packages(
                    package_specs,
                    offline,
                    python=managed_python,
                    package_indexes=req.package_indexes,
                )
        except Exception as exc:
            failure_report = dict(report)
            failure_report.update(
                mode="sync",
                managed={
                    "runtime_root": str(root) if root is not None else None,
                    "python_executable": str(managed_python) if managed_python is not None else None,
                },
                actions=list(actions),
                changes=list(actions),
            )
            if isinstance(exc, RuntimeDependencyError):
                setattr(exc, "dependency_report", failure_report)
                raise
            wrapped = RuntimeDependencyError(
                f"runtime package synchronization failed: {exc}"
            )
            setattr(wrapped, "dependency_report", failure_report)
            raise wrapped from exc
        actions.extend(f"install {spec}" for spec in package_specs)
    if verify is not None:
        final_target = dict(verify())
    else:
        # Never return the pre-install observation as proof of synchronization.
        final_target = inspect_runtime_target(
            runtime_root=runtime_root,
            python_executable=managed_python,
            package_names=[name for name, _constraint in req.packages],
        )
    if launch_flags is not None:
        final_target["launch_flags"] = list(launch_flags)
    elif isinstance(target, Mapping) and isinstance(target.get("launch_flags"), (list, tuple, set)):
        # A managed-session snapshot is the process-owned observation for
        # launch flags; package facts are always freshly probed above.
        final_target["launch_flags"] = list(target["launch_flags"])
    report = compare_runtime(req, target=final_target, runtime_root=runtime_root)
    if report.get("status") != "matching":
        # A scoped repair is useful even when other declared requirements were
        # intentionally left untouched.  Return the fresh full observation so
        # callers can show both the successful selected actions and the
        # remaining mismatches.  The report stays noncompliant; the runtime
        # admission gate decides whether an explicit per-attempt deviation is
        # present.
        if selected is not None:
            return {
                **report,
                "mode": "sync",
                "managed": {
                    "runtime_root": str(root) if root is not None else None,
                    "python_executable": str(managed_python) if managed_python is not None else None,
                },
                "synced": bool(actions),
                "partial": True,
                "selected_packages": sorted(selected),
                "remaining_mismatches": list(report.get("mismatches", ())),
                "actions": actions,
                "changes": list(actions),
            }
        exc = RuntimeDependencyError(
            "runtime synchronization did not produce a compatible target: "
            + "; ".join(report.get("mismatches", ()))
        )
        failure_report = dict(report)
        failure_report.update(
            mode="sync",
            managed={
                "runtime_root": str(root) if root is not None else None,
                "python_executable": str(managed_python) if managed_python is not None else None,
            },
            actions=list(actions),
            changes=list(actions),
        )
        setattr(exc, "dependency_report", failure_report)
        raise exc
    return {
        **report,
        "mode": "sync",
        "managed": {"runtime_root": str(root) if root is not None else None, "python_executable": str(managed_python) if managed_python is not None else None},
        "synced": bool(actions),
        "actions": actions,
        "changes": list(actions),
    }


def _package_probe(package_names: Sequence[str]) -> str:
    return (
        "import importlib.metadata, json, platform\n"
        "packages = {}\n"
        f"for name in {tuple(package_names)!r}:\n"
        "    try:\n"
        "        packages[name] = importlib.metadata.version(name)\n"
        "    except importlib.metadata.PackageNotFoundError:\n"
        "        pass\n"
        "print(json.dumps({'python_version': platform.python_version(), 'packages': packages}))"
    )


_PACKAGE_PROBE = _package_probe(("comfy", "comfyui", "torch"))

_MANAGED_MARKER = ".vibecomfy-managed"


def _managed_runtime_marker(runtime_root: str | Path) -> Path:
    return Path(runtime_root).expanduser().resolve(strict=False) / _MANAGED_MARKER


def _managed_python(runtime_root: str | Path | None) -> Path | None:
    if runtime_root is None:
        return None
    root = Path(runtime_root).expanduser().resolve(strict=False)
    candidates = (
        root / ".venv" / "bin" / "python",
        root / "venv" / "bin" / "python",
        root / "ComfyUI" / ".venv" / "bin" / "python",
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _install_packages(
    specs: list[str],
    offline: bool,
    *,
    python: Path | None,
    package_indexes: Sequence[str] = (),
) -> None:
    if python is None:
        raise RuntimeDependencyError("managed Python executable is unavailable")
    command = [str(python), "-m", "pip", "install", "--no-deps"]
    if offline:
        command.append("--no-index")
    elif package_indexes:
        command.extend(["--index-url", str(package_indexes[0])])
        for index in package_indexes[1:]:
            command.extend(["--extra-index-url", str(index)])
    subprocess.run([*command, *specs], check=True)


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeDependencyError(f"{label} must be a nonblank string or null")
    return value.strip()


def _object_list(value: Any, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise RuntimeDependencyError(f"{label} must be an array")
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            result.append({"name": item})
        elif isinstance(item, Mapping):
            result.append({str(key): child for key, child in item.items()})
        else:
            raise RuntimeDependencyError(f"{label} entries must be strings or mappings")
    return result


def _compare_named_objects(
    kind: str,
    expected: tuple[dict[str, Any], ...],
    actual: Any,
    checks: list[dict[str, Any]],
    mismatches: list[str],
) -> None:
    if not expected:
        return
    if not isinstance(actual, Mapping):
        for item in expected:
            name = str(item.get("name", item.get("slug", "<unnamed>")))
            checks.append({
                "path": f"{kind}.{name}",
                "expected": item,
                "actual": None,
                "status": "unverified",
                "reason": "target did not provide an authoritative inventory",
            })
        return
    for item in expected:
        name = str(item.get("name", item.get("slug", "<unnamed>")))
        observed = actual.get(name)
        if observed is None or (isinstance(observed, Mapping) and observed.get("present") is False):
            status = "missing"
        elif isinstance(observed, Mapping):
            status = _object_match_status(item, observed)
        elif observed == item or (isinstance(observed, str) and observed in item.values()):
            status = "matching"
        else:
            status = "different"
        checks.append({
            "path": f"{kind}.{name}",
            "expected": item,
            "actual": observed,
            "status": status,
            "reason": {
                "matching": "observed object satisfies the declared identity",
                "missing": "target reported the object as absent",
                "different": "observed object differs from the declaration",
            }.get(status, "object predicate was not satisfied"),
        })
        if status in {"missing", "different"}:
            mismatches.append(f"{kind}.{name}: expected {item!r}, actual {observed!r}")


def _object_match_status(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> str:
    return "matching" if _object_matches(expected, actual) else "different"


def _check_status(report: Mapping[str, Any], path: str) -> str | None:
    checks = report.get("checks", ())
    if not isinstance(checks, (list, tuple)):
        return None
    for item in checks:
        if isinstance(item, Mapping) and item.get("path") == path:
            return str(item.get("status"))
    return None


def _discover_models(root: Path, expected: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    model_root = root / "ComfyUI" / "models"
    comfy_root = root / "ComfyUI"
    result: dict[str, dict[str, Any]] = {}
    for entry in expected:
        name = str(entry.get("name", entry.get("filename", "")))
        filename = str(entry.get("filename", name))
        subdir = str(entry.get("subdir", entry.get("directory", "")))
        declared_target = entry.get("target_path")
        target_path = str(declared_target) if declared_target is not None else f"{subdir}/{filename}".strip("/")
        path = (comfy_root / target_path) if declared_target is not None else (model_root / subdir / filename)
        item: dict[str, Any] = {
            "name": name,
            "filename": filename,
            "subdir": subdir,
            "target_path": target_path,
            "path": str(path),
            "present": path.is_file(),
        }
        if path.is_file():
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        result[name] = item
    return result


def _discover_custom_nodes(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    try:
        from vibecomfy.node_packs import read_lockfile
        entries = read_lockfile(root / "custom_nodes.lock")
    except Exception:
        entries = ()
    for entry in entries:
        path = root / "custom_nodes" / entry.name
        result[entry.name] = {
            "path": str(path),
            "commit": _git_head(path) if path.is_dir() else None,
            "present": path.is_dir(),
        }
    return result


def _git_head(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout.strip() or None


def _comfyui_git_head_for_root(runtime_root: str | Path | None) -> str | None:
    if runtime_root is None:
        return None
    root = Path(runtime_root).expanduser().resolve(strict=False)
    for candidate in (root / "ComfyUI", root):
        if (candidate / ".git").is_dir():
            return _git_head(candidate)
    return None


def _object_matches(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    aliases = {
        "name": ("name", "filename"),
        "filename": ("filename", "name"),
        "subdir": ("subdir", "directory"),
        "directory": ("directory", "subdir"),
        "target_path": ("target_path", "path"),
        "path": ("path", "target_path"),
    }
    for key in (
        "name", "filename", "subdir", "directory", "target_path", "path",
        "commit", "git_commit_sha", "version", "sha256", "expected_sha256",
    ):
        if key not in expected or expected[key] is None:
            continue
        observed = next(
            (actual.get(candidate) for candidate in aliases.get(key, (key,)) if candidate in actual),
            None,
        )
        if observed != expected[key]:
            return False
    return True


def _version_satisfies(actual: str, constraint: str) -> bool:
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
        return Version(actual) in SpecifierSet(constraint)
    except Exception:
        normalized = constraint.strip()
        if normalized.startswith("=="):
            return actual == normalized[2:].strip()
        return actual == normalized


__all__ = [
    "RuntimeDependencyError",
    "RuntimeRequirements",
    "compare_runtime",
    "inspect_runtime_target",
    "normalize_runtime_requirements",
    "runtime_requirements_from_workflow",
    "sync_runtime",
]
