from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from scripts.runpod_runner import DEFAULT_UPLOAD_EXCLUDES, REMOTE_ROOT, run_pod_detached

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = Path("out") / "reigh_route_validation"
DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_POLL_INTERVAL_SECONDS = 30
DEFAULT_ENV_FILES = (
    ROOT / ".env",
    ROOT.parent / "reigh-worker" / ".env",
)


@dataclass(frozen=True)
class ReighRouteTemplate:
    route_key: str
    task_type: str
    support_state: str
    selected_template_id: str
    fixture_path: Path


ROUTE_TEMPLATES: dict[str, ReighRouteTemplate] = {
    "z_image_turbo": ReighRouteTemplate(
        route_key="z_image_turbo",
        task_type="z_image_turbo",
        support_state="vibecomfy_supported",
        selected_template_id="image/z_image",
        fixture_path=ROOT / "fixtures" / "reigh_routes" / "z_image_turbo.json",
    ),
}


def _load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def load_default_env_files(paths: Sequence[Path] | None = None) -> None:
    for path in paths if paths is not None else DEFAULT_ENV_FILES:
        _load_env_file(path)


def resolve_route_template(
    *,
    route_key: str | None = None,
    task_type: str | None = None,
    selected_template_id: str | None = None,
    fixture_path: Path | None = None,
) -> ReighRouteTemplate:
    if route_key:
        base = ROUTE_TEMPLATES.get(route_key)
    elif task_type:
        base = next((spec for spec in ROUTE_TEMPLATES.values() if spec.task_type == task_type), None)
    else:
        base = ROUTE_TEMPLATES["z_image_turbo"]

    if base is None:
        label = route_key or task_type or "<default>"
        if not selected_template_id or not fixture_path:
            raise ValueError(
                f"Unknown Reigh route/task {label!r}; pass both --selected-template-id and --input-fixture to validate it."
            )
        fixture = _load_fixture(fixture_path)
        return ReighRouteTemplate(
            route_key=route_key or str(fixture.get("route_key") or task_type),
            task_type=task_type or str(fixture.get("task_type") or route_key),
            support_state=str(fixture.get("support_state") or "vibecomfy_unsupported"),
            selected_template_id=selected_template_id,
            fixture_path=fixture_path,
        )

    if selected_template_id is None and fixture_path is None:
        return base

    return ReighRouteTemplate(
        route_key=base.route_key,
        task_type=base.task_type,
        support_state=base.support_state,
        selected_template_id=selected_template_id or base.selected_template_id,
        fixture_path=fixture_path or base.fixture_path,
    )


def build_manifest(spec: ReighRouteTemplate, fixture: dict, out_dir: Path) -> dict:
    return {
        "route_key": spec.route_key,
        "task_type": spec.task_type,
        "support_state": spec.support_state,
        "selected_template_id": spec.selected_template_id,
        "input_fixture": str(spec.fixture_path),
        "output_dir": str(out_dir),
        "runpod": {
            "mode": "detached",
            "artifact_manifest": "downloaded by scripts.runpod_runner into its artifact root",
        },
        "fixture_params": {
            "prompt": fixture.get("params", {}).get("prompt"),
            "resolution": fixture.get("params", {}).get("resolution"),
            "seed": fixture.get("params", {}).get("seed"),
            "steps": fixture.get("params", {}).get("steps") or fixture.get("params", {}).get("num_inference_steps"),
        },
    }


