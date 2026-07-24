"""L5 coverage guard — regression gate for the node-schema resolution ladder.

This is plan-verification layer L5 (see ``docs/plans/all-installable-nodes.md``).
It runs a SMALL slice of the coverage sweep over the curated node-pack catalog
and asserts an exact-coverage floor. If the resolution ladder regresses (a
rung stops resolving, a provider is dropped from the shared authoring chain),
coverage drops below the floor and this test fails.

It is:

* ``@pytest.mark.live`` — it hits the network for on-demand git clones of
  public repos, so it is deselected in normal CI (needs ``--run-live``).
* Skipped unless ``VIBECOMFY_RUN_COVERAGE_SWEEP=1`` — an explicit opt-in so
  ``--run-live`` alone (which runs other live tests) does not silently pull
  dozens of repos and add minutes to a run.
* Offline-safe otherwise — no live ComfyUI server is needed; the ladder is
  corpus -> static AST -> on-demand clone+AST -> on-demand stub-import.

The sweep logic lives in ``scripts/node_schema_coverage.py`` (imported here, not
duplicated) so the test and the CLI report stay in lockstep.
"""
from __future__ import annotations

import os

import pytest

# Imported lazily inside the test so collection never depends on the scripts dir.
_EXACT_COVERAGE_FLOOR_DEFAULT = 70.0


def _floor() -> float:
    raw = os.environ.get("VIBECOMFY_COVERAGE_FLOOR")
    if raw is None:
        return _EXACT_COVERAGE_FLOOR_DEFAULT
    try:
        return float(raw)
    except ValueError:
        return _EXACT_COVERAGE_FLOOR_DEFAULT


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("VIBECOMFY_RUN_COVERAGE_SWEEP") != "1",
    reason=(
        "needs VIBECOMFY_RUN_COVERAGE_SWEEP=1 (clones public GitHub repos via "
        "the on-demand rungs; pair with --run-live)"
    ),
)
def test_l5_exact_coverage_floor() -> None:
    """L5 guard: the resolution ladder resolves >= floor% of a small pack slice.

    Runs the sweep over a bounded slice (``--limit 8``) of the known-node-pack
    catalog through the shared authoring provider with the on-demand rungs
    active. The default floor is 70%; override with
    ``VIBECOMFY_COVERAGE_FLOOR=<pct>``.

    A drop below the floor means the ladder regressed — a rung stopped
    resolving or a provider fell out of the shared authoring chain. Investigate
    before re-pinning the floor downward.
    """
    from scripts.node_schema_coverage import run_sweep

    pack_results = run_sweep(limit=8)
    assert pack_results, "sweep returned no packs (catalog empty or filter bug)"

    total_classes = sum(r.class_count for r in pack_results)
    assert total_classes > 0, "swept packs declared zero classes total"

    total_exact = sum(r.exact for r in pack_results)
    exact_pct = round(100.0 * total_exact / total_classes, 2)

    floor = _floor()
    assert exact_pct >= floor, (
        f"L5 exact coverage {exact_pct}% ({total_exact}/{total_classes} classes "
        f"across {len(pack_results)} packs) is below the {floor}% floor. "
        f"The resolution ladder regressed — see the sweep report for the failing "
        f"classes (run: VIBECOMFY_ON_DEMAND_SCHEMAS=1 "
        f"python scripts/node_schema_coverage.py --limit 8)."
    )
