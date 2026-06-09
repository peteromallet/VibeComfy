"""VibeComfy agentic-test embedding.

This package provides the Sisypy-compatible adapter, runner, scenarios, and briefs
that wire VibeComfy into the Sisypy agentic testing framework.

Layout:
  adapter.py   — VibeComfyProjectAdapter (extends FakeProjectAdapter)
  runner.py    — Scenario runner: load scenarios, dispatch actors, freeze evidence
  scenarios/   — Scenario YAML files (one per user ask)
  briefs/      — User-shaped markdown briefs
  README.md    — Handoff documentation for M2–M6
"""

from __future__ import annotations
