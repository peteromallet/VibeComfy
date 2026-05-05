from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import posixpath
import re
import signal
import shutil
import struct
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/workspace/vibecomfy"
MiB = 1024 * 1024

DEFAULT_UPLOAD_EXCLUDES: set[str] = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".desloppify",
    ".megaplan",
    "out",
    "output",
    "vendor",
    "workflow_corpus",
    "custom_nodes",
    "input",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
}

DEFAULT_UPLOAD_PROGRESS_SECONDS = 10.0
DEFAULT_UPLOAD_PROGRESS_FILES = 250


def runpod_lifecycle_root() -> Path:
    configured = os.getenv("VIBECOMFY_RUNPOD_LIFECYCLE_ROOT")
    if configured:
        return Path(configured)
    return ROOT.parent / "runpod-lifecycle"


RUNPOD_LIFECYCLE = runpod_lifecycle_root()


def _format_bytes(value: int) -> str:
    if value >= 1024 * MiB:
        return f"{value / (1024 * MiB):.1f}GiB"
    if value >= MiB:
        return f"{value / MiB:.1f}MiB"
    if value >= 1024:
        return f"{value / 1024:.1f}KiB"
    return f"{value}B"


def _log_phase(name: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"phase={name}{suffix}", flush=True)


def _log_pod_identity(pod) -> None:
    print(f"pod_id={pod.id}", flush=True)
    print(f"manual_cleanup_command=vibecomfy runpod terminate {pod.id} --yes", flush=True)


class UploadHeartbeat:
    def __init__(self, *, label: str) -> None:
        self.label = label
        self.files = 0
        self.bytes = 0
        self.start = time.monotonic()
        self.last_log = self.start
        self.every_seconds = float(os.getenv("VIBECOMFY_UPLOAD_PROGRESS_SECONDS", str(DEFAULT_UPLOAD_PROGRESS_SECONDS)))
        self.every_files = max(1, int(os.getenv("VIBECOMFY_UPLOAD_PROGRESS_FILES", str(DEFAULT_UPLOAD_PROGRESS_FILES))))

    def tick(self, *, files: int = 0, bytes_added: int = 0, force: bool = False) -> None:
        self.files += files
        self.bytes += bytes_added
        now = time.monotonic()
        if force or self.files % self.every_files == 0 or now - self.last_log >= self.every_seconds:
            elapsed = max(now - self.start, 0.001)
            print(
                f"{self.label}_progress files={self.files} bytes={self.bytes} "
                f"size={_format_bytes(self.bytes)} elapsed_seconds={elapsed:.1f}",
                flush=True,
            )
            self.last_log = now


class PodGuard:
    def __init__(
        self,
        *,
        name_prefix: str,
        max_runtime_seconds_env: str = "VIBECOMFY_RUNPOD_MAX_RUNTIME_SECONDS",
        default_max_runtime_seconds: int = 7200,
    ) -> None:
        self.name_prefix = name_prefix
        self.max_runtime_seconds_env = max_runtime_seconds_env
        self.default_max_runtime_seconds = default_max_runtime_seconds
        self.pod = None
        self._watchdog: asyncio.Task[None] | None = None

    async def launch(self):
        load_dotenv, runpod_config, launch = _runpod_lifecycle()
        load_dotenv(runpod_lifecycle_root() / ".env")
        config_kwargs = {
            "storage_name": os.getenv("VIBECOMFY_RUNPOD_STORAGE", "Peter"),
            "storage_volumes": (),
            "gpu_type": os.getenv("VIBECOMFY_RUNPOD_GPU", "NVIDIA GeForce RTX 4090"),
            "ram_tiers": (32, 16),
        }
        if os.getenv("VIBECOMFY_RUNPOD_CONTAINER_DISK_GB"):
            config_kwargs["container_disk_gb"] = int(os.environ["VIBECOMFY_RUNPOD_CONTAINER_DISK_GB"])
        if os.getenv("VIBECOMFY_RUNPOD_DISK_SIZE_GB"):
            config_kwargs["disk_size_gb"] = int(os.environ["VIBECOMFY_RUNPOD_DISK_SIZE_GB"])
        self.pod = await launch(runpod_config.from_env(**config_kwargs), name=f"{self.name_prefix}-{int(time.time())}")
        self._start_watchdog()
        return self.pod

    async def terminate(self) -> None:
        if self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None
        if self.pod is not None:
            try:
                await self.pod.terminate()
            except Exception as exc:
                if "not found" in str(exc).lower():
                    print(f"pod_already_terminated={self.pod.id}", flush=True)
                else:
                    raise

    def _start_watchdog(self) -> None:
        seconds = int(os.getenv(self.max_runtime_seconds_env, str(self.default_max_runtime_seconds)))
        self._watchdog = asyncio.create_task(self._terminate_after(seconds))

    async def _terminate_after(self, seconds: int) -> None:
        try:
            await asyncio.sleep(seconds)
            if self.pod is not None:
                print(f"watchdog_terminating_pod={self.pod.id}", flush=True)
                await self.pod.terminate()
        except asyncio.CancelledError:
            return


