# Explore Hotshot XL Research Route — structural evidence brief

The goal is to prove the same executor path used by the frontend/API performs
research for a research-only question: the classifier's `search_directions`
scope the deterministic research query (domain anchors, never generic words
from the raw sentence) and its `source_preferences` become the explicit tier
tuple, then the semantic reply phase answers — the agent-edit batch gate never
runs. Structural/fake runs must be deterministic and avoid live model calls,
but the frozen shape (`executor_result.json`, `executor_report.json`,
`research.json`, `actions.jsonl`) should match the live agentic flow.
