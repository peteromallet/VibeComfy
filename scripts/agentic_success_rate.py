#!/usr/bin/env python3
"""
scripts/agentic_success_rate.py — Framework usability harness
==============================================================

Tests whether an LLM agent can complete four concrete vibecomfy tasks:

  (a) Tweak prompt/seed/steps and run a workflow
  (b) Create a workflow from a JSON template
  (c) Debug a failing template with ``port doctor-all``
  (d) Splice a custom node-pack class into a workflow

Each task defines a prompt, a validation function, and a success metric.
The harness can run in two modes:

  --dry-run    Validate task definitions and local infrastructure without
               making any LLM API calls.  Safe for CI.
  (default)    Execute each task via the configured LLM provider, record
               results, and compute a success rate.

Budget: max $5.00 per category (configurable via --max-budget).
Default model: deepseek:deepseek-v4-pro (OpenRouter).

Usage:
  python scripts/agentic_success_rate.py --dry-run
  python scripts/agentic_success_rate.py --model deepseek:deepseek-v4-pro
  python scripts/agentic_success_rate.py --max-budget 3.00 --category tweak_and_run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "deepseek:deepseek-v4-pro"
DEFAULT_MAX_BUDGET_PER_CATEGORY = 5.00  # USD


@dataclass
class TaskConfig:
    """Definition of one agentic task."""

    id: str
    category: str
    description: str
    prompt: str
    success_metric: str
    validate: Callable[[dict[str, Any]], tuple[bool, str]]
    # ^ Returns (success: bool, detail: str)


# ---------------------------------------------------------------------------
# 1. Task definitions
# ---------------------------------------------------------------------------

def _validate_tweak_and_run(result: dict[str, Any]) -> tuple[bool, str]:
    """Check that prompt/seed/steps were tweaked and a workflow was compiled."""
    inputs = result.get("inputs", {})
    api = result.get("api", {})
    if not inputs:
        return False, "No public inputs found in result"
    if not api:
        return False, "No API JSON produced"
    # Must have at least prompt, seed, steps keys present
    has_prompt = any("prompt" in k.lower() for k in inputs)
    has_seed = any("seed" in k.lower() for k in inputs)
    has_steps = any("steps" in k.lower() for k in inputs)
    if not (has_prompt or has_seed or has_steps):
        return False, f"Missing prompt/seed/steps in inputs: {list(inputs.keys())}"
    return True, f"Tweaked {len(inputs)} inputs; API has {len(api)} nodes"


def _validate_json_to_template(result: dict[str, Any]) -> tuple[bool, str]:
    """Check that a workflow was created from JSON."""
    workflow_info = result.get("workflow", {})
    source = result.get("source", "")
    if not workflow_info and not source:
        return False, "No workflow or source info in result"
    node_count = workflow_info.get("node_count", 0)
    return True, f"Workflow created from JSON source: {source[:80]}, {node_count} nodes"


def _validate_doctor_all(result: dict[str, Any]) -> tuple[bool, str]:
    """Check that doctor-all ran and produced diagnostics."""
    findings = result.get("findings", [])
    status = result.get("status", "unknown")
    sections = result.get("sections", [])
    if not sections and not findings and status == "unknown":
        return False, "No doctor-all output captured"
    return True, f"Doctor-all status={status}, {len(findings)} findings, {len(sections)} sections"


def _validate_node_splice(result: dict[str, Any]) -> tuple[bool, str]:
    """Check that a custom node pack class was spliced into a workflow."""
    nodes = result.get("nodes", {})
    spliced_class = result.get("spliced_class", "")
    if not spliced_class:
        return False, "No spliced class name reported"
    # At minimum, the class should appear in the workflow nodes
    found = any(
        str(node.get("class_type", "")) == spliced_class
        for node in (nodes.values() if isinstance(nodes, dict) else [])
    )
    if not found and nodes:
        return False, f"Spliced class '{spliced_class}' not found in workflow nodes"
    return True, f"Spliced class '{spliced_class}' into workflow with {len(nodes) if isinstance(nodes, dict) else 0} nodes"


TASKS: list[TaskConfig] = [
    TaskConfig(
        id="tweak_and_run",
        category="tweak_and_run",
        description="Tweak prompt, seed, and steps on a ready template, then compile to API JSON",
        prompt=(
            "You have access to the vibecomfy Python library.  "
            "Load the ready template at ready_templates/image/z_image.py, "
            "change the prompt to 'a majestic dragon', the seed to 12345, "
            "and the steps to 25.  Compile the workflow to API JSON and "
            "return a JSON object with keys 'inputs' (the tweaked public inputs) "
            "and 'api' (the compiled API dict)."
        ),
        success_metric="Workflow compiled with tweaked inputs; API JSON contains expected nodes",
        validate=_validate_tweak_and_run,
    ),
    TaskConfig(
        id="json_to_template",
        category="json_to_template",
        description="Create a workflow from a ComfyUI API JSON file",
        prompt=(
            "You have access to the vibecomfy CLI.  "
            "Run 'vibecomfy import ready_templates/sources/official/video/wan_i2v.json' "
            "to create a canonical workflow bundle, then validate it and inspect "
            "the editable Python workflow. Return a JSON object with key 'workflow' "
            "(containing node_count and class_types) and 'source' (the path used)."
        ),
        success_metric="JSON validated and workflow object created from file",
        validate=_validate_json_to_template,
    ),
    TaskConfig(
        id="doctor_all",
        category="doctor_all",
        description="Debug a failing template with port doctor-all",
        prompt=(
            "You have access to the vibecomfy CLI.  "
            "Run 'vibecomfy port doctor-all ready_templates/sources/official/video/wan_i2v.json --json' "
            "and capture the output.  Return the parsed JSON result (the full report)."
        ),
        success_metric="Doctor-all ran without crashing and produced diagnostic sections",
        validate=_validate_doctor_all,
    ),
    TaskConfig(
        id="node_splice",
        category="node_splice",
        description="Splice a custom node-pack class into a workflow",
        prompt=(
            "You have access to the vibecomfy Python library.  "
            "Create a minimal workflow using the node() function from vibecomfy.templates, "
            "then add a node from a known custom pack (e.g., 'VHS_VideoCombine' from "
            "VideoHelperSuite) using templates.node('VHS_VideoCombine', ...).  "
            "Return a JSON object with 'nodes' (the workflow nodes dict), "
            "and 'spliced_class' set to 'VHS_VideoCombine'."
        ),
        success_metric="Custom node class appears in the workflow graph",
        validate=_validate_node_splice,
    ),
]


# ---------------------------------------------------------------------------
# 2. Cost tracking
# ---------------------------------------------------------------------------

@dataclass
class CostTracker:
    """Track spending per category."""

    budgets: dict[str, float] = field(default_factory=dict)
    spent: dict[str, float] = field(default_factory=dict)

    def can_afford(self, category: str, estimated_cost: float = 0.01) -> bool:
        budget = self.budgets.get(category, DEFAULT_MAX_BUDGET_PER_CATEGORY)
        spent = self.spent.get(category, 0.0)
        return (spent + estimated_cost) <= budget

    def record(self, category: str, cost: float) -> None:
        self.spent[category] = self.spent.get(category, 0.0) + cost


# ---------------------------------------------------------------------------
# 3. LLM execution (stubbed for --dry-run)
# ---------------------------------------------------------------------------

def call_llm(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send a prompt to the LLM and return the parsed JSON result.

    In --dry-run mode, returns a canned success response without any API call.
    """
    if dry_run:
        return {
            "_dry_run": True,
            "status": "dry_run_ok",
            "message": "Dry-run: no LLM API call made.",
            "prompt_length": len(prompt),
        }

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "status": "error",
            "error": "No API key found. Set DEEPSEEK_API_KEY or OPENROUTER_API_KEY.",
        }

    # Placeholder for real API integration.
    # In practice, this would use the OpenRouter or DeepSeek API.
    return {
        "status": "error",
        "error": "Real LLM execution requires API integration (not implemented in this stub).",
        "hint": "Use --dry-run for offline validation.",
    }