def should_skip(path: Path, root: Path, exclude_set: set[str]) -> bool:
    rel = path.relative_to(root).as_posix()
    parts = Path(rel).parts
    return (
        any(rel == item or rel.startswith(f"{item}/") or item in parts for item in exclude_set)
        or path.suffix in {".pyc", ".pyo"}
    )


def upload_dir(sftp, local: Path, remote: str, exclude_set: set[str], *, progress: UploadHeartbeat | None = None) -> None:
    try:
        sftp.mkdir(remote)
    except OSError:
        pass
    for child in local.iterdir():
        if should_skip(child, ROOT, exclude_set):
            continue
        remote_child = posixpath.join(remote, child.name)
        if child.is_dir():
            upload_dir(sftp, child, remote_child, exclude_set, progress=progress)
        else:
            size = child.stat().st_size
            if progress is not None:
                sent = 0

                def _progress(current: int, _total: int) -> None:
                    nonlocal sent
                    delta = max(0, current - sent)
                    sent = current
                    progress.tick(bytes_added=delta)

                sftp.put(str(child), remote_child, callback=_progress)
                progress.tick(files=1, bytes_added=max(0, size - sent))
            else:
                sftp.put(str(child), remote_child)


def install_signal_handlers(loop) -> asyncio.Event:
    cancel_event = asyncio.Event()
    task = asyncio.current_task(loop=loop)
    signal_count = 0

    def _handle_signal(sig: signal.Signals) -> None:
        nonlocal signal_count
        signal_count += 1
        print(f"interrupt_requested signal={sig.name} cleanup=true", flush=True)
        cancel_event.set()
        if task is not None and not task.done():
            task.cancel()
        if signal_count > 1:
            print("interrupt_repeated=true cleanup_still_in_progress=true", flush=True)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
        except (NotImplementedError, RuntimeError):
            previous = signal.getsignal(sig)

            def _fallback(signum, frame, *, previous=previous) -> None:
                loop.call_soon_threadsafe(_handle_signal, signal.Signals(signum))
                if callable(previous) and previous not in {signal.SIG_DFL, signal.SIG_IGN}:
                    previous(signum, frame)

            signal.signal(sig, _fallback)
    return cancel_event


def _clear_current_task_cancellation() -> None:
    task = asyncio.current_task()
    if task is None or not hasattr(task, "uncancel"):
        return
    while task.cancelling():
        task.uncancel()


async def run_pod(
    remote_script: str,
    *,
    name_prefix: str,
    exclude: set[str],
    upload_mode: Literal["sftp_walk", "tarball"] = "sftp_walk",
    timeout: int,
) -> int:
    guard = PodGuard(name_prefix=name_prefix, default_max_runtime_seconds=max(timeout * 2, 7200))
    install_signal_handlers(asyncio.get_running_loop())
    result_code: int | None = None
    try:
        _log_phase("launching", f"name_prefix={name_prefix} upload_mode={upload_mode} timeout={timeout}")
        pod = await guard.launch()
        _log_pod_identity(pod)
        _log_phase("waiting_ssh", f"pod_id={pod.id}")
        await pod.wait_ready(timeout=300)
        ssh_details = await pod._ensure_ssh_details()
        print(f"pod_ssh=root@{ssh_details['ip']} -p {ssh_details['port']}", flush=True)
        _log_phase("gpu_check", f"pod_id={pod.id}")
        code, stdout, stderr = await pod.exec_ssh("nvidia-smi -L", timeout=60)
        print(stdout.strip(), flush=True)
        if code != 0:
            print(stderr, flush=True)
            result_code = code
            return result_code

        if upload_mode == "tarball":
            await _upload_tarball(pod, exclude)
        else:
            _log_phase("uploading", "mode=sftp_walk")
            client = pod.open_ssh_client()
            try:
                sftp = client.open_sftp()
                try:
                    progress = UploadHeartbeat(label="sftp_upload")
                    upload_dir(sftp, ROOT, REMOTE_ROOT, exclude, progress=progress)
                    progress.tick(force=True)
                finally:
                    sftp.close()
            finally:
                client.close()
        print("upload_complete=true", flush=True)

        _log_phase("starting_remote", f"timeout={timeout}")
        code, stdout, stderr = await pod.exec_ssh(remote_script, timeout=timeout)
        print(stdout, flush=True)
        if stderr.strip():
            print(stderr, flush=True)
        result_code = code
        return result_code
    except asyncio.CancelledError:
        _clear_current_task_cancellation()
        result_code = 130
        _log_phase("cancelled", "exit_code=130")
        return result_code
    finally:
        pod_id = getattr(guard.pod, "id", "")
        _log_phase("terminating", f"pod_id={pod_id}" if pod_id else "")
        await guard.terminate()
        print("terminated_launched_pod=true", flush=True)
        if result_code is not None:
            _log_phase("done", f"exit_code={result_code}")


