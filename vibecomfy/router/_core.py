from __future__ import annotations

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
    raise KeyError(f"no template for verb={verb_kind}.{verb_name} inputs={inputs!r}")


def _default_workflow_loader(template_id: str) -> VibeWorkflow:
    from vibecomfy.cli_loader import load_workflow_any

    return load_workflow_any(template_id)


__all__ = ["RouterResult", "pick"]
