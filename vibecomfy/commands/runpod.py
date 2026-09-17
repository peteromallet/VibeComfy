from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from vibecomfy.commands import runpod_setup
from vibecomfy.runtime.session_binding import load_binding, write_binding


def _load_runpod_lifecycle():
    """Load the existing lifecycle package, including a sibling checkout."""
    try:
        return importlib.import_module("runpod_lifecycle")
    except ImportError:
        root = _runpod_lifecycle_root()
        src = root / "src"
        if not src.exists():
            raise RuntimeError(
                "runpod-lifecycle is not installed and its configured sibling checkout is unavailable"
            )
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        try:
            return importlib.import_module("runpod_lifecycle")
        except Exception as exc:
            raise RuntimeError(f"could not import runpod-lifecycle: {type(exc).__name__}: {exc}") from exc


class BoundRunPodLifecycleAdapter:
    """Use the existing lifecycle API for one explicitly bound pod.

    Comfy's HTTP API remains the queue transport.  This adapter owns the
    machine custody witness and the SSH-backed artifact/log retrieval, so a
    named RunPod session cannot silently degrade into an unverified URL run.
    It never provisions, restarts, or mutates the pod.
    """

    def __init__(self, binding: dict[str, object], *, session_id: str) -> None:
        self.binding = dict(binding)
        self.session_id = str(session_id)
        self._pod = None
        self._witness: dict[str, object] | None = None

    def describe(self) -> dict[str, object]:
        return {
            "provider": "runpod_lifecycle",
            "operation": "attach/status/prepare/download/log",
            "pod_id": self.binding.get("pod_id"),
            "status": "not_attached",
        }

    async def attach(self) -> dict[str, object]:
        if self._witness is not None:
            return dict(self._witness)
        lifecycle = _load_runpod_lifecycle()
        pod_id = str(self.binding.get("pod_id") or "").strip()
        if not pod_id:
            raise RuntimeError("RunPod binding has no pod_id")
        config = lifecycle.RunPodConfig.from_env()
        pod = await lifecycle.get_pod(pod_id, config, name=self.session_id)
        status = await pod.status()
        if not isinstance(status, dict):
            raise RuntimeError(f"RunPod lifecycle returned no status for bound pod {pod_id}")
        self._pod = pod
        self._witness = {
            "provider": "runpod_lifecycle",
            "operation": "attach/status/prepare/download/log",
            "pod_id": pod_id,
            "status": "attached",
            "desired_status": status.get("desired_status"),
            "actual_status": status.get("actual_status"),
        }
        return dict(self._witness)

    def prepare(
        self,
        *,
        workflow_reference: str | Path,
        dependency_mode: str,
        runtime_root: str | Path | None,
        ensure_models: bool,
        ensure_packs: bool,
        offline: bool,
        plan: dict[str, object],
        runtime_target: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Run the shared VibeComfy preparation coordinator on the bound pod.

        The lifecycle package owns pod custody and SSH transport; the VibeComfy
        CLI on the pod remains the single preparation coordinator.  A binding
        must therefore name the remote workflow path (or a configured remote
        command can provide one).  We fail closed when that handoff is not
        configured instead of pretending that local preparation affected the
        pod.
        """
        return asyncio.run(
            self._prepare_async(
                workflow_reference=workflow_reference,
                dependency_mode=dependency_mode,
                runtime_root=runtime_root,
                ensure_models=ensure_models,
                ensure_packs=ensure_packs,
                offline=offline,
                plan=plan,
                runtime_target=runtime_target,
            )
        )

    async def _prepare_async(
        self,
        *,
        workflow_reference: str | Path,
        dependency_mode: str,
        runtime_root: str | Path | None,
        ensure_models: bool,
        ensure_packs: bool,
        offline: bool,
        plan: dict[str, object],
        runtime_target: dict[str, object] | None,
    ) -> dict[str, object]:
        pod = self._pod
        if pod is None:
            await self.attach()
            pod = self._pod
        if pod is None:
            raise RuntimeError("RunPod lifecycle adapter did not attach a pod")
        wait_ready = getattr(pod, "wait_ready", None)
        if callable(wait_ready):
            await wait_ready(timeout=60)

        remote_reference = self.binding.get("remote_workflow") or self.binding.get("workflow_path")
        if not isinstance(remote_reference, str) or not remote_reference.strip():
            raise RuntimeError(
                "RunPod binding has no remote_workflow; bind the workflow on the pod "
                "before requesting lifecycle-backed preparation"
            )
        executable = self.binding.get("vibecomfy_executable")
        if isinstance(executable, str) and executable.strip():
            command = shlex.split(executable)
        else:
            target_python = self.binding.get("python_executable")
            command = [str(target_python), "-m", "vibecomfy.cli"] if target_python else ["vibecomfy"]
        if not command:
            raise RuntimeError("RunPod binding has an empty vibecomfy_executable")
        remote_root = str(
            self.binding.get("remote_runtime_root")
            or self.binding.get("runtime_root")
            or Path(str(self.binding.get("comfy_root") or "/workspace")).parent
        )
        command.extend(
            [
                "prepare",
                remote_reference.strip(),
                "--session",
                self.session_id,
                "--deps",
                str(dependency_mode),
                "--runtime-root",
                remote_root,
                "--json",
            ]
        )
        if not ensure_models:
            command.append("--no-models")
        if not ensure_packs:
            command.append("--no-packs")
        if offline:
            command.append("--offline")
        code, stdout, stderr = await pod.exec_ssh(shlex.join(command), timeout=600)
        if code != 0:
            detail = (stderr or stdout or "remote preparation failed").strip()
            raise RuntimeError(f"remote VibeComfy preparation failed: {detail[-2000:]}")
        response: dict[str, object] | None = None
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict):
                response = parsed
        except (TypeError, ValueError):
            response = None
        return {
            "provider": "runpod_lifecycle",
            "operation": "prepare",
            "pod_id": self.binding.get("pod_id"),
            "status": "prepared",
            "remote_workflow": remote_reference.strip(),
            "remote_runtime_root": remote_root,
            "dependency_mode": dependency_mode,
            "plan": dict(plan),
            "runtime_target": dict(runtime_target or {}),
            "response": response,
            "stdout_tail": stdout[-2000:] if isinstance(stdout, str) else "",
        }

    async def download_artifacts(self, *, local_root: Path) -> dict[str, object]:
        pod = self._pod
        if pod is None:
            await self.attach()
            pod = self._pod
        if pod is None:
            raise RuntimeError("RunPod lifecycle adapter did not attach a pod")
        wait_ready = getattr(pod, "wait_ready", None)
        if callable(wait_ready):
            await wait_ready(timeout=60)
        remote_root = str(self.binding.get("comfy_root") or "/workspace")
        downloaded = await pod.download_archive(
            remote_root,
            local_root,
            artifact_paths=["output", "out"],
        )
        return {
            "provider": "runpod_lifecycle",
            "status": "retrieved" if downloaded is not None else "unavailable",
            "remote_root": remote_root,
            "artifact_paths": ["output", "out"],
            "local_root": str(downloaded or local_root),
        }

    async def capture_log(self, *, local_path: Path) -> dict[str, object]:
        pod = self._pod
        if pod is None:
            await self.attach()
            pod = self._pod
        if pod is None:
            raise RuntimeError("RunPod lifecycle adapter did not attach a pod")
        remote_path = str(
            self.binding.get("log_path")
            or (Path(str(self.binding.get("comfy_root") or "/workspace")) / "comfy.log")
        )
        command = f"if [ -f {shlex.quote(remote_path)} ]; then cat {shlex.quote(remote_path)}; else exit 3; fi"
        code, stdout, stderr = await pod.exec_ssh(command, timeout=60)
        if code != 0:
            return {
                "provider": "runpod_lifecycle",
                "status": "unavailable",
                "remote_path": remote_path,
                "local_path": None,
                "reason": (stderr or stdout or "remote log was not found").strip()[:500],
            }
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(stdout, encoding="utf-8")
        return {
            "provider": "runpod_lifecycle",
            "status": "captured",
            "remote_path": remote_path,
            "local_path": str(local_path),
        }


def _runpod_lifecycle_root() -> Path:
    configured = getattr(sys, "_vibecomfy_runpod_lifecycle_root", None)
    if configured:
        return Path(configured)
    configured_env = os.getenv("VIBECOMFY_RUNPOD_LIFECYCLE_ROOT")
    if configured_env:
        return Path(configured_env)
    return Path(__file__).resolve().parents[3] / "runpod-lifecycle"


def _runpod_lifecycle_main(argv: list[str]) -> int:
    try:
        from runpod_lifecycle.cli import main as runpod_main
    except ImportError:
        root = _runpod_lifecycle_root()
        src = root / "src"
        if not src.exists():
            print(
                "runpod-lifecycle is not installed. Install VibeComfy with `pip install -e '.[runpod-local]'` "
                "or set VIBECOMFY_RUNPOD_LIFECYCLE_ROOT for a local checkout.",
                file=sys.stderr,
            )
            return 1
        sys.path.insert(0, str(src))
        try:
            from runpod_lifecycle.cli import main as runpod_main
        except Exception as exc:
            print(f"could not import runpod-lifecycle: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    root = _runpod_lifecycle_root()
    try:
        from runpod_lifecycle.config import load_runpod_env
    except ImportError:
        # The pinned lifecycle release predates the shared environment loader.
        # Keep it usable while newer installations own shared-file precedence.
        from dotenv import load_dotenv as load_runpod_env
    load_runpod_env(root / ".env")
    return runpod_main(argv)


def _cmd_runpod_list(args: argparse.Namespace) -> int:
    argv = ["list"]
    if args.name_prefix:
        argv.extend(["--name-prefix", args.name_prefix])
    if args.json:
        argv.append("--json")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_status(args: argparse.Namespace) -> int:
    return _runpod_lifecycle_main(["status", args.pod_id])


def _cmd_runpod_terminate(args: argparse.Namespace) -> int:
    argv = ["terminate", args.pod_id]
    if args.yes:
        argv.append("--yes")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_gpu_types(args: argparse.Namespace) -> int:
    argv = ["gpu-types"]
    if args.json:
        argv.append("--json")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_corpus_matrix(args: argparse.Namespace) -> int:
    script = Path("scripts/runpod_corpus_matrix.py")
    if not script.exists():
        print("scripts/runpod_corpus_matrix.py not found; run from the VibeComfy repo root", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(script)])


def _cmd_runpod_bind(args: argparse.Namespace) -> int:
    """Record custody for an existing pod without provisioning or mutating it."""
    from vibecomfy.runtime.session_binding import binding_path

    values = {
        "pod_id": str(args.pod_id),
        "comfy_root": str(args.comfy_root),
        "python_executable": str(args.python_executable),
        "custom_nodes_root": str(args.custom_nodes_root) if args.custom_nodes_root else None,
        "models_root": str(args.models_root) if args.models_root else None,
        "launch_flags": list(args.launch_flags or []),
        "remote": True,
    }
    comfy_url = getattr(args, "comfy_url", None)
    if comfy_url is not None and str(comfy_url).strip():
        values["comfy_url"] = str(comfy_url).strip().rstrip("/")
    log_path = getattr(args, "log_path", None)
    if log_path is not None and str(log_path).strip():
        values["log_path"] = str(log_path).strip()
    for argument, key in (
        ("remote_workflow", "remote_workflow"),
        ("remote_runtime_root", "remote_runtime_root"),
        ("vibecomfy_executable", "vibecomfy_executable"),
    ):
        value = getattr(args, argument, None)
        if value is not None and str(value).strip():
            values[key] = str(value).strip()
    if any(not str(values[key]).strip() for key in ("pod_id", "comfy_root", "python_executable")):
        print("runpod bind failed: pod_id, comfy_root, and python are required", file=sys.stderr)
        return 2
    path = binding_path(args.session, args.runtime_root)
    existing = load_binding(args.session, args.runtime_root)
    if existing and not args.replace:
        if all(existing.get(key) == values.get(key) for key in ("pod_id", "comfy_root", "python_executable", "comfy_url")):
            print(f"runpod binding already recorded: {path}")
            return 0
        print(f"runpod bind refused: {path} already names a different target; pass --replace", file=sys.stderr)
        return 1
    written = write_binding(args.session, values, args.runtime_root)
    print(f"runpod binding recorded: {written}")
    return 0


def _cmd_runpod_prepare_comfy(args: argparse.Namespace) -> int:
    try:
        runpod_setup.link_vibecomfy_custom_node(
            custom_nodes=args.custom_nodes,
            dry_run=args.dry_run,
        )
    except FileExistsError as exc:
        print(f"VibeComfy custom node link skipped: {exc}")
    if args.profile == "baseline":
        if args.install_python_deps:
            runpod_setup.install_python_deps(dry_run=args.dry_run)
        runpod_setup.stage_baseline_models(
            models_root=args.models_root,
            registry=args.registry,
            dry_run=args.dry_run,
        )
        parked = runpod_setup.park_node_packs(
            custom_nodes=args.custom_nodes,
            disabled_custom_nodes=args.disabled_custom_nodes,
            dry_run=args.dry_run,
        )
        for item in parked:
            if item.changed:
                action = "would park" if args.dry_run else "parked"
                print(f"{action} {item.name}: {item.source} -> {item.target}")
        return 0
    if args.profile == "ltx":
        if args.install_python_deps:
            runpod_setup.install_python_deps(dry_run=args.dry_run)
        runpod_setup.stage_ltx_models(
            models_root=args.models_root,
            registry=args.registry,
            full=args.full,
            dry_run=args.dry_run,
        )
        print("ltx profile staged LTX models. ResAdapter stays parked so SD1.5 and LTX can share one ComfyUI process.")
        return 0
    raise ValueError(f"unknown profile: {args.profile}")


def _cmd_runpod_install_nodes(args: argparse.Namespace) -> int:
    try:
        linked = runpod_setup.link_vibecomfy_custom_node(
            custom_nodes=args.custom_nodes,
            dry_run=args.dry_run,
        )
        if linked.changed:
            action = "would link" if args.dry_run else "linked"
            print(f"{action} VibeComfy custom node: {linked.target} -> {linked.source}")
    except FileExistsError as exc:
        print(f"VibeComfy custom node link skipped: {exc}")
    installed = runpod_setup.install_node_packs(
        custom_nodes=args.custom_nodes,
        lockfile=args.lockfile,
        node_packs=args.node_pack or runpod_setup.LTX_NODE_PACKS,
        install_requirements=not args.no_requirements,
        dry_run=args.dry_run,
    )
    for item in installed:
        action = "would install" if args.dry_run else ("installed" if item.changed else "verified")
        print(f"{action} {item.name} @ {item.commit}: {item.path}")
    return 0


def _cmd_runpod_install_torch(args: argparse.Namespace) -> int:
    runpod_setup.install_runpod_torch(
        python=args.python,
        dry_run=args.dry_run,
    )
    return 0


def _cmd_runpod_bootstrap_comfy(args: argparse.Namespace) -> int:
    launch_flags = None
    runtime_decl = None
    workflow_arg = getattr(args, "workflow", None)
    if workflow_arg is not None:
        workflow_path = Path(workflow_arg)
        try:
            if workflow_path.suffix == ".json":
                raw = json.loads(workflow_path.read_text(encoding="utf-8"))
                reqs = raw.get("requirements", {}) if isinstance(raw, dict) else {}
                runtime_raw = reqs.get("runtime") if isinstance(reqs, dict) else None
                from vibecomfy.contracts.runtime import RuntimeRequirements
                runtime_decl = RuntimeRequirements.from_dict(
                    runtime_raw,
                    legacy_python_env=(raw.get("metadata", {}) or {}).get("python_env") if isinstance(raw, dict) and isinstance(raw.get("metadata"), dict) else None,
                    legacy_comfy_commit=(raw.get("metadata", {}) or {}).get("comfy_commit") if isinstance(raw, dict) and isinstance(raw.get("metadata"), dict) else None,
                )
                launch_flags = list(runtime_decl.launch_flags) if runtime_decl is not None else None
            else:
                from vibecomfy.registry.static_contract import extract_ready_template_contract
                static = extract_ready_template_contract(workflow_path)
                static_errors = [
                    item for item in static.get("diagnostics", [])
                    if isinstance(item, dict) and item.get("severity") == "error"
                ]
                if static_errors:
                    detail = "; ".join(str(item.get("message", item)) for item in static_errors)
                    raise ValueError(f"workflow runtime declaration is invalid: {detail}")
                runtime_raw = static.get("runtime")
                from vibecomfy.contracts.runtime import RuntimeRequirements
                runtime_decl = RuntimeRequirements.from_dict(runtime_raw)
                launch_flags = list(runtime_raw.get("launch_flags", [])) if isinstance(runtime_raw, dict) else None
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"workflow runtime declaration could not be read: {exc}") from exc
    runtime_root = args.runtime_root
    managed_python = None
    if runtime_decl is not None and not args.dry_run:
        from vibecomfy.runtime.dependencies import _managed_python

        managed_python = _managed_python(runtime_root)
        comfy_root = runtime_root / "ComfyUI"
        managed_cli = managed_python.with_name("comfyui") if managed_python is not None else None
        marker = runtime_root / runpod_setup.MANAGED_RUNTIME_MARKER
        if (
            not marker.is_file()
            or managed_python is None
            or not comfy_root.is_dir()
            or not (comfy_root / ".git").is_dir()
            or managed_cli is None
            or not managed_cli.is_file()
        ):
            print(
                "RunPod runtime bootstrap refused: a declared workflow runtime requires "
                f"an existing managed interpreter and ComfyUI checkout under {runtime_root} "
                "(including the .vibecomfy-managed marker, runtime_root/.venv or venv, "
                "and its comfyui executable); "
                "provision/bind those first",
                file=sys.stderr,
            )
            return 1
        args.comfyui_executable = str(managed_cli)
    runpod_setup.ensure_runtime_layout(runtime_root=runtime_root, dry_run=args.dry_run)
    env = runpod_setup.runtime_environment(runtime_root=runtime_root)
    os.environ.update({key: os.environ.get(key, value) for key, value in env.items()})
    runpod_setup.write_extra_model_paths(runtime_root=runtime_root, dry_run=args.dry_run)
    runpod_setup.ensure_smoke_inputs(runtime_root=runtime_root, dry_run=args.dry_run)
    if runtime_decl is not None:
        from vibecomfy.runtime.dependencies import RuntimeDependencyError, sync_runtime

        if args.dry_run:
            print(f"would sync workflow runtime: {runtime_decl.to_dict()}")
        else:
            try:
                sync_runtime(
                    runtime_decl,
                    runtime_root=runtime_root,
                    offline=os.environ.get("VIBECOMFY_OFFLINE") == "1",
                    launch_flags=launch_flags,
                )
            except (RuntimeDependencyError, OSError, subprocess.SubprocessError) as exc:
                print(f"RunPod runtime sync failed: {exc}", file=sys.stderr)
                return 1
    declared_torch = runtime_decl.python_packages.get("torch") if runtime_decl is not None else None
    if not args.skip_torch_fix and declared_torch is None:
        runpod_setup.install_runpod_torch(
            python=str(Path(args.comfyui_executable).with_name("python")) if "/" in args.comfyui_executable else sys.executable,
            dry_run=args.dry_run,
        )
    elif declared_torch is not None:
        print(f"workflow runtime declares torch {declared_torch}; skipping legacy RunPod Torch override")
    try:
        installed = runpod_setup.install_node_packs(
            custom_nodes=runtime_root / "custom_nodes",
            lockfile=args.lockfile,
            node_packs=args.node_pack or runpod_setup.LTX_NODE_PACKS,
            python=str(managed_python) if managed_python is not None else sys.executable,
            install_requirements=not args.no_requirements,
            offline=os.environ.get("VIBECOMFY_OFFLINE") == "1",
            dry_run=args.dry_run,
        )
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"RunPod node-pack installation failed: {exc}", file=sys.stderr)
        return 1
    for item in installed:
        action = "would install" if args.dry_run else ("installed" if item.changed else "verified")
        print(f"{action} {item.name} @ {item.commit}: {item.path}")
    try:
        linked = runpod_setup.link_vibecomfy_custom_node(
            custom_nodes=runtime_root / "custom_nodes",
            dry_run=args.dry_run,
        )
        if linked.changed:
            action = "would link" if args.dry_run else "linked"
            print(f"{action} VibeComfy custom node: {linked.target} -> {linked.source}")
    except FileExistsError as exc:
        print(f"VibeComfy custom node link skipped: {exc}")
    if runtime_decl is not None and not args.dry_run:
        from vibecomfy.runtime.dependencies import RuntimeDependencyError, sync_runtime

        try:
            final_runtime_report = sync_runtime(
                runtime_decl,
                runtime_root=runtime_root,
                offline=os.environ.get("VIBECOMFY_OFFLINE") == "1",
                launch_flags=launch_flags,
            )
        except (RuntimeDependencyError, OSError, subprocess.SubprocessError) as exc:
            print(f"RunPod runtime verification failed after node installation: {exc}", file=sys.stderr)
            return 1
        print(f"workflow runtime verified: {final_runtime_report.get('status', 'unknown')}")
    if not args.skip_models:
        runpod_setup.stage_baseline_models(
            models_root=runtime_root / "models",
            registry=args.registry,
            dry_run=args.dry_run,
        )
        runpod_setup.park_node_packs(
            custom_nodes=runtime_root / "custom_nodes",
            disabled_custom_nodes=runtime_root / "disabled_custom_nodes",
            dry_run=args.dry_run,
        )
        runpod_setup.stage_ltx_models(
            models_root=runtime_root / "models",
            registry=args.registry,
            full=args.full_ltx,
            dry_run=args.dry_run,
        )
    command = runpod_setup.comfy_serve_command(
        runtime_root=runtime_root,
        external_address=args.external_address,
        port=args.port,
        comfyui_executable=args.comfyui_executable,
        launch_flags=launch_flags,
    )
    print("\n# Runtime environment")
    for key, value in env.items():
        print(f"export {key}={shlex.quote(value)}")
    print("\n# Start ComfyUI")
    print(" ".join(shlex.quote(part) for part in command))
    return 0


def register(subparsers) -> None:
    runpod = subparsers.add_parser("runpod")
    runpod_sub = runpod.add_subparsers(dest="subcmd", required=True)

    runpod_list = runpod_sub.add_parser("list")
    runpod_list.add_argument("--name-prefix")
    runpod_list.add_argument("--json", action="store_true")
    runpod_list.set_defaults(func=_cmd_runpod_list)

    runpod_status = runpod_sub.add_parser("status")
    runpod_status.add_argument("pod_id")
    runpod_status.set_defaults(func=_cmd_runpod_status)

    runpod_terminate = runpod_sub.add_parser("terminate")
    runpod_terminate.add_argument("pod_id")
    runpod_terminate.add_argument("--yes", "-y", action="store_true")
    runpod_terminate.set_defaults(func=_cmd_runpod_terminate)

    runpod_gpu_types = runpod_sub.add_parser("gpu-types")
    runpod_gpu_types.add_argument("--json", action="store_true")
    runpod_gpu_types.set_defaults(func=_cmd_runpod_gpu_types)

    runpod_corpus = runpod_sub.add_parser("corpus-matrix")
    runpod_corpus.set_defaults(func=_cmd_runpod_corpus_matrix)

    bind = runpod_sub.add_parser("bind", help="Record a named binding for an existing pod; does not provision or mutate it.")
    bind.add_argument("pod_id")
    bind.add_argument("--session", required=True)
    bind.add_argument("--comfy-root", required=True)
    bind.add_argument("--python", dest="python_executable", required=True)
    bind.add_argument("--custom-nodes-root")
    bind.add_argument("--models-root")
    bind.add_argument("--comfy-url", help="Reachable Comfy endpoint for this existing pod (optional).")
    bind.add_argument("--log-path", help="Remote Comfy log path to capture through the lifecycle API (optional).")
    bind.add_argument("--remote-workflow", help="Workflow path already present on the bound pod for lifecycle-backed prepare.")
    bind.add_argument("--remote-runtime-root", help="Managed runtime root on the bound pod (defaults to the ComfyUI parent).")
    bind.add_argument("--vibecomfy-executable", help="Remote VibeComfy CLI or command used by lifecycle-backed prepare (default: vibecomfy).")
    bind.add_argument("--launch-flag", dest="launch_flags", action="append")
    bind.add_argument("--runtime-root")
    bind.add_argument("--replace", action="store_true")
    bind.set_defaults(func=_cmd_runpod_bind)

    prepare = runpod_sub.add_parser("prepare-comfy")
    prepare.add_argument("--profile", choices=("baseline", "ltx"), default="baseline")
    prepare.add_argument("--models-root", type=Path, default=Path("/workspace/vibecomfy/models"))
    prepare.add_argument("--custom-nodes", type=Path, default=Path("/workspace/vibecomfy/custom_nodes"))
    prepare.add_argument("--disabled-custom-nodes", type=Path, default=Path("/workspace/vibecomfy/disabled_custom_nodes"))
    prepare.add_argument("--registry", type=Path, default=None)
    prepare.add_argument("--install-python-deps", action="store_true")
    prepare.add_argument("--full", action="store_true", help="For --profile ltx, stage every phase:ltx registry asset.")
    prepare.add_argument("--dry-run", action="store_true")
    prepare.set_defaults(func=_cmd_runpod_prepare_comfy)

    install_nodes = runpod_sub.add_parser("install-nodes")
    install_nodes.add_argument("--custom-nodes", type=Path, default=Path("/workspace/vibecomfy/custom_nodes"))
    install_nodes.add_argument("--lockfile", type=Path, default=Path("custom_nodes.lock"))
    install_nodes.add_argument(
        "--node-pack",
        action="append",
        default=None,
        help="Node pack from custom_nodes.lock to install. Repeat to override/extend the default LTX set.",
    )
    install_nodes.add_argument("--no-requirements", action="store_true")
    install_nodes.add_argument("--dry-run", action="store_true")
    install_nodes.set_defaults(func=_cmd_runpod_install_nodes)

    install_torch = runpod_sub.add_parser("install-torch")
    install_torch.add_argument("--python", default=sys.executable)
    install_torch.add_argument("--dry-run", action="store_true")
    install_torch.set_defaults(func=_cmd_runpod_install_torch)

    bootstrap = runpod_sub.add_parser("bootstrap-comfy")
    bootstrap.add_argument("--runtime-root", type=Path, default=Path("/workspace/vibecomfy"))
    bootstrap.add_argument("--lockfile", type=Path, default=Path("custom_nodes.lock"))
    bootstrap.add_argument("--registry", type=Path, default=None)
    bootstrap.add_argument("--port", type=int, default=19123)
    bootstrap.add_argument("--external-address")
    bootstrap.add_argument("--comfyui-executable", default="comfyui")
    bootstrap.add_argument("--workflow", type=Path, help="Workflow envelope or ready-template source whose runtime declaration should be used.")
    bootstrap.add_argument(
        "--node-pack",
        action="append",
        default=None,
        help="Node pack from custom_nodes.lock to install. Repeat to override/extend the default LTX set.",
    )
    bootstrap.add_argument("--no-requirements", action="store_true")
    bootstrap.add_argument("--skip-models", action="store_true")
    bootstrap.add_argument("--skip-torch-fix", action="store_true")
    bootstrap.add_argument("--full-ltx", action="store_true", help="Stage every phase:ltx registry asset instead of the basic TTV set.")
    bootstrap.add_argument("--dry-run", action="store_true")
    bootstrap.set_defaults(func=_cmd_runpod_bootstrap_comfy)