async def run_pod_detached(
    remote_script: str,
    *,
    name_prefix: str,
    exclude: set[str],
    upload_mode: Literal["sftp_walk", "tarball"] = "sftp_walk",
    timeout: int,
    poll_interval: int = 60,
) -> int:
    guard = PodGuard(name_prefix=name_prefix, default_max_runtime_seconds=max(timeout * 2, 7200))
    install_signal_handlers(asyncio.get_running_loop())
    result_code: int | None = None
    artifact_root: Path | None = None
    upload_info: dict[str, Any] = {"mode": upload_mode}
    remote_command: str | None = None
    terminated = False
    try:
        _log_phase("launching", f"name_prefix={name_prefix} upload_mode={upload_mode} timeout={timeout}")
        pod = await guard.launch()
        _log_pod_identity(pod)
        _log_phase("waiting_ssh", f"pod_id={pod.id}")
        await pod.wait_ready(timeout=300)
        ssh_details = await pod._ensure_ssh_details()
        print(f"pod_ssh=root@{ssh_details['ip']} -p {ssh_details['port']}", flush=True)
        _log_phase("gpu_check", f"pod_id={pod.id}")
        code, stdout, stderr = await pod.exec_ssh("nvidia-smi -L", timeout=60)
        print(stdout.strip(), flush=True)
        if code != 0:
            print(stderr, flush=True)
            result_code = code
            return result_code

        if upload_mode == "tarball":
            upload_info = await _upload_tarball(pod, exclude)
        else:
            _log_phase("uploading", "mode=sftp_walk")
            client = pod.open_ssh_client()
            try:
                sftp = client.open_sftp()
                try:
                    progress = UploadHeartbeat(label="sftp_upload")
                    upload_dir(sftp, ROOT, REMOTE_ROOT, exclude, progress=progress)
                    progress.tick(force=True)
                finally:
                    sftp.close()
            finally:
                client.close()
        print("upload_complete=true", flush=True)

        _log_phase("starting_remote", "mode=detached")
        await _upload_remote_script(pod, remote_script)
        launch_command = (
            f"cd {REMOTE_ROOT} && mkdir -p out/corpus_matrix "
            "&& rm -f out/corpus_matrix/exit_code "
            "&& nohup bash /tmp/vibecomfy-remote-run.sh "
            "> /tmp/vibecomfy-remote-live.log 2>&1; "
            'rc=$?; printf "%s" "$rc" > out/corpus_matrix/exit_code; exit "$rc"'
        )
        remote_command = launch_command
        code, stdout, stderr = await pod.exec_ssh(f"nohup bash -lc {launch_command!r} >/tmp/vibecomfy-launch.log 2>&1 & echo $!", timeout=30)
        if stdout.strip():
            print(f"remote_pid={stdout.strip()}", flush=True)
        if code != 0:
            print(stderr, flush=True)
            result_code = code
            return result_code

        _log_phase("polling", f"interval_seconds={poll_interval} timeout={timeout}")
        start = time.monotonic()
        last_snapshot = ""
        while True:
            if time.monotonic() - start > timeout:
                print(f"detached_timeout={timeout}", flush=True)
                result_code = 124
                return result_code
            status_command = f"""
cd {REMOTE_ROOT}
echo "=== POLL $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
if [ -f out/corpus_matrix/results.tsv ]; then echo "--- RESULTS ---"; cat out/corpus_matrix/results.tsv; fi
if [ -f out/corpus_matrix/ready_results.tsv ]; then echo "--- READY ---"; cat out/corpus_matrix/ready_results.tsv; fi
echo "--- MEDIA ---"
find out/corpus_matrix output -maxdepth 5 -type f \\( -name '*.png' -o -name '*.mp4' -o -name '*.webp' -o -name '*.webm' \\) -printf '%TY-%Tm-%Td %TH:%TM %s %p\\n' 2>/dev/null | sort | tail -80
echo "--- LOG ---"
tail -80 /tmp/vibecomfy-remote-live.log 2>/dev/null || true
tail -80 out/corpus_matrix/live.log 2>/dev/null || true
echo "--- EXIT ---"
cat out/corpus_matrix/exit_code 2>/dev/null || true
"""
            try:
                code, stdout, stderr = await pod.exec_ssh(status_command, timeout=60)
            except Exception as exc:
                print(f"poll_ssh_failed={exc}", flush=True)
                await asyncio.sleep(poll_interval)
                continue
            snapshot = stdout.strip()
            if snapshot and snapshot != last_snapshot:
                print(snapshot, flush=True)
                last_snapshot = snapshot
            if stderr.strip():
                print(stderr, flush=True)
            if code != 0:
                result_code = code
                return result_code
            exit_code = _parse_detached_exit(stdout)
            if exit_code is not None:
                result_code = exit_code
                try:
                    artifact_root = await _download_artifacts(
                        pod,
                        exit_code=exit_code,
                        remote_command=remote_command,
                        upload=upload_info,
                    )
                except OSError as exc:
                    print(f"artifact_download_failed={exc}", flush=True)
                return result_code
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        _clear_current_task_cancellation()
        result_code = 130
        _log_phase("cancelled", "exit_code=130")
        return result_code
    finally:
        pod_id = getattr(guard.pod, "id", "")
        _log_phase("terminating", f"pod_id={pod_id}" if pod_id else "")
        await guard.terminate()
        terminated = True
        print("terminated_launched_pod=true", flush=True)
        if result_code is not None:
            if artifact_root is not None:
                _finalize_artifacts(
                    artifact_root,
                    pod_id=pod_id or None,
                    exit_code=result_code,
                    mode="detached",
                    terminated=terminated,
                    remote_command=remote_command,
                    upload=upload_info,
                )
            _log_phase("done", f"exit_code={result_code}")
            _print_detached_summary(
                pod_id=pod_id or None,
                exit_code=result_code,
                terminated=terminated,
                artifact_root=artifact_root,
            )


