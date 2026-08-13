"""B07-lite deterministic transport probe (native vs OpenRouter).

Precommitted matched configuration (B07-lite task 5):
- Commit: the current HEAD of the oracle-run checkout (recorded at run time).
- Scenario set: the ten IDs below (descriptor SHAs verified + recorded).
- Profile: the default executor profile (``default``) — no all-Flash profile,
  no prompt rewrite.
- Concurrency: max_workers=2, per_scenario_timeout=1800s, infra_retries=1
  (runner defaults otherwise), scenario-level timeouts from the descriptors.

Because historical typed-empty evidence is absent (out/agentic/ and
external_workflows/ historical runs not restored), this is a DETERMINISTIC
PROBE — not an "empty-heavy" experiment.  Every B01 model attempt's OBSERVED
transport must equal the selected transport.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from tests.live_agentic_harness.runner import REPO, run_tag
from tests.live_agentic_harness.scenario_manifest import write_manifest

# ── precommitted scenario IDs (exactly ten) ─────────────────────────────────
PROBE_SCENARIO_IDS = [
    "speed-distillation-research",  # health control
    "live-graph-explanation-smoke",  # health control
    "image-llava-image-captioning-and-keyword-extraction-d38dc8",  # semantic
    "image-image-processing-with-sharpening-film-grain-an-9aa0f1",  # semantic
    "image-dual-checkpoint-xl-image-generation-with-refin-c9df19",  # semantic
    "multi-animatediff-video-generation-with-controlnet-a7e2af",  # semantic
    "3d-generates-a-3d-mesh-from",  # edit
    "3d-3d-model-load-edit-and-export-workflow-d66a66",  # edit
    "audio-acestep-audio-generation-and-processing-workfl-1b1360",  # edit
    "video-video-loading-and-saving-workflow-1c7ad8",  # edit
]

MAX_WORKERS = 2
PER_SCENARIO_TIMEOUT = 1800
INFRA_RETRIES = 1
PROFILE = "default"

SCENARIOS_DIR = REPO / "tests" / "live_agentic_harness" / "scenarios"
PROBE_ROOT = REPO / "out" / "b07-probe"
PROBE_SCENARIOS = PROBE_ROOT / "scenarios"
PROBE_MANIFEST = PROBE_ROOT / "scenario_manifest.json"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def commit_sha() -> str:
    return (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO), capture_output=True, text=True
        )
        .stdout.strip()
        or "unknown"
    )


def main() -> None:
    commit = commit_sha()

    # Verify + hash the precommitted set BEFORE any model call.
    entries = []
    for scenario_id in PROBE_SCENARIO_IDS:
        path = SCENARIOS_DIR / f"{scenario_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"precommitted probe scenario missing: {path}")
        entries.append(
            {"id": scenario_id, "descriptor_sha256": sha256_file(path)}
        )

    matched_digest = sha256_text(
        json.dumps(
            {
                "commit": commit,
                "profile": PROFILE,
                "scenario_ids": [entry["id"] for entry in entries],
                "descriptor_sha256": [entry["descriptor_sha256"] for entry in entries],
                "max_workers": MAX_WORKERS,
                "per_scenario_timeout": PER_SCENARIO_TIMEOUT,
                "infra_retries": INFRA_RETRIES,
            },
            sort_keys=True,
        )
    )

    # Build an isolated ten-scenario lane with its own manifest.
    if PROBE_SCENARIOS.exists():
        shutil.rmtree(PROBE_SCENARIOS)
    PROBE_SCENARIOS.mkdir(parents=True, exist_ok=True)
    for scenario_id, entry in zip(PROBE_SCENARIO_IDS, entries, strict=True):
        shutil.copy2(SCENARIOS_DIR / f"{scenario_id}.json", PROBE_SCENARIOS / f"{scenario_id}.json")
    write_manifest(PROBE_SCENARIOS, manifest_path=PROBE_MANIFEST, repo=REPO)

    report: dict = {
        "probe": "B07-lite deterministic transport probe",
        "commit": commit,
        "profile": PROFILE,
        "scenario_count": len(entries),
        "scenario_ids": [entry["id"] for entry in entries],
        "descriptor_sha256": {entry["id"]: entry["descriptor_sha256"] for entry in entries},
        "matched_config_digest": matched_digest,
        "historical_typed_empty_evidence_restored": False,
        "note": (
            "Historical out/agentic/ run evidence is NOT restored; this is a "
            "deterministic matched probe, not an empty-heavy experiment."
        ),
        "arms": {},
    }

    for transport in ("native", "openrouter"):
        tag = f"b07-probe-{transport}"
        arm_digest = sha256_text(
            json.dumps(
                {
                    "matched_config_digest": matched_digest,
                    "transport": transport,
                },
                sort_keys=True,
            )
        )
        run_summary = run_tag(
            tag,
            scenarios_dir=PROBE_SCENARIOS,
            output_base=PROBE_ROOT,
            max_workers=MAX_WORKERS,
            per_scenario_timeout=PER_SCENARIO_TIMEOUT,
            progress_every=5,
            infra_retries=INFRA_RETRIES,
            manifest_path=PROBE_MANIFEST,
            transport=transport,
        )

        scenario_rows = []
        total_attempts = 0
        typed_empty = 0
        zero_token_empty = 0
        observed_mismatches = []
        for scenario in run_summary["scenarios"]:
            scenario_id = scenario["scenario_id"]
            attempts = scenario.get("attempts") or []
            model_attempts = [
                attempt
                for record in attempts
                for attempt in (record.get("model_attempts") or [])
            ]
            total_attempts += len(model_attempts)
            latency_s = round(sum(float(record.get("elapsed_s") or 0.0) for record in attempts), 1)
            for attempt in model_attempts:
                if attempt.get("failure_type") == "empty_response":
                    typed_empty += 1
                    usage = attempt.get("token_usage") or {}
                    if usage.get("completion_tokens") == 0:
                        zero_token_empty += 1
                observed = attempt.get("transport")
                if observed not in (None, transport):
                    observed_mismatches.append(
                        {
                            "scenario_id": scenario_id,
                            "phase": attempt.get("phase"),
                            "observed_transport": observed,
                            "selected_transport": transport,
                            "endpoint": attempt.get("endpoint"),
                        }
                    )
            scenario_rows.append(
                {
                    "scenario_id": scenario_id,
                    "status": scenario.get("status"),
                    "passed": scenario["guard"].get("live_agentic_success"),
                    "failure_class": scenario.get("failure_class"),
                    "attempt_count": scenario.get("attempt_count"),
                    "latency_s": latency_s,
                    "typed_empty_attempts": sum(
                        1
                        for attempt in model_attempts
                        if attempt.get("failure_type") == "empty_response"
                    ),
                    "model_attempts": len(model_attempts),
                }
            )

        report["arms"][transport] = {
            "arm_config_digest": arm_digest,
            "tag": tag,
            "selected_transport": transport,
            "overall_success": run_summary["overall_success"],
            "passed": run_summary["passed"],
            "failed": run_summary["failed"],
            "infra_failures": run_summary["infra_failures"],
            "total_model_attempts": total_attempts,
            "typed_empty_attempts": typed_empty,
            "typed_empty_rate": (
                round(typed_empty / total_attempts, 4) if total_attempts else None
            ),
            "zero_token_empty_attempts": zero_token_empty,
            "total_latency_s": round(
                sum(float(row["latency_s"]) for row in scenario_rows), 1
            ),
            "observed_transport_mismatches": observed_mismatches,
            "observed_transport_matches_selection": not observed_mismatches,
            "scenarios": scenario_rows,
        }

    report_path = PROBE_ROOT / "probe_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
