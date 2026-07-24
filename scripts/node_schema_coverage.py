#!/usr/bin/env python3
"""L5 coverage sweep — measure what fraction of public ComfyUI nodes the
current resolution ladder can resolve.

This is plan-verification layer L5 (see ``docs/plans/all-installable-nodes.md``).
It grounds the "we can resolve ALL nodes" claim in data by resolving every
class declared by a bounded sample of node packs through the *shared*
authoring provider (:func:`vibecomfy.schema.provider.get_authoring_schema_provider`)
and bucketing each result by provenance.

The resolution ladder (each rung catches what the prior missed):

* shipped corpus (``ObjectInfoIndexSchemaProvider`` — ``source_provider=object_info_index``)
* static AST parse (``SourceSchemaProvider`` — ``source_provider=source_parser``)
* on-demand clone + AST (``on_demand_static``)
* on-demand stub-import runtime (``on_demand_runtime``, gated on ``VIBECOMFY_ON_DEMAND_BOOT=1``)

Each resolved schema carries ``source_provider`` and ``confidence``. We bucket:

* ``exact``      — resolved with >=1 real input slot (any ladder rung)
* ``structural`` — resolved object but degenerate (empty inputs — INPUT_TYPES was dynamic)
* ``fail``       — None (the coverage gap)

The sample is ``vibecomfy.node_packs.get_known_node_packs()`` — the curated
catalog the shipped corpus was built from, so the sweep exercises the whole
ladder meaningfully.

Usage::

    # Full sweep (all known packs, on-demand rungs on):
    VIBECOMFY_ON_DEMAND_SCHEMAS=1 python scripts/node_schema_coverage.py

    # With the runtime boot rung too (executes third-party code):
    VIBECOMFY_ON_DEMAND_SCHEMAS=1 VIBECOMFY_ON_DEMAND_BOOT=1 \\
        python scripts/node_schema_coverage.py --boot

    # Quick slice:
    python scripts/node_schema_coverage.py --limit 6
    python scripts/node_schema_coverage.py --pack ComfyUI-Impact-Pack

Offline-safe: no live ComfyUI server needed. Network is only used by the
on-demand rungs (git clones of public repos) when ``VIBECOMFY_ON_DEMAND_SCHEMAS=1``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Make `import vibecomfy.*` work whether invoked as a script or via -m.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Activate the on-demand rungs unless the caller already set them. The sweep
# is meaningless without on-demand: the corpus alone trivially covers 100% of
# the sample because the sample IS what the corpus was built from.
os.environ.setdefault("VIBECOMFY_ON_DEMAND_SCHEMAS", "1")

from vibecomfy.node_packs import get_known_node_packs  # noqa: E402
from vibecomfy.schema.provider import get_authoring_schema_provider  # noqa: E402


# Source-provider names emitted by the resolution-ladder rungs. Used only to
# annotate the report — bucketing is driven by whether inputs are non-empty,
# NOT by provider name (a corpus row that forgot to stamp provenance still
# resolved with real inputs and counts as exact).
_LADDER_PROVIDERS = frozenset(
    {
        "object_info_index",
        "source_parser",
        "on_demand_static",
        "on_demand_runtime",
        "object_info_cache",
        "node_index",
        "vibecomfy_builtin",
    }
)


@dataclass
class ClassResult:
    class_type: str
    bucket: str  # "exact" | "structural" | "fail"
    source_provider: str | None = None
    confidence: float | None = None
    input_count: int = 0
    error: str | None = None


@dataclass
class PackResult:
    name: str
    repo: str
    class_count: int = 0
    exact: int = 0
    structural: int = 0
    fail: int = 0
    fail_classes: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    error: str | None = None  # whole-pack failure (timeout / unexpected exception)


def _bucket(schema: Any | None, *, error: str | None) -> ClassResult:
    class_type = ""
    if schema is not None:
        class_type = getattr(schema, "class_type", "") or ""
    if schema is None:
        return ClassResult(
            class_type=class_type,
            bucket="fail",
            error=error,
        )
    inputs = getattr(schema, "inputs", None) or {}
    provider = getattr(schema, "source_provider", None) or "unknown"
    confidence = getattr(schema, "confidence", None)
    input_count = len(inputs)
    # Bucketing is driven by INPUT PRESENCE, not provider name:
    #   * exact      = resolved with >=1 real input slot (the rung did real work)
    #   * structural = resolved object but zero inputs (degenerate — dynamic
    #                  INPUT_TYPES the AST could not evaluate, landed empty)
    # A corpus row that forgot to stamp source_provider still resolved with
    # real inputs and counts as exact; provider is recorded as metadata only.
    bucket = "exact" if input_count > 0 else "structural"
    return ClassResult(
        class_type=class_type,
        bucket=bucket,
        source_provider=provider,
        confidence=confidence,
        input_count=input_count,
    )


def _resolve_one(provider: Any, class_type: str) -> ClassResult:
    """Resolve a single class, catching every failure mode so one bad class
    can never abort the sweep."""
    try:
        schema = provider.get_schema(class_type)
    except Exception as exc:  # noqa: BLE001 — sweep must be robust per-class
        return ClassResult(
            class_type=class_type,
            bucket="fail",
            error=f"{type(exc).__name__}: {exc}",
        )
    return _bucket(schema, error=None)


def _resolve_pack(provider: Any, pack: Any, *, per_class_timeout: float) -> PackResult:
    classes = sorted(getattr(pack, "classes", ()) or ())
    result = PackResult(
        name=getattr(pack, "name", "?"),
        repo=getattr(pack, "repo", "") or "",
        class_count=len(classes),
    )
    if not classes:
        result.error = "no classes declared"
        return result
    start = time.monotonic()
    fail_classes: list[str] = []
    for class_type in classes:
        # Soft per-class budget: if the whole pack has already overrun, record
        # the remaining as fail rather than letting one pack run unbounded.
        if time.monotonic() - start > per_class_timeout * max(len(classes), 1):
            fail_classes.append(class_type)
            result.fail += 1
            continue
        cr = _resolve_one(provider, class_type)
        if cr.bucket == "exact":
            result.exact += 1
        elif cr.bucket == "structural":
            result.structural += 1
        else:
            result.fail += 1
            fail_classes.append(class_type)
    result.fail_classes = fail_classes
    result.elapsed_s = round(time.monotonic() - start, 2)
    return result


def _select_packs(
    all_packs: tuple[Any, ...],
    *,
    limit: int | None,
    pack_name: str | None,
) -> list[Any]:
    if pack_name is not None:
        matched = [p for p in all_packs if getattr(p, "name", "") == pack_name]
        if not matched:
            # Fuzzy: case-insensitive substring.
            needle = pack_name.casefold()
            matched = [p for p in all_packs if needle in getattr(p, "name", "").casefold()]
        return matched
    if limit is not None and limit > 0:
        return list(all_packs[:limit])
    return list(all_packs)


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 2) if total else 0.0


def _print_summary(
    pack_results: list[PackResult],
    *,
    stream=sys.stdout,
) -> None:
    total_classes = sum(r.class_count for r in pack_results)
    total_exact = sum(r.exact for r in pack_results)
    total_struct = sum(r.structural for r in pack_results)
    total_fail = sum(r.fail for r in pack_results)
    print("", file=stream)
    print("=" * 72, file=stream)
    print(f"L5 node-schema coverage — {len(pack_results)} pack(s), {total_classes} class(es)", file=stream)
    print("=" * 72, file=stream)
    print(f"  exact      : {total_exact:>6}  ({_pct(total_exact, total_classes):>5.2f}%)", file=stream)
    print(f"  structural : {total_struct:>6}  ({_pct(total_struct, total_classes):>5.2f}%)", file=stream)
    print(f"  fail       : {total_fail:>6}  ({_pct(total_fail, total_classes):>5.2f}%)", file=stream)
    print("-" * 72, file=stream)
    print(f"  {'pack':<40} {'cls':>5} {'exact':>6} {'struct':>7} {'fail':>5}  {'sec':>7}", file=stream)
    for r in pack_results:
        if r.class_count == 0:
            continue
        print(
            f"  {r.name[:40]:<40} {r.class_count:>5} {r.exact:>6} {r.structural:>7} {r.fail:>5}  {r.elapsed_s:>7.1f}",
            file=stream,
        )
    print("-" * 72, file=stream)
    if total_fail:
        # Sample the first 30 failing class names so the gap is visible.
        sample_fails: list[str] = []
        for r in pack_results:
            sample_fails.extend(r.fail_classes)
            if len(sample_fails) >= 30:
                break
        print(f"  coverage gap (first {min(30, total_fail)} of {total_fail} fails):", file=stream)
        for name in sample_fails[:30]:
            print(f"    - {name}", file=stream)
    print("=" * 72, file=stream)


def _to_jsonable(pack_results: list[PackResult]) -> dict[str, Any]:
    total_classes = sum(r.class_count for r in pack_results)
    total_exact = sum(r.exact for r in pack_results)
    total_struct = sum(r.structural for r in pack_results)
    total_fail = sum(r.fail for r in pack_results)
    all_fails: list[str] = []
    for r in pack_results:
        all_fails.extend(r.fail_classes)
    # Per-provider exact breakdown (useful to see which rung did the work).
    # We don't track this per-class to keep the report small; re-derive is not
    # possible without re-resolving, so we omit it. The pack-level counts are
    # the load-bearing output.
    return {
        "packs": [asdict(r) for r in pack_results],
        "totals": {
            "packs": len(pack_results),
            "classes": total_classes,
            "exact": total_exact,
            "structural": total_struct,
            "fail": total_fail,
            "exact_pct": _pct(total_exact, total_classes),
            "structural_pct": _pct(total_struct, total_classes),
            "fail_pct": _pct(total_fail, total_classes),
        },
        "fail_classes": all_fails,
        "env": {
            "VIBECOMFY_ON_DEMAND_SCHEMAS": os.environ.get("VIBECOMFY_ON_DEMAND_SCHEMAS"),
            "VIBECOMFY_ON_DEMAND_BOOT": os.environ.get("VIBECOMFY_ON_DEMAND_BOOT"),
        },
    }


def run_sweep(
    *,
    limit: int | None = None,
    pack_name: str | None = None,
    per_class_timeout: float = 60.0,
    boot: bool = False,
) -> list[PackResult]:
    """Run the coverage sweep and return per-pack results.

    Sets ``VIBECOMFY_ON_DEMAND_BOOT=1`` when ``boot=True`` so the runtime
    import rung is active (it executes third-party code in a subprocess).
    """
    if boot:
        os.environ["VIBECOMFY_ON_DEMAND_BOOT"] = "1"

    all_packs = get_known_node_packs()
    selected = _select_packs(all_packs, limit=limit, pack_name=pack_name)
    if not selected:
        print(
            f"No packs matched (limit={limit}, pack={pack_name!r}); "
            f"known packs: {len(all_packs)}",
            file=sys.stderr,
        )
        return []

    provider = get_authoring_schema_provider()
    print(
        f"Resolving {sum(len(getattr(p, 'classes', ()) or ()) for p in selected)} "
        f"classes across {len(selected)} pack(s) via the authoring provider "
        f"(on_demand_schemas={os.environ.get('VIBECOMFY_ON_DEMAND_SCHEMAS')}, "
        f"on_demand_boot={os.environ.get('VIBECOMFY_ON_DEMAND_BOOT')})",
        file=sys.stderr,
    )
    pack_results: list[PackResult] = []
    for idx, pack in enumerate(selected, 1):
        print(
            f"[{idx}/{len(selected)}] {getattr(pack, 'name', '?')} "
            f"({len(getattr(pack, 'classes', ()) or ())} classes)",
            file=sys.stderr,
        )
        try:
            pr = _resolve_pack(provider, pack, per_class_timeout=per_class_timeout)
        except Exception as exc:  # noqa: BLE001 — a whole pack must not abort the sweep
            pr = PackResult(
                name=getattr(pack, "name", "?"),
                repo=getattr(pack, "repo", "") or "",
                class_count=len(getattr(pack, "classes", ()) or ()),
                error=f"{type(exc).__name__}: {exc}",
            )
            pr.fail = pr.class_count
            pr.fail_classes = sorted(getattr(pack, "classes", ()) or ())
        pack_results.append(pr)
    return pack_results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="L5 node-schema coverage sweep (see docs/plans/all-installable-nodes.md).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only sweep the first N known packs (default: all).",
    )
    parser.add_argument(
        "--pack",
        type=str,
        default=None,
        help="Only sweep a single pack by name (exact or case-insensitive substring).",
    )
    parser.add_argument(
        "--boot",
        action="store_true",
        help="Enable the VIBECOMFY_ON_DEMAND_BOOT runtime-import rung (executes third-party code).",
    )
    parser.add_argument(
        "--per-class-timeout",
        type=float,
        default=60.0,
        help="Soft per-class budget in seconds (default 60). Bounds a single pack.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write a JSON report to this path (default: out/node_schema_coverage.json).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the printed summary (JSON report is still written if --out given).",
    )
    args = parser.parse_args(argv)

    pack_results = run_sweep(
        limit=args.limit,
        pack_name=args.pack,
        per_class_timeout=args.per_class_timeout,
        boot=args.boot,
    )
    if not pack_results:
        return 2

    if not args.quiet:
        _print_summary(pack_results)

    report = _to_jsonable(pack_results)
    out_path = Path(args.out) if args.out else _REPO_ROOT / "out" / "node_schema_coverage.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nWrote JSON report -> {out_path}", file=sys.stderr)

    totals = report["totals"]
    # Exit non-zero if exact coverage is below a sane floor (regression signal
    # when run unattended). Default floor is low (10%) so a partial --limit
    # slice does not spuriously fail; the guard test pins a higher floor.
    floor = float(os.environ.get("VIBECOMFY_COVERAGE_FLOOR", "10"))
    if totals["classes"] and totals["exact_pct"] < floor:
        print(
            f"ERROR: exact coverage {totals['exact_pct']}% below floor {floor}% "
            f"(set VIBECOMFY_COVERAGE_FLOOR to adjust)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