def _runpod_lifecycle():
    import sys

    sys.path.insert(0, str(runpod_lifecycle_root() / "src"))
    from dotenv import load_dotenv
    from runpod_lifecycle import RunPodConfig, launch

    return load_dotenv, RunPodConfig, launch


async def _upload_remote_script(pod, remote_script: str) -> None:
    handle = tempfile.NamedTemporaryFile(prefix="vibecomfy-remote-run-", suffix=".sh", mode="w", delete=False)
    script_path = Path(handle.name)
    try:
        handle.write(remote_script)
        handle.write("\n")
        handle.close()
        client = pod.open_ssh_client()
        try:
            sftp = client.open_sftp()
            try:
                sftp.put(str(script_path), "/tmp/vibecomfy-remote-run.sh", confirm=False)
            finally:
                sftp.close()
        finally:
            client.close()
        code, stdout, stderr = await pod.exec_ssh("chmod +x /tmp/vibecomfy-remote-run.sh", timeout=30)
        if code != 0:
            print(stdout, flush=True)
            print(stderr, flush=True)
            raise RuntimeError(f"remote script chmod failed with exit code {code}")
    finally:
        script_path.unlink(missing_ok=True)


async def _download_artifacts(
    pod,
    *,
    exit_code: int | None = None,
    remote_command: str | None = None,
    upload: dict[str, Any] | None = None,
) -> Path | None:
    local_root = _new_artifact_root()
    local_root.mkdir(parents=True, exist_ok=True)
    remote_archive = "/tmp/vibecomfy-artifacts.tar.gz"
    _log_phase("downloading_artifacts", f"local={local_root.relative_to(ROOT)}")
    code, stdout, stderr = await pod.exec_ssh(
        f"cd {REMOTE_ROOT} || exit $?; "
        "mkdir -p out/corpus_matrix; "
        "cp /tmp/vibecomfy-remote-live.log out/corpus_matrix/remote_live.log 2>/dev/null || true; "
        "cp /tmp/vibecomfy-remote-run.sh out/corpus_matrix/remote_run.sh 2>/dev/null || true; "
        "paths=''; "
        "for path in out/corpus_matrix output out/runs; do if [ -e \"$path\" ]; then paths=\"$paths $path\"; fi; done; "
        "if [ -z \"$paths\" ]; then mkdir -p /tmp/vibecomfy-empty-artifacts && "
        f"tar -czf {remote_archive} -C /tmp/vibecomfy-empty-artifacts .; "
        f"elif ! tar -czf {remote_archive} $paths 2>/tmp/vibecomfy-artifact-tar.err; then "
        "cat /tmp/vibecomfy-artifact-tar.err; exit 1; fi",
        timeout=300,
    )
    if code != 0:
        print(stdout, flush=True)
        if stderr.strip():
            print(stderr, flush=True)
        print("artifact_download_failed=archive", flush=True)
        return None
    client = pod.open_ssh_client()
    try:
        sftp = client.open_sftp()
        try:
            archive = local_root / "artifacts.tar.gz"
            sftp.get(remote_archive, str(archive))
        finally:
            sftp.close()
    except Exception as exc:
        print(f"artifact_download_failed={exc}", flush=True)
        return None
    finally:
        client.close()
    with tarfile.open(local_root / "artifacts.tar.gz", "r:gz") as tar:
        tar.extractall(local_root)
    _finalize_artifacts(
        local_root,
        pod_id=getattr(pod, "id", None),
        exit_code=exit_code,
        mode="detached",
        remote_command=remote_command,
        upload=upload,
    )
    print(f"artifact_downloaded={local_root.relative_to(ROOT)}", flush=True)
    return local_root