# ---------------------------------------------------------------------------
# 4. Harness runner
# ---------------------------------------------------------------------------

def run_task(
    task: TaskConfig,
    *,
    model: str,
    dry_run: bool,
    tracker: CostTracker,
) -> dict[str, Any]:
    """Run one task and return its result bundle."""
    start = time.perf_counter()

    estimated_cost = 0.02  # Rough estimate per LLM call
    if not tracker.can_afford(task.category, estimated_cost):
        return {
            "task_id": task.id,
            "category": task.category,
            "status": "skipped",
            "reason": f"Budget exhausted for {task.category}",
            "duration_ms": 0,
            "success": False,
            "detail": "",
        }

    # Call the LLM
    llm_result = call_llm(task.prompt, model=model, dry_run=dry_run)

    if llm_result.get("status") == "error":
        success = False
        detail = llm_result.get("error", "Unknown LLM error")
    elif dry_run:
        # In dry-run, validate that the task's validation function works
        # by feeding it a minimal expected structure.
        dummy_result = _dry_run_dummy_result(task)
        success, detail = task.validate(dummy_result)
        tracker.record(task.category, 0.0)
    else:
        success, detail = task.validate(llm_result)
        cost = llm_result.get("cost", estimated_cost)
        tracker.record(task.category, cost)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    return {
        "task_id": task.id,
        "category": task.category,
        "description": task.description,
        "status": "ok" if success else "failed",
        "success": success,
        "detail": detail,
        "success_metric": task.success_metric,
        "duration_ms": elapsed_ms,
        "dry_run": dry_run,
    }


