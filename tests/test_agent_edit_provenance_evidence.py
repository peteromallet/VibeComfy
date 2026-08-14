"""Provenance evidence contract — the deterministic prefetch engine is gone.

The agent-judgment rework (Wave D) deleted the deterministic research engine
(``vibecomfy.executor.research`` / ``research_sources``), the
``ResearchResult`` / ``PrecedentAdaptationPlan`` / ``WorkflowSlice`` contracts,
and the ``_should_prefetch_research`` gate that decided whether the executor
pre-fetched provenance slices before the corpus.  Research is agent-owned
(C01): evidence arrives as an ``AgentResearchResult`` (trace + EvidencePack +
ledger), and the batch-REPL ``research(...)`` statement fails closed with
guidance to the ten named tool statements.

These tests pin the absence so a resurrected deterministic engine cannot
silently creep back in.
"""

from __future__ import annotations

import importlib

import pytest


def _assert_module_absent(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_deterministic_research_module_deleted() -> None:
    """vibecomfy.executor.research no longer exists."""
    _assert_module_absent("vibecomfy.executor.research")


def test_deterministic_research_sources_module_deleted() -> None:
    """vibecomfy.executor.research_sources no longer exists."""
    _assert_module_absent("vibecomfy.executor.research_sources")


def test_prefetch_gate_removed_from_core() -> None:
    """The legacy _should_prefetch_research gate is gone from the executor."""
    import vibecomfy.executor.core as core_module

    assert not hasattr(core_module, "_should_prefetch_research")
    # The legacy automatic research phase is a fail-closed stub kept only for
    # assert_not_called proofs; it must never be live-called.
    assert not hasattr(core_module, "_run_research_phase") or callable(
        getattr(core_module, "_run_research_phase", None)
    )
    with pytest.raises(RuntimeError, match="research engine removed"):
        core_module.run_research_phase()


def test_legacy_research_contracts_deleted_from_contracts() -> None:
    """The deleted research/precedent contracts are absent from contracts."""
    import vibecomfy.executor.contracts as contracts_module

    for name in (
        "ResearchResult",
        "PrecedentAdaptationPlan",
        "PrecedentPacket",
        "PrecedentOption",
        "WorkflowSlice",
    ):
        assert not hasattr(contracts_module, name), f"{name} must be deleted"


def test_active_research_shape_is_agent_owned() -> None:
    """The active research shape is AgentResearchResult with a ledger."""
    import vibecomfy.executor.core as core_module

    agent_result_cls = getattr(core_module, "AgentResearchResult", None)
    assert agent_result_cls is not None
    # The agent-owned research stage produces (trace, evidence_pack) for the
    # executor to wrap; both shapes are importable.
    from vibecomfy.executor.agent_research_stage import (  # noqa: F401
        AgentResearchTrace,
        run_agent_research_stage,
    )
    from vibecomfy.executor.evidence_pack import (  # noqa: F401
        EvidenceLedger,
        EvidencePack,
    )

    assert callable(run_agent_research_stage)
