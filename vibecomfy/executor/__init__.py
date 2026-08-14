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
    "EffectiveFieldFact": ".graph_facts",
    "EffectiveValueChange": ".graph_facts",
    "GraphFacts": ".contracts",
    "GraphFieldTarget": ".graph_facts",
    "ImplementationResult": ".contracts",
    "LinkedSourceFact": ".graph_facts",
    "parse_classify_response": ".prompts",
    "parse_target_node_type": ".contracts",
    "parse_reply_response": ".prompts",
    "Report": ".contracts",
    "run_classify_turn": ".agent_backend",
    "run_executor": ".core",
    "compare_effective_field": ".graph_facts",
    "inspect_effective_field": ".graph_facts",
    "run_reply_turn": ".agent_backend",
    "widget_field_name_for_index": ".graph_facts",
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
