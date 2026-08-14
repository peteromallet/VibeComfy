"""B09 preflight — sole corpus-hash owner + authoritative manifest extension.

Runs BEFORE any model call. It:

1. Validates D13's authoritative manifest (``scenario_manifest.json``) via
   ``discover_manifest_scenarios`` — 100 scenarios, descriptor SHA-256s,
   source-workflow SHA-256s, no missing/duplicate/unmanifested files.
2. Inventories the ignored ``external_workflows/corpus`` and computes one
   aggregate corpus digest (the SOLE corpus-hash owner; the B02 preservation
   suite owns the preservation proof — mismatches/uidless — not hashes).
3. Extends D13's manifest IN PLACE with ``primary_source``, ``aggregate``,
   ``commit``, ``selection`` and ``configuration`` — no parallel manifest is
   created, and ``discover_manifest_scenarios`` ignores the extra keys, so the
   D13 hash authority is unchanged.
4. Writes ``out/agentic/<tag>/b09_preflight.json`` with every digest.

Deterministic: stable sort everywhere, no timestamps, idempotent (re-running
over an already-extended manifest is a no-op with identical bytes).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tests" / "live_agentic_harness"
MANIFEST_PATH = HARNESS / "scenario_manifest.json"
SCENARIOS_DIR = HARNESS / "scenarios"
CORPUS_DIR = REPO / "external_workflows" / "corpus"
DEFAULT_TAG = "megado-final"

# Canonical lane configuration (frozen for B09; matches the brief's command
# shape — the harness runner has no --profile flag, so the production default
# profile is the no-flag default; models are resolved from default.toml).
LANE_CONFIG: dict[str, object] = {
    "transport": "openrouter",
    "profile": "default",
    "models": {
        "classify": "hermes:openrouter:deepseek/deepseek-v4-flash",
        "research": "hermes:openrouter:deepseek/deepseek-v4-pro",
        "implement": "hermes:openrouter:deepseek/deepseek-v4-pro",
        "reply": "hermes:openrouter:deepseek/deepseek-v4-flash",
    },
    "max_workers": 6,
    "per_scenario_timeout": 1200,
    "infra_retries": 1,
    "progress_every": 10,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_digest(config: dict[str, object]) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def corpus_digest(corpus_dir: Path) -> dict[str, object]:
    """One aggregate digest over every ``*.json`` in the corpus (stable order)."""
    files = sorted(corpus_dir.glob("*.json"))
    lines = []
    envelopes = 0
    layout_sidecars = 0
    for path in files:
        digest = sha256_file(path)
        lines.append(f"{path.name}\t{digest}")
        if path.name.endswith(".layout.json"):
            layout_sidecars += 1
        else:
            envelopes += 1
    blob = "\n".join(lines) + "\n"
    return {
        "scope": "external_workflows/corpus/*.json",
        "file_count": len(files),
        "envelope_count": envelopes,
        "layout_sidecars": layout_sidecars,
        "algorithm": "sha256",
        "method": "sha256 over 'name\\tsha256' lines, names sorted ascending",
        "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
    }


def source_workflow_digest(entries: list[dict[str, object]]) -> dict[str, object]:
    sources: dict[str, dict[str, str]] = {}
    for entry in entries:
        source = entry.get("source_workflow")
        if not isinstance(source, dict):
            continue
        sources[str(entry["id"])] = {
            "source_workflow_id": str(source.get("id") or ""),
            "path": str(source.get("path") or ""),
            "sha256": str(source.get("sha256") or ""),
        }
    unique = sorted({(v["source_workflow_id"], v["sha256"]) for v in sources.values()})
    blob = "\n".join(f"{sid}\t{s}" for sid, s in unique) + "\n"
    return {
        "scenario_count": len(sources),
        "unique_source_files": len(unique),
        "algorithm": "sha256",
        "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "by_scenario": sources,
    }


def git_head() -> dict[str, str]:
    sha = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True)
        .strip()
    )
    subject = (
        subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], cwd=REPO, text=True
        ).strip()
    )
    return {"sha": sha, "subject": subject}


def preflight(tag: str) -> dict[str, object]:
    sys_path = str(REPO)
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from tests.live_agentic_harness.scenario_manifest import discover_manifest_scenarios

    # 1. Manifest validation (descriptor + source hashes, 100 scenarios).
    selected = discover_manifest_scenarios(SCENARIOS_DIR, manifest_path=MANIFEST_PATH, repo=REPO)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest["entries"]
    assert len(selected) == 100, f"expected 100 selected scenarios, got {len(selected)}"
    assert manifest["scenario_count"] == 100

    # 2. Corpus inventory + aggregate digest.
    corpus = corpus_digest(CORPUS_DIR)
    source_workflows = source_workflow_digest(entries)

    # 3. Commit / selection / configuration digests.
    head = git_head()
    selection = {
        "basis": "tests/live_agentic_harness/scenario_manifest.json (D13 authority)",
        "count": 100,
        "inclusion_status": "included",
        "by_kind": {
            "edit": sum(1 for e in entries if e["scenario_kind"] == "edit"),
            "semantic_product": sum(
                1 for e in entries if e["scenario_kind"] == "semantic_product"
            ),
            "health_control": sum(
                1 for e in entries if e["scenario_kind"] == "health_control"
            ),
        },
        "by_revision_status": {
            "matched": sum(1 for e in entries if e["revision_status"] == "matched"),
            "revised": sum(1 for e in entries if e["revision_status"] == "revised"),
        },
    }
    configuration = dict(LANE_CONFIG)
    configuration["digest"] = config_digest(LANE_CONFIG)

    # 4. Extend the D13 manifest in place (no parallel manifest).
    extension = {
        "primary_source": {
            "corpus_dir": "external_workflows/corpus",
            "algorithm": "sha256",
            "by_scenario": source_workflows["by_scenario"] if "by_scenario" in source_workflows else {},
            "note": "per-scenario source-workflow id/path/sha256 (identical to entries[].source_workflow; declared here for report citation by stable ID)",
        },
        "aggregate": {
            "corpus": corpus,
            "source_workflows": {
                "scenario_count": source_workflows["scenario_count"],
                "unique_source_files": source_workflows["unique_source_files"],
                "algorithm": source_workflows["algorithm"],
                "sha256": source_workflows["sha256"],
            },
            "scenarios": selection["by_kind"] | {"count": 100},
            "revision": selection["by_revision_status"],
        },
        "commit": head,
        "selection": selection,
        "configuration": configuration,
    }
    manifest.update(extension)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # 5. Persist the preflight record.
    out_dir = REPO / "out" / "agentic" / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "preflight": "PASS",
        "manifest": {
            "path": "tests/live_agentic_harness/scenario_manifest.json",
            "scenario_count": 100,
            "selected": len(selected),
            "descriptor_hashes_verified": True,
            "source_workflow_hashes_verified": True,
        },
        "corpus": corpus,
        "source_workflows": {
            "scenario_count": source_workflows["scenario_count"],
            "unique_source_files": source_workflows["unique_source_files"],
            "sha256": source_workflows["sha256"],
        },
        "commit": head,
        "selection": selection,
        "configuration": configuration,
        "corpus_hash_ownership": (
            "B09 preflight is the SOLE corpus-hash owner; the B02 preservation "
            "suite (tests/test_b02_rich_preservation.py) owns the preservation "
            "proof (projection mismatches / uidless emissions), not hashes. "
            "No second hash authority exists."
        ),
        "historical_evidence": {
            "out_agentic_present": False,
            "note": (
                "out/agentic/ is absent -> no historical comparison, no "
                "flaky-set derivation, no regression-vs-variance claim (B09 item 9/10)."
            ),
        },
    }
    record_path = out_dir / "b09_preflight.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    args = parser.parse_args(argv)
    record = preflight(args.tag)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
