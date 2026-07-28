"""Run a single additive campaign case by index — for parallel execution.

Usage: python scripts/run_one_additive.py <index> <output_base>

Each invocation is fully isolated (its own process), so N cases can run
concurrently without shared-state races in the agent-edit pipeline. The result
dict is written to <output_base>/results/case<index>.json for aggregation.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make the repo root importable regardless of how the script is invoked.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vibecomfy.demo_factory.run_campaign import ADDITIVE_WORKFLOWS, run_additive_case


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: run_one_additive.py <index> <output_base>", file=sys.stderr)
        return 2
    idx = int(sys.argv[1])
    out = Path(sys.argv[2])
    if idx < 0 or idx >= len(ADDITIVE_WORKFLOWS):
        print(f"index {idx} out of range (0..{len(ADDITIVE_WORKFLOWS) - 1})", file=sys.stderr)
        return 2

    workflow_id, feature_type = ADDITIVE_WORKFLOWS[idx]
    result = run_additive_case(workflow_id, feature_type, idx, out)

    results_dir = out / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"case{idx:02d}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(f"[{idx:02d}] {workflow_id} ({feature_type}) -> {result.get('verdict')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
