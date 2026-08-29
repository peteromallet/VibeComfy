"""End-to-end RunPod matrix for regeneratable ready templates.

Reuses ``scripts/runpod_matrix_plan.py`` types / manifest paths and
``scripts/runpod_runner.py`` shipping helpers.  Adds a regeneratable
filter (FLAG-001) that scans ``coverage.json`` for ``ready_template: true``
(boolean) entries — yielding ~43 rows vs the 15 from scope='all'.

Usage::

    python3 scripts/runpod_e2e_matrix.py --dry-run
    python3 scripts/runpod_e2e_matrix.py --scope ltx --limit 5
    python3 scripts/runpod_e2e_matrix.py --scope wan_wrapper

Dry-run prints plan + remote command WITHOUT network or RUNPOD_API_KEY.
Real mode ships a pod, executes, and writes out/e2e/<YYYYMMDD>/results.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the repo root is on sys.path so that ``import scripts.runpod_*``
# works regardless of how this file is invoked (e.g. ``python3 scripts/...``
# vs ``PYTHONPATH=. python scripts/...``).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# -- constants defined locally so dry-run never needs runpod_runner/artifacts --
ROOT: Path = _REPO_ROOT
REMOTE_ROOT: str = "/workspace/vibecomfy"
REGENERATABLE_MANIFEST: str = "ready_templates/sources/manifests/coverage.json"
ESTIMATED_COST_PER_TEMPLATE: float = 0.25
DEFAULT_UPLOAD_EXCLUDES: set[str] = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".desloppify", ".megaplan",
    "out", "output", "vendor", "ready_templates/sources", "custom_nodes", "input",
    "node_modules", ".mypy_cache", ".ruff_cache", ".DS_Store",
}
_NON_FAILURE_ROW_STATUSES = frozenset({"ok", "skipped"})

# MatrixRow is a lightweight dataclass from runpod_matrix_plan (no heavy deps).
# We import it directly; the rest of runpod_matrix_plan is not needed here.
from scripts.runpod_matrix_plan import MatrixRow  # noqa: E402

# ---------------------------------------------------------------------------
# Regeneratable filter (FLAG-001)
# ---------------------------------------------------------------------------


def _load_coverage_manifest(root: Path | None = None) -> list[dict[str, Any]]:
    """Load coverage.json workflow entries."""
    if root is None:
        root = ROOT
    manifest_path = root / REGENERATABLE_MANIFEST
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return list(data.get("workflows", []))


def build_regeneratable_matrix(
    root: Path | None = None,
    *,
    scope: str = "all",
    manifest: str = REGENERATABLE_MANIFEST,
) -> tuple[MatrixRow, ...]:
    """Return ready_template rows where ``ready_template`` is ``True`` (boolean).

    This is the regeneratable filter (FLAG-001): boolean ``ready_template``
    entries are supplemental workflows whose ready templates are regeneratable
    from source.  The 15 string-path entries are the core required tier and are
    handled by ``build_corpus_matrix_plan(scope='all')`` separately.

    Returns ~43 rows vs the 15 from the default scope='all' plan.
    """
    if root is None:
        root = ROOT
    entries = _load_coverage_manifest(root)
    rows: list[MatrixRow] = []

    for item in entries:
        # Only boolean ready_template — not string paths
        if item.get("ready_template") is not True:
            continue

        workflow_id = item.get("id", "")
        media = item.get("media", "unknown")

        # Scope filtering (reusing the same scope names as runpod_matrix_plan)
        if scope not in ("all", ""):
            if not _matches_regeneratable_scope(workflow_id, media, scope):
                continue

        # Verify the ready template file exists
        ready_path = _ready_template_path(root, workflow_id, media)
        if not ready_path.exists():
            continue

        rows.append(
            MatrixRow(
                id=workflow_id,
                path=ready_path.relative_to(root).as_posix(),
                media=media,
                task=item.get("task", ""),
            )
        )

    return tuple(rows)


def _ready_template_path(root: Path, workflow_id: str, media: str) -> Path:
    """Resolve the on-disk ready template path for a boolean ready_template entry."""
    # Boolean ready_template entries follow the convention:
    # ready_templates/<media>/<id>.py
    return root / "ready_templates" / media / f"{workflow_id}.py"


def _matches_regeneratable_scope(workflow_id: str, media: str, scope: str) -> bool:
    """Match a regeneratable entry against a scope filter."""
    if scope == "wan" or scope == "wan_wrapper":
        return workflow_id.startswith("wanvideo_wrapper")
    if scope == "ltx":
        return workflow_id.startswith("ltx2_3")
    if scope == "flux" or scope == "flux2":
        return workflow_id.startswith("flux2_klein")
    if scope == "qwen_tts":
        return workflow_id.startswith("qwen3_tts")
    if scope == "image":
        return media == "image"
    if scope == "video":
        return media == "video"
    if scope == "audio":
        return media == "audio"
    return True


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def _estimate_cost(template_count: int) -> float:
    return round(template_count * ESTIMATED_COST_PER_TEMPLATE, 2)


# ---------------------------------------------------------------------------
# Dry-run output
# ---------------------------------------------------------------------------


def _dry_run_output(
    rows: tuple[MatrixRow, ...],
    scope: str,
    output_root: Path,
    remote_script_body: str,
) -> str:
    lines: list[str] = []
    lines.append("=== E2E Matrix Dry-Run ===")
    lines.append(f"Scope: {scope or 'all'}")
    lines.append(f"Selected regeneratable templates: {len(rows)}")
    lines.append(f"Estimated cost: ${_estimate_cost(len(rows)):.2f}")
    lines.append(f"Output root: {output_root}")
    lines.append("")
    lines.append("--- Template IDs ---")
    for row in rows:
        lines.append(f"  {row.id}  ({row.media})  [{row.path}]")
    lines.append("")
    lines.append("--- Remote Command (first 2000 chars) ---")
    lines.append(remote_script_body[:2000])
    if len(remote_script_body) > 2000:
        lines.append(f"... ({len(remote_script_body) - 2000} more chars)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Remote script generation
# ---------------------------------------------------------------------------


def _build_remote_script(
    rows: tuple[MatrixRow, ...],
    *,
    attention_profile: str = "portable",
    seed: int = 123,
    steps: int = 1,
    prompt: str = "a compact red cube on a neutral background",
    timeout_per_template: int = 1800,
) -> str:
    """Build the remote bash/Python script run on the pod.

    The script sets up the vibecomfy environment and runs each ready template
    via ``vibecomfy.cli run``, recording results to a JSON file.
    """
    template_ids = [row.id for row in rows]
    template_paths = [row.path for row in rows]

    # Escape for safe embedding in bash
    ids_json = json.dumps(template_ids)
    paths_json = json.dumps(template_paths)

    return f"""\
