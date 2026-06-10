from __future__ import annotations

import argparse
import json
import sys

from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.porting.simulate import simulate_rule
from vibecomfy.schema import get_schema_provider

from ._shared import READY_ROOT


def _cmd_port_simulate(args: argparse.Namespace) -> int:
    """Sandbox simulation of an experimental emitter rule."""
    rule_spec: str = args.rule
    all_mode = getattr(args, "all", False)
    json_mode = getattr(args, "json", False)

    schema_provider = get_schema_provider("auto")

    # Resolve template IDs: without --all, use None (regeneratable in simulate_rule);
    # with --all, explicitly gather all template IDs from the corpus.
    template_ids = None
    if all_mode:
        snapshot = build_corpus_snapshot(READY_ROOT)
        template_ids = [t["id"] for t in snapshot.templates_list]

    result = simulate_rule(
        rule_spec,
        template_ids=template_ids,
        schema_provider=schema_provider,
    )

    if result.error:
        print(f"Simulation error: {result.error}", file=sys.stderr)
        return 1

    if json_mode:
        print(json.dumps(result.to_json(), indent=2, sort_keys=True))
        return 0

    print(f"\nCorpus simulation: {rule_spec}")
    print(f"  templates affected: {result.templates_affected}")
    if result.templates_total > 0:
        pct = abs(result.loc_delta_total) / max(1, sum(
            pt.get("original_loc", 0) for pt in result.per_template
        )) * 100
        print(f"  LOC delta: {result.loc_delta_total:+d} lines total ({pct:+.1f}% corpus)")
    print(f"  canonical parity: {result.parity_preserved}/{result.parity_preserved + result.parity_broken} preserved {'✅' if result.parity_broken == 0 else '❌'}")
    print(f"  no broken outputs" if result.parity_broken == 0 else f"  {result.parity_broken} broken outputs")

    # Per-template top 5
    affected = [pt for pt in result.per_template if pt.get("changed")]
    if affected:
        print("\nPer-template (top 5):")
        for pt in sorted(affected, key=lambda x: x["loc_delta"])[:5]:
            print(f"  {pt['template_id']}: {pt['original_loc']} → {pt['emitted_loc']} ({pt['loc_delta']:+d})")

    if result.sample_diff:
        print(f"\nSample diff ({affected[0]['template_id'] if affected else 'N/A'}):")
        print(result.sample_diff[:2000])

    return 0
