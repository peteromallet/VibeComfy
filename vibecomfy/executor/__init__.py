from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "build_classify_messages": ".prompts",
    "build_reply_messages": ".prompts",
    "ClassifyDecision": ".contracts",
    "collect_graph_facts": ".revision_evidence",
    "ExecutorRequest": ".contracts",
    "ExecutorResult": ".contracts",
    "GraphFacts": ".contracts",
    "HivemindClient": ".research",
    "HivemindError": ".research",
    "ImplementationResult": ".contracts",
    "build_execution_plan": ".execution_plan_builder",
    "detect_named_external_technologies": ".execution_plan_builder",
    "needs_precedent_plan": ".execution_plan_builder",
    "parse_classify_response": ".prompts",
    "parse_reply_response": ".prompts",
    "PrecedentOption": ".contracts",
    "PrecedentPacket": ".contracts",
    "Report": ".contracts",
    "research": ".research",
    "ResearchResult": ".contracts",
    "run_classify_turn": ".agent_backend",
    "run_executor": ".core",
    "run_local_research": ".research",
    "SelectedPrecedent": ".contracts",
    "run_reply_turn": ".agent_backend",
    "_default_hivemind_client": ".research",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