def _new_artifact_root() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = ROOT / "out" / "runpod_artifacts" / stamp
    if not root.exists():
        return root
    suffix = 1
    while True:
        candidate = ROOT / "out" / "runpod_artifacts" / f"{stamp}-{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1


def _parse_tsv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not reader.fieldnames:
                return []
            rows: list[dict[str, str]] = []
            for row in reader:
                rows.append({str(key): "" if value is None else value for key, value in row.items() if key is not None})
            return rows
    except OSError:
        return []


def _image_info(path: Path) -> dict[str, Any] | None:
    try:
        from PIL import Image
    except Exception:
        return _png_info(path)
    try:
        with Image.open(path) as image:
            return {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
            }
    except Exception:
        return None


def _png_info(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() != ".png":
        return None
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return {
        "width": width,
        "height": height,
        "format": "PNG",
        "mode": None,
    }


def _finalize_artifacts(
    local_root: Path,
    *,
    pod_id: str | None = None,
    exit_code: int | None = None,
    mode: str = "detached",
    terminated: bool | None = None,
    remote_command: str | None = None,
    upload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = _build_artifact_manifest(
        local_root,
        pod_id=pod_id,
        exit_code=exit_code,
        mode=mode,
        terminated=terminated,
        remote_command=remote_command,
        upload=upload,
    )
    manifest_path = local_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path = _write_artifact_report(local_root, manifest)
    manifest["manifest_path"] = _display_path(manifest_path)
    manifest["report_path"] = _display_path(report_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return manifest


def _build_artifact_manifest(
    local_root: Path,
    *,
    pod_id: str | None = None,
    exit_code: int | None = None,
    mode: str = "detached",
    terminated: bool | None = None,
    remote_command: str | None = None,
    upload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    loaded_manifest = _load_json(local_root / "manifest.json")
    existing = loaded_manifest if isinstance(loaded_manifest, dict) else {}
    generated_at = existing.get("generated_at") or datetime.now(timezone.utc).isoformat()
    archive = local_root / "artifacts.tar.gz"
    results_path = local_root / "out" / "corpus_matrix" / "results.tsv"
    results = _parse_tsv(results_path)
    outputs = _collect_outputs(local_root)
    run_metadata, metadata_warnings = _collect_run_metadata(local_root)
    watchdogs, watchdog_warnings = _collect_watchdogs(local_root, run_metadata)
    remote_logs = _collect_remote_logs(local_root)
    remote_script = _file_record(local_root / "out" / "corpus_matrix" / "remote_run.sh", local_root)
    failures = _count_failures(results)
    warnings = metadata_warnings + watchdog_warnings
    status = "unknown"
    if exit_code is not None:
        status = "pass" if exit_code == 0 and failures == 0 else "fail"
    manifest: dict[str, Any] = {
        "generated_at": generated_at,
        "pod_id": pod_id,
        "mode": mode,
        "remote_root": REMOTE_ROOT,
        "artifact_root": _display_path(local_root),
        "exit_code": exit_code,
        "terminated": terminated,
        "status": status,
        "summary": {
            "status": status,
            "outputs": len(outputs),
            "result_rows": len(results),
            "failures": failures,
            "warnings": len(warnings),
            "exit_code": exit_code,
            "terminated": terminated,
        },
        "archive": _file_record(archive, local_root) if archive.exists() else None,
        "upload": upload or {},
        "remote_command": remote_command,
        "remote_script": remote_script,
        "results": {
            "path": _display_path(results_path) if results_path.exists() else None,
            "rows": results,
        },
        "outputs": outputs,
        "run_metadata": run_metadata,
        "watchdogs": watchdogs,
        "remote_logs": remote_logs,
        "warnings": warnings,
    }
    return manifest


def _collect_outputs(local_root: Path) -> list[dict[str, Any]]:
    output_root = local_root / "output"
    if not output_root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in output_root.rglob("*") if item.is_file()):
        record = _file_record(path, local_root)
        if record is None:
            continue
        record["output_relative_path"] = path.relative_to(output_root).as_posix()
        info = _image_info(path)
        if info is not None:
            record["image"] = info
        records.append(record)
    return records


def _collect_run_metadata(local_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    runs_root = local_root / "out" / "runs"
    if not runs_root.exists():
        return records, warnings
    for path in sorted(runs_root.glob("*/metadata.json")):
        data = _load_json(path)
        if not isinstance(data, dict):
            warnings.append(f"invalid run metadata: {_display_path(path)}")
            continue
        queued = data.get("queued")
        prompt_id = _extract_prompt_id(queued)
        outputs = data.get("outputs") if isinstance(data.get("outputs"), list) else []
        records.append(
            {
                "path": _display_path(path),
                "relative_path": path.relative_to(local_root).as_posix(),
                "run_id": data.get("run_id") or path.parent.name,
                "workflow_id": data.get("workflow_id"),
                "runtime": data.get("runtime"),
                "prompt_id": prompt_id,
                "outputs": outputs,
                "workflow_hash": data.get("workflow_hash"),
                "git_sha": data.get("git_sha"),
                "metadata": data,
            }
        )
    return records, warnings


def _collect_watchdogs(
    local_root: Path,
    run_metadata: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    outputs_by_run = {
        str(record.get("run_id")): bool(record.get("outputs"))
        for record in run_metadata
        if record.get("run_id")
    }
    runs_root = local_root / "out" / "runs"
    if not runs_root.exists():
        return records, warnings
    for path in sorted(runs_root.glob("*/watchdog.json")):
        data = _load_watchdog_json(path)
        if not isinstance(data, dict):
            warnings.append(f"invalid watchdog report: {_display_path(path)}")
            continue
        state = data.get("state") if isinstance(data.get("state"), dict) else {}
        run_id = path.parent.name
        diagnosis = data.get("diagnosis")
        stop_reason = state.get("stop_reason")
        record = {
            "path": _display_path(path),
            "relative_path": path.relative_to(local_root).as_posix(),
            "run_id": run_id,
            "diagnosis": diagnosis,
            "diagnosis_reason": data.get("diagnosis_reason"),
            "stop_reason": stop_reason,
            "elapsed_seconds": data.get("elapsed_seconds"),
            "prompt_id": state.get("prompt_id"),
            "current_node_id": state.get("current_node_id"),
            "current_node_class_type": state.get("current_node_class_type"),
            "state": state,
        }
        records.append(record)
        if diagnosis == "crashed" and stop_reason == "completed" and outputs_by_run.get(run_id):
            warnings.append(
                f"watchdog diagnosis=crashed for run_id={run_id} but stop_reason=completed and outputs exist"
            )
    return records, warnings


def _collect_remote_logs(local_root: Path) -> list[dict[str, Any]]:
    candidates = [
        local_root / "out" / "corpus_matrix" / "remote_live.log",
        local_root / "out" / "corpus_matrix" / "live.log",
        local_root / "out" / "corpus_matrix" / "remote_run.sh",
    ]
    runs_root = local_root / "out" / "runs"
    if runs_root.exists():
        candidates.extend(sorted(runs_root.glob("*/*.log")))
    seen: set[Path] = set()
    logs: list[dict[str, Any]] = []
    for path in candidates:
        if path in seen or not path.exists() or not path.is_file():
            continue
        seen.add(path)
        record = _file_record(path, local_root)
        if record is not None:
            logs.append(record)
    return logs


def _write_artifact_report(local_root: Path, manifest: dict[str, Any]) -> Path:
    report_path = local_root / "report.md"
    summary = manifest.get("summary", {})
    lines = [
        "# RunPod Evidence Report",
        "",
        "## Summary",
        "",
        f"- status: {summary.get('status')}",
        f"- exit_code: {summary.get('exit_code')}",
        f"- pod_id: {manifest.get('pod_id') or '-'}",
        f"- terminated: {summary.get('terminated')}",
        f"- artifact_root: {manifest.get('artifact_root')}",
        f"- outputs: {summary.get('outputs')}",
        f"- failures: {summary.get('failures')}",
        f"- warnings: {summary.get('warnings')}",
        "",
        "## Evidence",
        "",
        f"- archive: {((manifest.get('archive') or {}).get('relative_path')) or '-'}",
        f"- remote_script: {((manifest.get('remote_script') or {}).get('relative_path')) or '-'}",
        f"- upload_mode: {((manifest.get('upload') or {}).get('mode')) or '-'}",
        f"- remote_command: `{_md(manifest.get('remote_command') or '-')}`",
        "",
    ]
    remote_logs = manifest.get("remote_logs") or []
    if remote_logs:
        lines.extend(["## Logs", ""])
        for log in remote_logs:
            lines.append(f"- {log.get('relative_path')} ({log.get('bytes')} bytes)")
        lines.append("")
    warnings = manifest.get("warnings") or []
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {_md(str(warning))}" for warning in warnings)
        lines.append("")
    rows = (manifest.get("results") or {}).get("rows") or []
    if rows:
        lines.extend(["## Results", ""])
        columns = list(rows[0].keys())
        lines.append("| " + " | ".join(_md(column) for column in columns) + " |")
        lines.append("| " + " | ".join("---" for _ in columns) + " |")
        for row in rows:
            lines.append("| " + " | ".join(_md(row.get(column, "")) for column in columns) + " |")
        lines.append("")
    outputs = manifest.get("outputs") or []
    if outputs:
        lines.extend(["## Outputs", ""])
        lines.append("| path | bytes | extension | dimensions |")
        lines.append("| --- | ---: | --- | --- |")
        for output in outputs:
            image = output.get("image") or {}
            dimensions = f"{image.get('width')}x{image.get('height')}" if image.get("width") and image.get("height") else "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(output.get("relative_path", "")),
                        str(output.get("bytes", "")),
                        _md(output.get("extension", "")),
                        _md(dimensions),
                    ]
                )
                + " |"
            )
        lines.append("")
    run_metadata = manifest.get("run_metadata") or []
    if run_metadata:
        lines.extend(["## Runs", ""])
        lines.append("| run_id | workflow_id | runtime | prompt_id | outputs |")
        lines.append("| --- | --- | --- | --- | ---: |")
        for record in run_metadata:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(record.get("run_id", "")),
                        _md(record.get("workflow_id", "")),
                        _md(record.get("runtime", "")),
                        _md(record.get("prompt_id", "")),
                        str(len(record.get("outputs") or [])),
                    ]
                )
                + " |"
            )
        lines.append("")
    watchdogs = manifest.get("watchdogs") or []
    if watchdogs:
        lines.extend(["## Watchdogs", ""])
        lines.append("| run_id | diagnosis | stop_reason | elapsed_seconds | prompt_id |")
        lines.append("| --- | --- | --- | ---: | --- |")
        for record in watchdogs:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(record.get("run_id", "")),
                        _md(record.get("diagnosis", "")),
                        _md(record.get("stop_reason", "")),
                        str(record.get("elapsed_seconds", "")),
                        _md(record.get("prompt_id", "")),
                    ]
                )
                + " |"
            )
        lines.append("")
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def _print_detached_summary(
    *,
    pod_id: str | None,
    exit_code: int,
    terminated: bool,
    artifact_root: Path | None,
) -> None:
    manifest: dict[str, Any] = {}
    if artifact_root is not None:
        loaded = _load_json(artifact_root / "manifest.json")
        if isinstance(loaded, dict):
            manifest = loaded
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    failures = int(summary.get("failures") or 0)
    outputs = int(summary.get("outputs") or 0)
    status = summary.get("status") or ("pass" if exit_code == 0 and failures == 0 else "fail")
    print(f"status={status} exit_code={exit_code}", flush=True)
    if pod_id:
        print(f"pod_id={pod_id}", flush=True)
    print(f"terminated={str(terminated).lower()}", flush=True)
    if artifact_root is not None:
        print(f"artifact_dir={_display_path(artifact_root)}", flush=True)
        print(f"manifest={_display_path(artifact_root / 'manifest.json')}", flush=True)
        print(f"report={_display_path(artifact_root / 'report.md')}", flush=True)
    print(f"outputs={outputs}", flush=True)
    print(f"failures={failures}", flush=True)