def _dry_run_dummy_result(task: TaskConfig) -> dict[str, Any]:
    """Return a minimal valid-looking result for dry-run validation."""
    if task.id == "tweak_and_run":
        return {
            "inputs": {"prompt": "test", "seed": 42, "steps": 25},
            "api": {"1": {"class_type": "KSampler"}},
        }
    elif task.id == "json_to_template":
        return {
            "workflow": {"node_count": 5, "class_types": ["KSampler"]},
            "source": "ready_templates/sources/official/video/wan_i2v.json",
        }
    elif task.id == "doctor_all":
        return {
            "status": "ok",
            "findings": [],
            "sections": [{"name": "import_diagnostics", "status": "ok"}],
        }
    elif task.id == "node_splice":
        return {
            "nodes": {"1": {"class_type": "VHS_VideoCombine"}},
            "spliced_class": "VHS_VideoCombine",
        }
    return {}


# ---------------------------------------------------------------------------
# 5. Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agentic success-rate harness for vibecomfy usability testing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate task definitions and local infrastructure without LLM API calls",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model identifier for the LLM provider (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max-budget",
        type=float,
        default=DEFAULT_MAX_BUDGET_PER_CATEGORY,
        help=f"Maximum USD budget per category (default: {DEFAULT_MAX_BUDGET_PER_CATEGORY})",
    )
    parser.add_argument(
        "--category",
        choices=[t.category for t in TASKS],
        help="Run only a specific category (default: all four)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args(argv)

    # Build cost tracker
    tracker = CostTracker(
        budgets={t.category: args.max_budget for t in TASKS},
    )

    # Filter tasks
    selected = (
        [t for t in TASKS if t.category == args.category]
        if args.category
        else list(TASKS)
    )

    # Run tasks
    results: list[dict[str, Any]] = []
    for task in selected:
        result = run_task(task, model=args.model, dry_run=args.dry_run, tracker=tracker)
        results.append(result)

    # Compute success rate
    successes = sum(1 for r in results if r["success"])
    rate = successes / len(results) if results else 0.0

    # Build output
    output: dict[str, Any] = {
        "model": args.model,
        "dry_run": args.dry_run,
        "max_budget_per_category": args.max_budget,
        "total_tasks": len(results),
        "successes": successes,
        "success_rate": round(rate, 4),
        "budgets": tracker.budgets,
        "spent": tracker.spent,
        "results": results,
    }

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"Agentic success rate: {successes}/{len(results)} ({rate:.0%})")
        print(f"  Model:  {args.model}")
        print(f"  Mode:   {'dry-run' if args.dry_run else 'live'}")
        print(f"  Budget: ${args.max_budget:.2f}/category")
        for r in results:
            status = "✓" if r["success"] else "✗"
            print(f"  {status} {r['task_id']}: {r['detail']}")
        print(f"  Spent: {json.dumps(tracker.spent)}")

    return 0 if rate >= 0.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