set -euo pipefail
cd {REMOTE_ROOT}
export XDG_CACHE_HOME=/tmp/vibecomfy-cache
export UV_CACHE_DIR=/tmp/vibecomfy-cache/uv
export HF_HOME=/workspace/.cache/huggingface
export HF_HUB_DISABLE_XET=1
export PIP_CACHE_DIR=/workspace/.cache/pip
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export VIBECOMFY_ATTENTION_PROFILE={shlex.quote(attention_profile)}
mkdir -p "$XDG_CACHE_HOME" "$UV_CACHE_DIR" "$HF_HOME" "$PIP_CACHE_DIR"
find "$HF_HOME" -type f -name '*.incomplete' -delete 2>/dev/null || true
PY=python3
$PY -m pip install --upgrade pip wheel setuptools
$PY -m pip install -e '.[dev]'
$PY -m pip install --prefer-binary pillow 'numpy<2.3'

mkdir -p out/e2e out/e2e/output out/e2e/logs

"$PY" - <<'PY'
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

TEMPLATE_IDS = {ids_json}
TEMPLATE_PATHS = {paths_json}
OUTPUT_ROOT = Path("out/e2e")
RESULTS_PATH = OUTPUT_ROOT / "results.json"
SEED = {seed}
STEPS = {steps}
PROMPT = {shlex.quote(prompt)}
TIMEOUT_PER = {timeout_per_template}