def _file_record(path: Path, root: Path) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return {
        "path": _display_path(path),
        "relative_path": path.relative_to(root).as_posix(),
        "bytes": stat.st_size,
        "extension": path.suffix.lower(),
        "sha256": _sha256(path),
    }


def _sha256(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_watchdog_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            return None
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            return None


def _extract_prompt_id(value: Any) -> str | None:
    if isinstance(value, dict):
        direct = value.get("prompt_id")
        if isinstance(direct, str):
            return direct
        for item in value.values():
            found = _extract_prompt_id(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _extract_prompt_id(item)
            if found:
                return found
    if isinstance(value, str):
        match = re.search(r"(?:prompt_id['\"]?\s*[:=]\s*['\"]?)([A-Za-z0-9_.:-]+)", value)
        if match:
            return match.group(1)
    return None


def _count_failures(rows: list[dict[str, str]]) -> int:
    passing = {"ok", "pass", "passed", "success", "succeeded"}
    failures = 0
    for row in rows:
        status = (row.get("status") or row.get("result") or "").strip().lower()
        if status and status not in passing:
            failures += 1
    return failures


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _parse_detached_exit(stdout: str) -> int | None:
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line == "--- EXIT ---" and index + 1 < len(lines):
            value = lines[index + 1].strip()
            if value.isdigit():
                return int(value)
    return None


async def _upload_tarball(pod, exclude: set[str]) -> dict[str, Any]:
    tar_path = _build_upload_tarball(exclude)
    upload_info = {
        "mode": "tarball",
        "local_archive_path": tar_path.as_posix(),
        "remote_archive_path": "/tmp/vibecomfy-upload.tar.gz",
        "archive_bytes": tar_path.stat().st_size,
        "excludes": sorted(exclude),
    }
    try:
        _log_phase("uploading", f"mode=tarball size={_format_bytes(tar_path.stat().st_size)}")
        client = pod.open_ssh_client()
        try:
            sftp = client.open_sftp()
            try:
                progress = UploadHeartbeat(label="tarball_upload")

                def _progress(sent: int, total: int) -> None:
                    progress.bytes = sent
                    progress.files = 1
                    now = time.monotonic()
                    if sent == total or now - progress.last_log >= progress.every_seconds:
                        print(
                            f"tarball_upload_progress bytes={sent} total_bytes={total} "
                            f"size={_format_bytes(sent)} total_size={_format_bytes(total)}",
                            flush=True,
                        )
                        progress.last_log = now

                sftp.put(str(tar_path), "/tmp/vibecomfy-upload.tar.gz", callback=_progress, confirm=False)
            finally:
                sftp.close()
        finally:
            client.close()
        _log_phase("extracting", f"remote_root={REMOTE_ROOT}")
        code, stdout, stderr = await pod.exec_ssh(
            f"rm -rf {REMOTE_ROOT} && mkdir -p {REMOTE_ROOT} && tar --no-same-owner -xzf /tmp/vibecomfy-upload.tar.gz -C {REMOTE_ROOT}",
            timeout=300,
        )
        if code != 0:
            print(stdout, flush=True)
            print(stderr, flush=True)
            raise RuntimeError(f"remote tarball extraction failed with exit code {code}")
        return upload_info
    finally:
        tar_path.unlink(missing_ok=True)


def _upload_tmpdir() -> Path:
    configured = os.getenv("VIBECOMFY_UPLOAD_TMPDIR")
    temp_dir = Path(configured).expanduser() if configured else Path(tempfile.gettempdir())
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _iter_upload_files(root: Path, exclude: set[str]) -> Iterable[Path]:
    for current, dir_names, file_names in os.walk(root):
        current_path = Path(current)
        dir_names[:] = [
            name for name in dir_names if not should_skip(current_path / name, root, exclude)
        ]
        for file_name in file_names:
            path = current_path / file_name
            if should_skip(path, root, exclude):
                continue
            yield path


def _estimate_upload_payload(root: Path, exclude: set[str]) -> tuple[list[Path], int]:
    files: list[Path] = []
    total_bytes = 0
    heartbeat = UploadHeartbeat(label="upload_scan")
    for path in _iter_upload_files(root, exclude):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        files.append(path)
        total_bytes += size
        heartbeat.tick(files=1, bytes_added=size)
    heartbeat.tick(force=True)
    return files, total_bytes


def _preflight_upload_disk(temp_dir: Path, estimated_bytes: int) -> None:
    usage = shutil.disk_usage(temp_dir)
    min_free_bytes = int(os.getenv("VIBECOMFY_UPLOAD_MIN_FREE_BYTES", str(512 * MiB)))
    required_free = max(min_free_bytes, int(estimated_bytes * 0.25))
    if usage.free >= required_free:
        return
    raise RuntimeError(
        "insufficient local disk for RunPod upload tarball: "
        f"tmpdir={temp_dir} free={_format_bytes(usage.free)} "
        f"estimated_payload={_format_bytes(estimated_bytes)} required_free={_format_bytes(required_free)}. "
        "Free disk space, set VIBECOMFY_UPLOAD_TMPDIR to a larger volume, or add excludes for bulky local paths."
    )


def _build_upload_tarball(exclude: set[str], *, root: Path = ROOT) -> Path:
    _log_phase("building_upload", f"mode=tarball root={root}")
    temp_dir = _upload_tmpdir()
    files, estimated_bytes = _estimate_upload_payload(root, exclude)
    _log_phase(
        "building_upload",
        f"files={len(files)} estimated_payload={_format_bytes(estimated_bytes)} tmpdir={temp_dir}",
    )
    _preflight_upload_disk(temp_dir, estimated_bytes)

    handle = tempfile.NamedTemporaryFile(prefix="vibecomfy-upload-", suffix=".tar.gz", dir=temp_dir, delete=False)
    tar_path = Path(handle.name)
    handle.close()
    heartbeat = UploadHeartbeat(label="tarball_build")
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            for path in files:
                tar.add(path, arcname=path.relative_to(root))
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                heartbeat.tick(files=1, bytes_added=size)
        heartbeat.tick(force=True)
        _log_phase("building_upload", f"archive={tar_path} size={_format_bytes(tar_path.stat().st_size)}")
    except Exception:
        tar_path.unlink(missing_ok=True)
        raise
    return tar_path
