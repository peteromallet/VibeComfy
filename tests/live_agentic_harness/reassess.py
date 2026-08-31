"""Re-run live-harness judges against immutable completed leg artifacts.

This command performs no product-agent execution. It reuses each leg's frozen
response/UI/authority evidence, runs the normal guard/assessor with an explicit
judge provider, and publishes a separate auditable reassessment dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Mapping

from .compare_pipeline_modes import (
    DEFAULT_COMPARISON_MANIFEST,
    PIPELINE_MODES,
    REPO,
    _authoritative_entries,
    validate_only,
)
from .judge_config import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_ROUTE,
    JudgeReadinessError,
    require_judge_readiness,
    resolve_judge_config,
)


class ReassessmentError(RuntimeError):
    """Raised when a source corpus cannot be reassessed without mutation."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReassessmentError(f"unreadable JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReassessmentError(f"JSON artifact is not an object: {path}")
    return payload


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_sha256(root: Path) -> str:
    """Digest relative paths and bytes for every regular source artifact."""
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _source_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _collect_legs(
    source_output: Path,
    manifest_path: Path,
    scenario_ids: set[str],
) -> list[dict[str, Any]]:
    validate_only(manifest_path)
    entries = _authoritative_entries()
    locked = _load_json(manifest_path)
    allowed_ids = {str(item["id"]) for item in locked.get("entries", [])}
    if scenario_ids - allowed_ids:
        raise ReassessmentError(
            "requested scenario ids are outside the locked manifest: "
            + ", ".join(sorted(scenario_ids - allowed_ids))
        )

    comparison_path = source_output / "comparison.json"
    comparison = _load_json(comparison_path)
    rows = comparison.get("scenarios")
    if not isinstance(rows, list) or not rows:
        raise ReassessmentError(f"comparison has no final scenario rows: {comparison_path}")
    legs: list[dict[str, Any]] = []
    source_root = source_output.resolve()
    selected: list[tuple[str, str, Mapping[str, Any]]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ReassessmentError("comparison scenario row is not an object")
        scenario_id = str(row.get("scenario_id") or "")
        if scenario_id not in allowed_ids or (scenario_ids and scenario_id not in scenario_ids):
            continue
        if all(isinstance(row.get(mode), Mapping) for mode in PIPELINE_MODES):
            selected.extend((scenario_id, mode, row[mode]) for mode in PIPELINE_MODES)
        elif row.get("mode") in PIPELINE_MODES and isinstance(row.get("leg"), Mapping):
            selected.append((scenario_id, str(row["mode"]), row["leg"]))
        else:
            raise ReassessmentError(f"comparison row has no final leg payload: {scenario_id}")

    for scenario_id, mode, final_leg in selected:
        output_dir = Path(str(final_leg.get("output_dir") or "")).resolve()
        try:
            relative = output_dir.relative_to(source_root)
        except ValueError as exc:
            raise ReassessmentError(
                f"leg output escapes source corpus: {output_dir}"
            ) from exc
        path_mode = relative.parts[0] if relative.parts else ""
        if path_mode != mode:
            raise ReassessmentError(
                f"leg output mode {path_mode!r} does not match comparison mode {mode!r}: "
                f"{output_dir}"
            )
        descriptor_entry = entries.get(scenario_id)
        if not isinstance(descriptor_entry, Mapping):
            raise ReassessmentError(f"no authoritative descriptor for {scenario_id}")
        descriptor_path = (REPO / str(descriptor_entry["path"])).resolve()
        legs.append(
            {
                "index": len(legs),
                "scenario_id": scenario_id,
                "mode": mode,
                "output_dir": str(output_dir),
                "descriptor_path": str(descriptor_path),
                "source_tree_sha256": _tree_sha256(output_dir),
                "source_commit": str(
                    (_load_json(output_dir / "artifact_lineage.json").get("binding") or {}).get(
                        "source_commit", ""
                    )
                )
                if (output_dir / "artifact_lineage.json").is_file()
                else "",
            }
        )
    if not legs:
        raise ReassessmentError("no source legs matched the requested scenarios")
    return legs


def _reassess_leg(
    leg: Mapping[str, Any],
    *,
    output_base: str,
    judge_route: str,
    judge_model: str,
) -> dict[str, Any]:
    from .guard import guard_output_dir

    scenario = _load_json(Path(str(leg["descriptor_path"])))
    assessment_path = (
        Path(output_base)
        / "assessments"
        / str(leg["mode"])
        / str(leg["scenario_id"])
        / "assessment.json"
    )
    record = dict(leg)
    try:
        guard = guard_output_dir(
            Path(str(leg["output_dir"])),
            scenario=scenario,
            judge_route=judge_route,
            judge_model=judge_model,
            assessment_path=assessment_path,
        )
        assessment = guard.get("assessment", {})
        if assessment.get("judge_config") != {
            "route": judge_route,
            "model": judge_model,
        }:
            raise ReassessmentError(
                f"assessment judge config mismatch for {leg['scenario_id']} {leg['mode']}"
            )
        for judge in assessment.get("judge_results", []):
            metadata = judge.get("metadata") if isinstance(judge, Mapping) else None
            if not isinstance(metadata, Mapping) or (
                metadata.get("requested_route") != judge_route
                or metadata.get("requested_model") != judge_model
            ):
                raise ReassessmentError(
                    "judge receipt requested config mismatch for "
                    f"{leg['scenario_id']} {leg['mode']}: {metadata}"
                )
            actual_route = metadata.get("route")
            actual_model = metadata.get("model")
            if actual_route is not None and actual_route != judge_route:
                raise ReassessmentError(f"judge actual route mismatch: {metadata}")
            if actual_model is not None and actual_model != judge_model:
                raise ReassessmentError(f"judge actual model mismatch: {metadata}")
        record.update(
            {
                "assessment_path": str(assessment_path),
                "verdict": guard.get("verdict"),
                "score_class": guard.get("score_class"),
                "live_agentic_success": guard.get("live_agentic_success") is True,
                "judge_results": assessment.get("judge_results", []),
                "guard": guard,
                "reassessment_error": None,
            }
        )
    except Exception as exc:  # noqa: BLE001 - one broken leg remains visible
        record.update(
            {
                "assessment_path": str(assessment_path),
                "verdict": "undetermined",
                "score_class": "reassessment_error",
                "live_agentic_success": False,
                "judge_results": [],
                "guard": None,
                "reassessment_error": f"{type(exc).__name__}: {exc}",
            }
        )
    result_path = (
        Path(output_base)
        / "legs"
        / f"{int(leg['index']):04d}_{leg['scenario_id']}_{leg['mode']}.json"
    )
    _write_json_atomic(result_path, record)
    record["reassessment_result_path"] = str(result_path)
    return record


def run_reassessment(
    source_output: Path,
    *,
    output_base: Path,
    manifest_path: Path = DEFAULT_COMPARISON_MANIFEST,
    judge_route: str = DEFAULT_JUDGE_ROUTE,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    concurrency: int = 1,
    scenario_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Reassess frozen legs and publish a separate, immutability-checked corpus."""
    if isinstance(concurrency, bool) or concurrency < 1:
        raise ReassessmentError("concurrency must be a positive integer")
    source_output = source_output.resolve()
    output_base = output_base.resolve()
    if (
        output_base == source_output
        or source_output in output_base.parents
        or output_base in source_output.parents
    ):
        raise ReassessmentError("reassessment output and source corpus must not contain each other")
    if output_base.exists() and any(output_base.iterdir()):
        raise ReassessmentError("reassessment output must be a new or empty directory")
    config = resolve_judge_config(judge_route, judge_model)
    try:
        readiness = require_judge_readiness(config)
    except JudgeReadinessError as exc:
        raise ReassessmentError(str(exc)) from exc
    legs = _collect_legs(source_output, manifest_path.resolve(), scenario_ids or set())

    output_base.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=min(concurrency, len(legs))) as executor:
        futures = [
            executor.submit(
                _reassess_leg,
                leg,
                output_base=str(output_base),
                judge_route=config.route,
                judge_model=config.model,
            )
            for leg in legs
        ]
        results = [future.result() for future in futures]

    mutated: list[str] = []
    for leg in legs:
        current = _tree_sha256(Path(str(leg["output_dir"])))
        if current != leg["source_tree_sha256"]:
            mutated.append(str(leg["output_dir"]))
    if mutated:
        raise ReassessmentError(
            "source assessment artifacts changed during reassessment: "
            + ", ".join(mutated)
        )

    counts: dict[str, dict[str, int]] = {
        mode: {"pass": 0, "fail": 0, "undetermined": 0} for mode in PIPELINE_MODES
    }
    judge_calls = 0
    for result in results:
        verdict = str(result.get("verdict") or "fail")
        if verdict not in counts[str(result["mode"])]:
            verdict = "fail"
        counts[str(result["mode"])][verdict] += 1
        judge_calls += len(result.get("judge_results") or [])
    aggregate = {
        "leg_count": len(results),
        "pass": sum(row["pass"] for row in counts.values()),
        "fail": sum(row["fail"] for row in counts.values()),
        "undetermined": sum(row["undetermined"] for row in counts.values()),
        "by_mode": counts,
        "judge_calls": judge_calls,
    }
    payload = {
        "schema_version": 1,
        "source_output": str(source_output),
        "source_run_commits": sorted(
            {str(leg.get("source_commit")) for leg in legs if leg.get("source_commit")}
        ),
        "reassessment_code_commit": _source_commit(),
        "source_comparison": str(source_output / "comparison.json"),
        "source_comparison_sha256": _sha256(source_output / "comparison.json"),
        "comparison_manifest": str(manifest_path.resolve()),
        "comparison_manifest_sha256": _sha256(manifest_path.resolve()),
        "judge_config": config.as_dict(),
        "judge_readiness": readiness,
        "source_assessments_immutable": True,
        "aggregate": aggregate,
        "legs": results,
    }
    _write_json_atomic(output_base / "reassessment.json", payload)
    return payload


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.live_agentic_harness.reassess"
    )
    parser.add_argument("--source-output", type=Path, required=True)
    parser.add_argument("--output-base", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_COMPARISON_MANIFEST)
    parser.add_argument("--judge-route", default=DEFAULT_JUDGE_ROUTE)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--concurrency", type=_positive_int, default=1)
    parser.add_argument("--scenario-id", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = run_reassessment(
            args.source_output,
            output_base=args.output_base,
            manifest_path=args.manifest,
            judge_route=args.judge_route,
            judge_model=args.judge_model,
            concurrency=args.concurrency,
            scenario_ids=set(args.scenario_id),
        )
    except ReassessmentError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(payload["aggregate"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