results = []
for idx, (tid, tpath) in enumerate(zip(TEMPLATE_IDS, TEMPLATE_PATHS)):
    tpath_obj = Path(tpath)
    print(f"\\n=== E2E [{{idx+1}}/{{len(TEMPLATE_IDS)}}] {{tid}} ===")
    entry = {{
        "template_id": tid,
        "template_path": tpath,
        "status": "unknown",
        "elapsed_seconds": 0,
        "output_sha256s": [],
        "peak_vram_bytes": None,
        "failure": None,
    }}
    if not tpath_obj.exists():
        entry["status"] = "template_missing"
        entry["failure"] = f"template file not found: {{tpath}}"
        results.append(entry)
        continue

    start = time.monotonic()
    log_path = OUTPUT_ROOT / "logs" / f"{{tid}}.log"
    try:
        proc = subprocess.run(
            [
                sys.executable, "-m", "vibecomfy.cli", "run",
                tpath,
                "--runtime", "embedded",
                "--backend", "api",
                "--steps", str(STEPS),
                "--seed", str(SEED),
                "--prompt", PROMPT,
                "--output-directory", str(OUTPUT_ROOT / "output" / tid),
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_PER,
        )
        elapsed = time.monotonic() - start
        entry["elapsed_seconds"] = round(elapsed, 1)
        log_path.write_text(proc.stdout + "\\n" + proc.stderr, encoding="utf-8")

        if proc.returncode == 0:
            entry["status"] = "ok"
        else:
            entry["status"] = "run_failed"
            entry["failure"] = (
                proc.stderr.strip()[-500:] if proc.stderr.strip()
                else f"exit code {{proc.returncode}}"
            )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        entry["elapsed_seconds"] = round(elapsed, 1)
        entry["status"] = "timeout"
        entry["failure"] = f"timeout after {{TIMEOUT_PER}}s"
    except Exception:
        elapsed = time.monotonic() - start
        entry["elapsed_seconds"] = round(elapsed, 1)
        entry["status"] = "exception"
        entry["failure"] = traceback.format_exc()[-500:]

    # Collect output SHA256 sums
    template_output_dir = OUTPUT_ROOT / "output" / tid
    sha_list = []
    if template_output_dir.exists():
        for fpath in sorted(template_output_dir.rglob("*")):
            if fpath.is_file():
                digest = hashlib.sha256()
                try:
                    with fpath.open("rb") as fh:
                        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                            digest.update(chunk)
                    sha_list.append(
                        {{"path": str(fpath.relative_to(template_output_dir)), "sha256": digest.hexdigest()}}
                    )
                except OSError:
                    pass
    entry["output_sha256s"] = sha_list

    # Parse peak VRAM from watchdog (correctness-2)
    watchdog_path = OUTPUT_ROOT / "logs" / f"{{tid}}.watchdog.json"
    if not watchdog_path.exists():
        # Try alternate location (out/runs/*/)
        for candidate in sorted(Path("out/runs").glob("*/watchdog.json")):
            watchdog_path = candidate
            break
    if watchdog_path.exists():
        try:
            wd = json.loads(watchdog_path.read_text(encoding="utf-8"))
            vram_samples = wd.get("vram_samples", [])
            peak = 0
            for sample in vram_samples:
                total = sample.get("vram_total_bytes")
                free = sample.get("vram_free_bytes")
                if isinstance(total, (int, float)) and isinstance(free, (int, float)) and total > 0:
                    used = int(total - free)
                    if used > peak:
                        peak = used
            if peak > 0:
                entry["peak_vram_bytes"] = peak
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    results.append(entry)

RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
RESULTS_PATH.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
print(f"\\n=== E2E RESULTS: {{len(results)}} templates ===")
ok_count = sum(1 for r in results if r["status"] == "ok")
fail_count = len(results) - ok_count
print(f"ok={{ok_count}} fail={{fail_count}}")
print(f"results written to {{RESULTS_PATH}}")
PY

echo "=== E2E COMPLETE ==="
"$PY" -c 'import json, sys; d=json.load(open("out/e2e/results.json")); rows=d if isinstance(d, list) else []; valid=isinstance(d, list) and bool(d); ok=sum(1 for r in rows if isinstance(r, dict) and r.get("status")=="ok"); fail=sum(1 for r in rows if not isinstance(r, dict) or r.get("status") not in {{"ok", "skipped"}}); print("ok=" + str(ok) + " fail=" + str(fail)); raise SystemExit(1 if not valid or fail else 0)'
"""


# ---------------------------------------------------------------------------
# Previous-run diff logic
# ---------------------------------------------------------------------------


def _load_previous_results(output_root: Path) -> list[dict[str, Any]] | None:
    """Load previous results.json if it exists for diff comparison."""
    prev_path = output_root / "results.json"
    if not prev_path.exists():
        return None
    try:
        return json.loads(prev_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _diff_sha_changes(
    current: list[dict[str, Any]],
    previous: list[dict[str, Any]] | None,
) -> dict[str, list[str]]:
    """Compare sha256 values between current and previous run.

    Returns dict of template_id -> list of changed output paths.
    sha changes are flags, not automatic failures.
    """
    if previous is None:
        return {}

    prev_by_id: dict[str, dict[str, Any]] = {}
    for entry in previous:
        tid = entry.get("template_id")
        if isinstance(tid, str):
            prev_by_id[tid] = entry

    changes: dict[str, list[str]] = {}
    for entry in current:
        tid = entry.get("template_id")
        if not isinstance(tid, str) or tid not in prev_by_id:
            continue
        prev_entry = prev_by_id[tid]
        prev_shas = {s.get("path"): s.get("sha256") for s in prev_entry.get("output_sha256s", [])}
        curr_shas = {s.get("path"): s.get("sha256") for s in entry.get("output_sha256s", [])}

        for path, curr_hash in curr_shas.items():
            prev_hash = prev_shas.get(path)
            if prev_hash and curr_hash and prev_hash != curr_hash:
                changes.setdefault(tid, []).append(path)

    return changes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _run_real(
    rows: tuple[MatrixRow, ...],
    output_root: Path,
    attention_profile: str,
) -> tuple[int, Path | None]:
    """Ship and execute the e2e matrix on a RunPod pod (real mode).

    Imports ``scripts.runpod_runner`` lazily so dry-run never needs
    ``runpod_lifecycle`` or other RunPod launch dependencies.
    """
    from scripts.runpod_runner import run_pod_detached  # noqa: E402

    remote_script = _build_remote_script(rows, attention_profile=attention_profile)
    artifact_roots: list[Path | None] = []
    return_code = await run_pod_detached(
        remote_script,
        name_prefix="vibecomfy-e2e",
        exclude=DEFAULT_UPLOAD_EXCLUDES,
        upload_mode="tarball",
        timeout=28800,
        poll_interval=int(os.getenv("VIBECOMFY_RUNPOD_POLL_INTERVAL_SECONDS", "60")),
        artifact_root_out=artifact_roots,
    )
    return return_code, (artifact_roots[-1] if artifact_roots else None)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="E2E RunPod matrix for regeneratable ready templates.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without requiring network or RUNPOD_API_KEY.",
    )
    parser.add_argument(
        "--scope",
        default="all",
        help=(
            "Filter regeneratable templates by model scope "
            "(wan, ltx, flux, qwen_tts, image, video, audio, or 'all')."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of templates to run (cost control).",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Override output root (default: out/e2e/<YYYYMMDD>/).",
    )
    parser.add_argument(
        "--attention-profile",
        default="portable",
        choices=("portable", "sage"),
        help="Attention backend profile.",
    )
    args = parser.parse_args()

    # Build regeneratable matrix
    rows = build_regeneratable_matrix(ROOT, scope=args.scope)

    if not rows:
        print("No regeneratable templates matched. Check --scope filter.", file=sys.stderr)
        return 1

    # Apply limit
    if args.limit is not None and args.limit < len(rows):
        rows = rows[: args.limit]

    # Output root
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    if args.output_root:
        output_root = Path(args.output_root)
    else:
        output_root = ROOT / "out" / "e2e" / today

    # Build remote script (always generated, used for both dry-run and real)
    remote_script_body = _build_remote_script(rows, attention_profile=args.attention_profile)

    if args.dry_run:
        print(
            _dry_run_output(rows, args.scope, output_root, remote_script_body),
            flush=True,
        )
        return 0

    # Real mode — requires RUNPOD_API_KEY and network
    if not os.getenv("RUNPOD_API_KEY"):
        print(
            "RUNPOD_API_KEY not set. Use --dry-run for offline planning.",
            file=sys.stderr,
        )
        return 1

    # Ensure output directory exists locally (for results)
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"Shipping e2e matrix: {len(rows)} templates", flush=True)
    print(f"Output root: {output_root}", flush=True)
    print(f"Estimated cost: ${_estimate_cost(len(rows)):.2f}", flush=True)

    return_code, artifact_dir = asyncio.run(_run_real(rows, output_root, args.attention_profile))

    # Post-process only the artifact root returned by this run. Never infer a
    # run from a global directory scan, which can select stale artifacts.
    if artifact_dir is None:
        return _write_diagnostic_aggregate(
            output_root,
            "RunPod completed without returning a downloaded artifact root",
        )
    post_process_code = _post_process_results(artifact_dir, output_root)
    if post_process_code != 0:
        return post_process_code

    return return_code


def _parse_peak_vram_from_watchdogs(artifact_root: Path) -> dict[str, int | None]:
    """Parse watchdog JSON files for peak VRAM per template (correctness-2).

    Scans out/e2e/logs/*.watchdog.json and out/runs/*/watchdog.json.
    Returns dict of template_id -> peak_vram_bytes.
    """
    peak_by_id: dict[str, int | None] = {}

    # Check direct watchdog files in e2e logs
    logs_dir = artifact_root / "out" / "e2e" / "logs"
    for wd_path in sorted(logs_dir.glob("*.watchdog.json")):
        tid = wd_path.stem.split(".watchdog")[0] if ".watchdog" in wd_path.name else wd_path.stem
        peak = _extract_peak_vram_from_json(wd_path)
        if peak is not None:
            peak_by_id[tid] = peak

    # Also check run-level watchdog files
    from scripts.runpod_artifacts import _load_json  # noqa: E402
    runs_dir = artifact_root / "out" / "runs"
    for wd_path in sorted(runs_dir.glob("*/watchdog.json")):
        try:
            wd = _load_json(wd_path)
            if isinstance(wd, dict):
                # Try to map run_id to template_id via results.json
                state = wd.get("state", {}) if isinstance(wd.get("state"), dict) else {}
                prompt_id = state.get("prompt_id") or wd_path.parent.name
                peak = _extract_peak_vram_from_watchdog_data(wd)
                if peak is not None and prompt_id:
                    peak_by_id[str(prompt_id)] = peak
        except Exception:
            pass

    return peak_by_id


def _extract_peak_vram_from_json(path: Path) -> int | None:
    """Extract peak VRAM (used bytes) from a watchdog JSON file."""
    from scripts.runpod_artifacts import _load_json  # noqa: E402
    data = _load_json(path)
    if not isinstance(data, dict):
        return None
    return _extract_peak_vram_from_watchdog_data(data)


def _extract_peak_vram_from_watchdog_data(data: dict[str, Any]) -> int | None:
    """Extract peak VRAM from watchdog report dict."""
    vram_samples = data.get("vram_samples", [])
    if not isinstance(vram_samples, list):
        return None
    peak = 0
    for sample in vram_samples:
        if not isinstance(sample, dict):
            continue
        total = sample.get("vram_total_bytes")
        free = sample.get("vram_free_bytes")
        if isinstance(total, (int, float)) and isinstance(free, (int, float)) and total > 0:
            used = int(total - free)
            if used > peak:
                peak = used
    return peak if peak > 0 else None


def _post_process_results(artifact_root: Path, output_root: Path) -> int:
    """After pod execution, parse downloaded artifacts into results.json.

    Enriches with:
    - Output sha256 list (reusing runpod_artifacts.py sha256 logic)
    - Peak VRAM from watchdog logs (correctness-2)
    - Previous-run sha diff flags
    """
    # Try to load remote results
    remote_results_path = artifact_root / "out" / "e2e" / "results.json"
    try:
        decoded = json.loads(remote_results_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return _write_diagnostic_aggregate(
            output_root,
            f"could not read remote results at {remote_results_path}: {exc}",
        )
    except json.JSONDecodeError as exc:
        return _write_diagnostic_aggregate(
            output_root,
            f"remote results at {remote_results_path} are not valid JSON: {exc.msg}",
        )

    if not isinstance(decoded, list):
        return _write_diagnostic_aggregate(
            output_root,
            f"remote results at {remote_results_path} must be a JSON list, got {type(decoded).__name__}",
        )
    if not decoded:
        return _write_diagnostic_aggregate(
            output_root,
            f"remote results at {remote_results_path} are empty",
        )
    for index, entry in enumerate(decoded):
        if not isinstance(entry, dict):
            return _write_diagnostic_aggregate(
                output_root,
                f"remote results row {index} at {remote_results_path} must be an object, got {type(entry).__name__}",
            )
    results: list[dict[str, Any]] = decoded

    # Enrich with peak VRAM from watchdogs
    peak_vram_map = _parse_peak_vram_from_watchdogs(artifact_root)
    for entry in results:
        tid = entry.get("template_id")
        if isinstance(tid, str) and tid in peak_vram_map:
            peak = peak_vram_map[tid]
            if peak is not None and entry.get("peak_vram_bytes") is None:
                entry["peak_vram_bytes"] = peak

    # Compute output sha256s for the local artifact root
    from scripts.runpod_artifacts import _sha256  # noqa: E402
    e2e_output_dir = artifact_root / "out" / "e2e" / "output"
    if e2e_output_dir.exists():
        for entry in results:
            tid = entry.get("template_id")
            if not isinstance(tid, str):
                continue
            template_output = e2e_output_dir / tid
            if not template_output.exists():
                continue
            sha_list = []
            for fpath in sorted(template_output.rglob("*")):
                if fpath.is_file():
                    digest = _sha256(fpath)
                    if digest:
                        sha_list.append(
                            {"path": str(fpath.relative_to(template_output)), "sha256": digest}
                        )
            if sha_list and not entry.get("output_sha256s"):
                entry["output_sha256s"] = sha_list

    # Previous-run diff: sha changes are flags, not failures
    prev_results = _load_previous_results(output_root)
    sha_changes = _diff_sha_changes(results, prev_results)
    if sha_changes:
        for entry in results:
            tid = entry.get("template_id")
            if isinstance(tid, str) and tid in sha_changes:
                entry["sha_changes_from_previous"] = sha_changes[tid]

    # Write enriched results
    output_results_path = output_root / "results.json"
    output_results_path.parent.mkdir(parents=True, exist_ok=True)
    output_results_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Results written to {output_results_path}", flush=True)

    # Print summary
    ok_count = sum(1 for r in results if r.get("status") == "ok")
    total = len(results)
    print(f"E2E summary: {ok_count}/{total} ok", flush=True)
    skipped_count = sum(1 for r in results if r.get("status") == "skipped")
    failed_rows = [
        r for r in results if r.get("status") not in _NON_FAILURE_ROW_STATUSES
    ]
    if skipped_count:
        print(f"E2E summary: {skipped_count} explicitly skipped", flush=True)
    if failed_rows:
        print(f"E2E failures: {len(failed_rows)} row(s)", flush=True)
        for entry in failed_rows:
            print(
                f"  FAILED: {entry.get('template_id', '<missing template id>')} "
                f"[{entry.get('status', '<missing status>')}]",
                flush=True,
            )
    if sha_changes:
        changed_ids = sorted(sha_changes.keys())
        print(f"Sha changes detected (flags, not failures): {', '.join(changed_ids)}", flush=True)
    return 1 if failed_rows else 0


def _write_diagnostic_aggregate(output_root: Path, reason: str) -> int:
    """Publish a schema-compatible failure row when results are unusable."""
    diagnostic = [
        {
            "template_id": "<matrix>",
            "status": "results_invalid",
            "failure": reason,
            "output_sha256s": [],
            "aggregate": {"status": "invalid", "reason": reason},
            "diagnostic": {"kind": "aggregate", "reason": reason},
        }
    ]
    output_results_path = output_root / "results.json"
    output_results_path.parent.mkdir(parents=True, exist_ok=True)
    output_results_path.write_text(json.dumps(diagnostic, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Results written to {output_results_path}", flush=True)
    print("E2E summary: 0/1 ok", flush=True)
    print("E2E failures: 1 row(s)", flush=True)
    print(f"  FAILED: <matrix> [results_invalid] {reason}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