def build_remote_script(spec: ReighRouteTemplate, fixture: dict, out_dir: Path) -> str:
    remote_out_dir = f"{REMOTE_ROOT}/{out_dir.as_posix()}"
    prompt = str(fixture.get("params", {}).get("prompt") or "")
    seed = fixture.get("params", {}).get("seed")
    steps = fixture.get("params", {}).get("steps") or fixture.get("params", {}).get("num_inference_steps")
    cli_parts = [
        "python3",
        "-m",
        "vibecomfy.cli",
        "run",
        spec.selected_template_id,
        "--ready",
        "--runtime",
        "embedded",
        "--backend",
        "graphbuilder",
    ]
    if prompt:
        cli_parts += ["--prompt", prompt]
    if seed is not None:
        cli_parts += ["--seed", str(seed)]
    if steps is not None:
        cli_parts += ["--steps", str(steps)]
    run_command = " ".join(shlex.quote(part) for part in cli_parts)

    manifest = build_manifest(spec, fixture, out_dir)
    manifest_json = json.dumps(manifest, indent=2, sort_keys=True)
    manifest_script = shlex.quote(manifest_json)

    return f"""set -euo pipefail
cd {shlex.quote(REMOTE_ROOT)}
mkdir -p {shlex.quote(remote_out_dir)} output
cat > {shlex.quote(remote_out_dir)}/route_manifest.json <<'JSON'
{manifest_json}
JSON
printf '%s\\n' {manifest_script} > {shlex.quote(remote_out_dir)}/route_manifest.compact.json
python3 -m pip install -e '.[dev]'
python3 -m pip install 'comfyui@git+https://github.com/peteromallet/ComfyUI.git@fix/latentupscale-model-mmap-residency' 'comfy-script[default]'
python3 -m vibecomfy.cli runtime doctor
before=$(find output -type f 2>/dev/null | sort || true)
start=$(date +%s)
{run_command} 2>&1 | tee {shlex.quote(remote_out_dir)}/run.log
seconds=$(( $(date +%s) - start ))
after=$(find output -type f 2>/dev/null | sort || true)
comm -13 <(printf '%s\\n' "$before") <(printf '%s\\n' "$after") > {shlex.quote(remote_out_dir)}/new_outputs.txt || true
media_files=$(awk '/\\.(png|webp|mp4|webm|mp3|glb)$/ {{c++}} END {{print c+0}}' {shlex.quote(remote_out_dir)}/new_outputs.txt)
bytes=$(find output -type f \\( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \\) -exec stat -c '%s' {{}} + 2>/dev/null | awk '{{s+=$1}} END {{print s+0}}')
cat > {shlex.quote(remote_out_dir)}/result.json <<JSON
{{"route_key":"{spec.route_key}","task_type":"{spec.task_type}","selected_template_id":"{spec.selected_template_id}","status":"ok","seconds":$seconds,"media_files":$media_files,"bytes":$bytes,"run_log":"{out_dir.as_posix()}/run.log"}}
JSON
cat {shlex.quote(remote_out_dir)}/result.json
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a Reigh route's selected VibeComfy ready template on RunPod.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--route-key")
    selection.add_argument("--task-type")
    parser.add_argument("--selected-template-id", help="Override the selected ready template ID.")
    parser.add_argument("--input-fixture", type=Path, help="Override the production-shaped Reigh route fixture.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR / "z_image_turbo")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=int(os.getenv("VIBECOMFY_RUNPOD_POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL_SECONDS))),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _dry_run_payload(spec: ReighRouteTemplate, fixture: dict, out_dir: Path, remote_script: str) -> dict:
    return {
        "dry_run": True,
        "route": asdict(spec) | {"fixture_path": str(spec.fixture_path)},
        "manifest": build_manifest(spec, fixture, out_dir),
        "remote_script_preview": remote_script,
    }


async def async_main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_default_env_files()
    if not args.route_key and not args.task_type:
        args.route_key = "z_image_turbo"
    try:
        spec = resolve_route_template(
            route_key=args.route_key,
            task_type=args.task_type,
            selected_template_id=args.selected_template_id,
            fixture_path=args.input_fixture,
        )
        fixture = _load_fixture(spec.fixture_path)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2

    out_dir = args.out_dir
    remote_script = build_remote_script(spec, fixture, out_dir)
    if args.dry_run:
        print(json.dumps(_dry_run_payload(spec, fixture, out_dir, remote_script), indent=2, sort_keys=True))
        return 0

    if not os.getenv("RUNPOD_API_KEY"):
        print(json.dumps({"error": "RUNPOD_API_KEY is required unless --dry-run is used."}, sort_keys=True))
        return 2

    return await run_pod_detached(
        remote_script,
        name_prefix=f"vibecomfy-reigh-{spec.route_key.replace('_', '-')}",
        exclude=set(DEFAULT_UPLOAD_EXCLUDES),
        upload_mode="tarball",
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
