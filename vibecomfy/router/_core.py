from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass

from vibecomfy.patches.registry import find_applicable
from vibecomfy.patches.types import Patch
from ._rules import rules
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True, slots=True)
class RouterResult:
    template_id: str
    explicit_patches: list[Patch]
    applicable_patches: list[Patch]


WorkflowLoader = Callable[[str], VibeWorkflow]

_RouteMeta = dict[str, str]


def list_routes() -> list[_RouteMeta]:
    """Return metadata for every registered route."""
    return [
        {
            "verb_kind": rule.verb_kind,
            "verb_name": rule.verb_name,
            "template_id": rule.template_id,
        }
        for rule in rules()
    ]


def describe_route(verb_kind: str, verb_name: str) -> list[_RouteMeta]:
    """Return metadata for routes matching *verb_kind* and *verb_name*."""
    return [
        {
            "verb_kind": rule.verb_kind,
            "verb_name": rule.verb_name,
            "template_id": rule.template_id,
        }
        for rule in rules()
        if rule.verb_kind == verb_kind and rule.verb_name == verb_name
    ]


def _build_missing_route_message(verb_kind: str, verb_name: str) -> str:
    all_routes = list_routes()
    verb_pairs = sorted({(r["verb_kind"], r["verb_name"]) for r in all_routes})
    available = [f"{k}.{n}" for k, n in verb_pairs]

    # Exact verb_kind matches
    kind_matches = [n for k, n in verb_pairs if k == verb_kind]

    parts: list[str] = [f"no route for {verb_kind}.{verb_name}"]

    if verb_kind and kind_matches:
        parts.append(f"(available '{verb_kind}' verbs: {', '.join(sorted(kind_matches))})")
    else:
        all_kinds = sorted({k for k, _ in verb_pairs})
        if all_kinds:
            parts.append(f"(available verb kinds: {', '.join(all_kinds)})")

    # Nearest-match suggestion via difflib
    candidates = [f"{k}.{n}" for k, n in verb_pairs]
    nearest = difflib.get_close_matches(f"{verb_kind}.{verb_name}", candidates, n=3, cutoff=0.0)
    if nearest:
        parts.append(f"nearest: {', '.join(nearest)}")

    return " ".join(parts)


def pick(
    verb_kind: str,
    verb_name: str,
    *,
    workflow_loader: WorkflowLoader | None = None,
    **inputs: object,
) -> RouterResult:
    for rule in rules():
        if rule.verb_kind != verb_kind or rule.verb_name != verb_name:
            continue
        if not rule.predicate(dict(inputs)):
            continue
        explicit_patches = list(rule.patches_factory(dict(inputs)))
        loader = workflow_loader or _default_workflow_loader
        workflow = loader(rule.template_id)
        return RouterResult(
            template_id=rule.template_id,
            explicit_patches=explicit_patches,
            applicable_patches=list(find_applicable(workflow)),
        )
    raise KeyError(_build_missing_route_message(verb_kind, verb_name))


def _default_workflow_loader(template_id: str) -> VibeWorkflow:
    from vibecomfy.cli_loader import load_workflow_any

    return load_workflow_any(template_id)


__all__ = [
    "RouterResult",
    "describe_route",
    "list_routes",
    "pick",
]
