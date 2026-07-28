"""VibeComfy demo scenario factory.

Generates fault injection test cases from transcript evidence and
ready template workflows, with deterministic oracle evaluation.
"""
from __future__ import annotations

__all__ = [
    "load_transcript_run_dir",
    "derive_repair_delta",
    "FaultInjection",
    "Oracle",
    "Verdict",
    "run_baseline",
    "run_headless_fixer",
    "Case",
    "CampaignLedger",
]

# Version info
__version__ = "0.1.0"

# Import public APIs
from vibecomfy.demo_factory.transcript import load_transcript_run_dir
from vibecomfy.demo_factory.deltas import derive_repair_delta, FaultInjection
from vibecomfy.demo_factory.oracle import Oracle, Verdict
from vibecomfy.demo_factory.baseline import run_baseline
from vibecomfy.demo_factory.fixer import run_headless_fixer
from vibecomfy.demo_factory.case import Case
from vibecomfy.demo_factory.ledger import CampaignLedger
