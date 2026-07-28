"""Inquiry handling for demo_factory."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

LEAK_PATTERNS = [
    "candidate.",
    "golden.",
    "repaired.",
    "correct answer is",
    "the right way is",
    "should output",
    "expected result",
]


def get_transcript_inquiry(transcript_inquiry: str) -> str:
    """Get inquiry from transcript (no leakage check needed)."""
    return transcript_inquiry.strip()


def author_synthetic_inquiry(
    user_effect: str,
    capability: str = "processing",
    *,
    deepseek_api_key: str | None = None,
) -> str:
    """Author a realistic, leak-free inquiry describing the observable fault symptom.

    Speaks as an intermediate creative-tool user: what they expected vs. what they
    observed. Never mentions node ids, class names, socket names, or the repair.
    """
    capability = (capability or "processing").strip()
    effect = (user_effect or "the output doesn't match what I expected").strip()
    return (
        f"Something's off with the {capability} — {effect} "
        f"I expected the processing to show up in the saved output, but it doesn't. "
        f"Can you look at the workflow and fix it so the result actually reflects "
        f"the {capability} step?"
    )


def check_leakage(inquiry: str) -> dict[str, Any]:
    """Check inquiry for golden-receipt leakage patterns."""
    inquiry_lower = inquiry.lower()
    leaks = []

    for pattern in LEAK_PATTERNS:
        if pattern.lower() in inquiry_lower:
            leaks.append(pattern)

    return {
        "safe": len(leaks) == 0,
        "leaks": leaks,
        "inquiry_length": len(inquiry),
    }


def write_leakage_check(
    result: dict[str, Any],
    output_dir: Path,
) -> None:
    """Write leakage check result to JSON file."""
    output_dir = Path(output_dir)
    proof_path = output_dir / "proof" / "leakage-check.json"
    proof_path.parent.mkdir(parents=True, exist_ok=True)

    proof_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
